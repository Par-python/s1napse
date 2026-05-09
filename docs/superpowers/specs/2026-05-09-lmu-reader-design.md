# Le Mans Ultimate Telemetry Reader — Design

**Branch:** `feat/lmu-listener`
**Date:** 2026-05-09
**Status:** Draft, pending implementation

## Context

S1napse currently has telemetry readers for Assetto Corsa (UDP), Assetto Corsa Competizione (shared memory), and iRacing (shared memory). Each implements the `TelemetryReader` interface in `s1napse/readers/base.py` and returns a flat dict of fields consumed by widgets and the lap-recording pipeline.

Le Mans Ultimate is built on the Studio 397 / rFactor 2 engine and exposes telemetry through the same `rFactor2SharedMemoryMapPlugin64.dll` that rF2 uses. Several established third-party tools (TinyPedal, SimHub, Sim Racing Studio, RaceLab) consume this exact path, so the integration surface is well-trodden and not a grey-area hack.

We have no LMU/Windows install available during development. The reader will be built blind against the documented rF2 shared memory layout and validated by a Windows tester.

## Goals

- Add an `LMUReader` that exposes the same field set as `ACCReader`, so existing widgets and recording logic work unchanged.
- Build it blind-safely: no live verification on the dev machine, but tight unit tests and a clear Windows verification checklist.
- Keep the change scoped to one new file plus minimal wiring edits — no refactor of the reader interface or anticipatory abstractions.
- Graceful degradation on macOS/Linux (where the dependency cannot import): `available=False`, no crashes.

## Non-goals

- An rF2 reader, an AMS2 reader, or any "Studio 397 family" base class. YAGNI — the boss asked for LMU.
- Exposing LMU-only fields (per-wheel suspension deflection, dampers, full opponent grid). Field shape mirrors ACC 1:1 to guarantee no widget breaks.
- Detecting "online race with telemetry restricted" (some online modes zero out physics fields, similar to iRacing). Documented, not auto-detected.
- A UDP-based path. LMU has one, but the shared memory plugin is the canonical and best-supported route.

## Approach

### Library choice

Depend on `pyRfactor2SharedMemory` (the most-used Python wrapper for the rF2 plugin). It mirrors how `pyaccsharedmemory` is used in `ACCReader`, and gives us `Cbytestring2Python` for decoding fixed-size byte strings. Lazy-imported inside `__init__` so non-Windows boxes set `available=False` instead of crashing.

The user installs the rF2 Shared Memory Plugin DLL themselves into LMU's plugin folder — that is not something the reader does.

### Field mapping (rF2 shared memory → ACC dict shape)

Read from two memory blocks the plugin publishes:
- `Telemetry` — per-vehicle physics, fast tick (engine, pedals, wheels, fuel)
- `Scoring` — session/lap/position state, slower tick (lap count, position, track name, weather)

| ACC field | rF2 source | Conversion / notes |
|---|---|---|
| `speed` | `Telemetry.mLocalVel` (3D vector, m/s) | magnitude × 3.6 → km/h |
| `rpm` | `Telemetry.mEngineRPM` | direct |
| `max_rpm` | `Telemetry.mEngineMaxRPM` | direct |
| `gear` | `Telemetry.mGear` | rF2: -1=R, 0=N, 1+=fwd → ACC: 0=R, 1=N, 2+=fwd. Add 1. |
| `throttle` | `Telemetry.mUnfilteredThrottle` (0–1) | ×100 |
| `brake` | `Telemetry.mUnfilteredBrake` (0–1) | ×100 |
| `steer_angle` | `Telemetry.mUnfilteredSteering` (-1..+1 normalized lock) | See open question 1. |
| `abs` | not exposed | return 0.0 |
| `tc` | not exposed | return 0.0 |
| `fuel` | `Telemetry.mFuel` | litres |
| `max_fuel` | `Telemetry.mFuelCapacity` | litres |
| `lap_time` | `Scoring.mVehicles[player].mLastLapTime` | seconds |
| `position` | `Scoring.mVehicles[player].mPlace` | int |
| `car_name` | `Scoring.mVehicles[player].mVehicleName` | bytes → `Cbytestring2Python` |
| `track_name` | `Scoring.mScoringInfo.mTrackName` | bytes → `Cbytestring2Python` |
| `lap_count` | `Scoring.mVehicles[player].mTotalLaps` | int |
| `current_time` | `Scoring.mCurrentET - mLapStartET` | seconds × 1000 → ms |
| `lap_dist_pct` | `Scoring.mVehicles[player].mLapDist / Scoring.mScoringInfo.mLapDist` | 0–1 |
| `world_x` | `Scoring.mVehicles[player].mPos.x` | direct |
| `world_z` | `Scoring.mVehicles[player].mPos.z` | direct |
| `lap_valid` | `Scoring.mVehicles[player].mCountLapFlag` | flag → bool |
| `is_in_pit_lane` | `Scoring.mVehicles[player].mInPits` | bool |
| `tyre_temp` (FL/FR/RL/RR) | `Telemetry.mWheels[i].mTireCarcassTemperature` | Kelvin → C; carcass temp is the single-value-per-tyre match for ACC |
| `tyre_pressure` (×4) | `Telemetry.mWheels[i].mPressure` | kPa, no conversion (ACC also kPa) |
| `brake_temp` (×4) | `Telemetry.mWheels[i].mBrakeTemp` | Kelvin → C |
| `tyre_wear` (×4) | `Telemetry.mWheels[i].mWear` (0–1) | ×100 |
| `tyre_compound` | `Telemetry.mFrontTireCompoundName` | bytes → `Cbytestring2Python` |
| `air_temp` | `Scoring.mScoringInfo.mAmbientTemp` | direct |
| `road_temp` | `Scoring.mScoringInfo.mTrackTemp` | direct |
| `session_type` | `Scoring.mScoringInfo.mSession` (int) | map to 'PRACTICE' / 'QUALIFY' / 'RACE' |
| `gap_ahead` | derive from neighbor's `mTimeBehindNext` | rF2 has no clean direct equivalent; if too noisy, return 0 |
| `gap_behind` | derive similarly | return 0 if no clean source |
| `stint_time_left` | not exposed | return 0 |
| `delta_lap_time` | not exposed cleanly | return 0 |
| `estimated_lap` | `Scoring.mVehicles[player].mBestLapTime` × 1000 | ms |
| `brake_bias` | `Telemetry.mRearBrakeBias` (0–1) | direct |

#### Open questions for the Windows tester

1. **`steer_angle` units.** ACC reports radians. rF2's `mUnfilteredSteering` is normalized -1..+1. The likely conversion is: angle_deg = `mUnfilteredSteering` × `mPhysicalSteeringWheelRange / 2`, then deg→rad. Verify against the [telemetry tab](../../../s1napse/widgets/tabs/telemetry.py) — if it expects radians, apply the conversion; if it tolerates raw normalized, leave it.
2. **Tyre temp source.** Carcass temp is the cleanest 1:1 match for ACC's single-value-per-tyre. If finer detail is wanted later, the surface inner/mid/outer trio (`mTemperature[3]`) maps to iRacing's `tyre_imo` shape and could be added separately — out of scope here.
3. **`gap_ahead` / `gap_behind` derivation.** rF2 gives `mTimeBehindNext` per vehicle but not a direct gap-behind. Default to 0 in v1 if the derivation looks lossy; ACC widgets already tolerate zeros for these.

### Lifecycle and error handling

`__init__` mirrors `ACCReader`:

```python
self._last_read_ok = False
try:
    from pyRfactor2SharedMemory.sharedMemoryAPI import Cbytestring2Python, SimInfoAPI
    self.info = SimInfoAPI()
    self.available = True
except Exception as e:
    print(f"LMU Reader initialization failed: {e}")
    print("Install with: pip install pyRfactor2SharedMemory")
    print("Also: install rFactor2SharedMemoryMapPlugin64.dll into LMU's Plugins folder")
    self.available = False
```

`read()` returns `None` when:
- `not self.available`
- player telemetry / scoring blocks return `None` or `mID == -1` (no active session)
- the `mElapsedTime` (or equivalent freshness counter) is stale across consecutive reads (game paused or in menus)
- any field-extraction exception is caught (matches ACCReader's try/except wrap)

`is_connected()` mirrors `ACCReader`: cache `_last_read_ok` for fast checks, fall back to a probe call when not yet validated.

No `connect()`/`disconnect()` and no thread management — shared memory is passive. Same as `ACCReader`.

### Wiring into the app

Three edits in [app.py](../../../s1napse/app.py), each tightly scoped:

1. **Line 47 import** — add `LMUReader` to the existing `from .readers import ...` line.
2. **~Line 138 construction** — `self.lmu_reader = LMUReader()` alongside `acc_reader` and `ir_reader`.
3. **~Line 3270 isinstance dispatch** — since the field shape matches ACC exactly, share the branch: `isinstance(self.current_reader, (ACCReader, LMUReader))`.

The implementation plan will also identify wherever the source-selector UI lists AC/ACC/iRacing and add LMU as an option there.

`requirements.txt` gains `pyRfactor2SharedMemory`. Mirror however `pyaccsharedmemory` is listed today.

### Setup documentation

Ship a short tester-facing guide (either appended to `REAL_RACING_GUIDE.md` or as `docs/lmu-setup.md` — pick during implementation) covering:

- Where to download `rFactor2SharedMemoryMapPlugin64.dll`.
- Exact path it goes in (LMU's `Plugins` folder).
- The `CustomPluginVariables.JSON` `" Enabled"` leading-space quirk.
- How to verify the plugin is publishing (e.g. open S1napse, pick LMU, check `is_connected`).
- The known online-race telemetry-restricted caveat.

### Testing strategy

**Unit tests** (`tests/test_lmu_reader.py`, runnable on macOS):
- Mock `SimInfoAPI`. Verify gear normalization across {-1, 0, 1, 2, ..., N}.
- Verify unit conversions: m/s → km/h on speed, ×100 on pedals and wear, Kelvin → C on tyre/brake temps, seconds × 1000 on `current_time` and `estimated_lap`.
- Verify bytes decoding via `Cbytestring2Python` for `car_name`, `track_name`, `tyre_compound`.
- Verify `available=False` returns `None` from `read()`.
- Verify stale `mElapsedTime` returns `None`.
- Verify exception inside field extraction returns `None` and sets `_last_read_ok = False`.

**Shape-conformance test:** assert `LMUReader.read()` (with mocked good data) returns a dict whose `.keys()` exactly equals `ACCReader.read()`'s key set. Catches mapping omissions before the Windows tester sees them.

**Windows verification checklist** (acceptance criteria for the PR):
- [ ] `pyRfactor2SharedMemory` installs cleanly on Windows.
- [ ] `rFactor2SharedMemoryMapPlugin64.dll` installed into LMU's `Plugins` folder.
- [ ] Plugin enabled in `CustomPluginVariables.JSON` (note the leading-space `" Enabled"` quirk).
- [ ] `LMUReader().is_connected()` returns True during an active LMU session.
- [ ] `speed` reads correctly in km/h at a known reference speed (e.g. pit limiter).
- [ ] `steer_angle` matches expected radians at full lock (resolves open question 1).
- [ ] All four wheels report non-zero `tyre_temp` / `tyre_pressure` / `brake_temp` during driving.
- [ ] `lap_count`, `current_time`, `lap_time` advance correctly across a completed lap.
- [ ] `session_type` reports correctly in Practice, Qualifying, and Race.
- [ ] `is_in_pit_lane` toggles when entering / leaving the pit lane.
- [ ] `world_x` / `world_z` populate the trackmap consistently with ACC behavior.

## Risks

- **Blind-build mapping errors.** Mitigated by ACC-shape conformance test, the verification checklist, and explicit "open questions" the tester resolves on first run.
- **`pyRfactor2SharedMemory` upstream drift.** The library is reasonably maintained but small. If a future LMU build changes the struct layout, the wrapper updates may lag. Same risk profile as `pyaccsharedmemory`.
- **Online-race telemetry restrictions.** Some LMU multiplayer modes zero out physics. Document in the setup guide; do not auto-detect.
- **Plugin install confusion.** The `CustomPluginVariables.JSON` " Enabled" leading-space gotcha will trip testers. Call it out in the setup doc.

## Out of scope (future work)

- LMU-only field exposure (suspension, dampers, opponent grid) for richer widgets.
- Per-wheel surface temperature trio (iRacing's `tyre_imo` shape) for LMU.
- Auto-detection of the "online race telemetry restricted" state.
- A shared rF2-family base class if/when an rF2 or AMS2 reader is added.
