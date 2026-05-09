# Le Mans Ultimate Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `LMUReader` that pulls telemetry from Le Mans Ultimate via the rFactor 2 Shared Memory Plugin, exposing the same field shape as `ACCReader` so all existing widgets and recording logic work unchanged.

**Architecture:** New `s1napse/readers/lmu.py` mirroring `ACCReader`'s structure. Lazy-imports `pyRfactor2SharedMemory` so non-Windows boxes degrade to `available=False`. Wires into [app.py](../../../s1napse/app.py) at five sites: import, construction, game-combo, `_on_game_changed`, `_detect_game`, label dispatch. Validation done blind via mocked unit tests + a Windows verification checklist for the tester.

**Tech Stack:** Python 3, PyQt6 (existing), `pyRfactor2SharedMemory` (new dep), pytest (existing).

**Spec:** [docs/superpowers/specs/2026-05-09-lmu-reader-design.md](../specs/2026-05-09-lmu-reader-design.md)

---

## Task 1: Add `pyRfactor2SharedMemory` dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependency**

Open `requirements.txt`. Add after the `pyaccsharedmemory` line:

```
pyRfactor2SharedMemory>=1.0.0
```

The exact pin can be relaxed — it's optional/Windows-effective like `pyaccsharedmemory`, and the reader handles import failure gracefully.

- [ ] **Step 2: Try installing locally**

Run: `pip install pyRfactor2SharedMemory`

Expected on macOS/Linux: may install but be non-functional, or may fail. Either is fine — the reader's lazy import handles it.

If install fails on macOS/Linux with a Windows-only error, that's expected. Proceed.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pyRfactor2SharedMemory dependency for LMU reader"
```

---

## Task 2: Skeleton `LMUReader` class with graceful unavailability

**Files:**
- Create: `s1napse/readers/lmu.py`
- Test: `tests/test_lmu_reader.py`

This task creates the file with the init/availability path only. Field reads come in later tasks. Write the test first (TDD).

- [ ] **Step 1: Write the failing test**

Create `tests/test_lmu_reader.py`:

```python
"""Unit tests for LMUReader — runnable on macOS/Linux via mocking."""

from unittest.mock import patch, MagicMock


def test_lmu_reader_unavailable_when_import_fails():
    """If pyRfactor2SharedMemory cannot be imported, the reader should
    set available=False and read()/is_connected() should return safely."""
    # Force import failure inside __init__ by patching the module's import.
    with patch.dict('sys.modules', {'pyRfactor2SharedMemory.sharedMemoryAPI': None}):
        from s1napse.readers.lmu import LMUReader
        # Re-instantiating should hit the except path because the patched
        # entry forces ImportError on `from ... import ...`.
        reader = LMUReader()
        assert reader.available is False
        assert reader.read() is None
        assert reader.is_connected() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lmu_reader.py::test_lmu_reader_unavailable_when_import_fails -v`

Expected: FAIL with `ModuleNotFoundError: No module named 's1napse.readers.lmu'`.

- [ ] **Step 3: Create the skeleton implementation**

Create `s1napse/readers/lmu.py`:

```python
"""Le Mans Ultimate via the rFactor 2 Shared Memory Plugin.

Requires:
    - pip install pyRfactor2SharedMemory
    - rFactor2SharedMemoryMapPlugin64.dll installed in LMU's Plugins folder
      and enabled in CustomPluginVariables.JSON (note the leading-space
      ' Enabled' key — required by the game).
"""

from .base import TelemetryReader


class LMUReader(TelemetryReader):
    """Le Mans Ultimate via the rFactor 2 Shared Memory Plugin."""

    def __init__(self):
        self._last_read_ok = False
        self.info = None
        self._cbytestring = None
        try:
            from pyRfactor2SharedMemory.sharedMemoryAPI import (
                Cbytestring2Python,
                SimInfoAPI,
            )
            self.info = SimInfoAPI()
            self._cbytestring = Cbytestring2Python
            self.available = True
        except Exception as e:
            print(f"LMU Reader initialization failed: {e}")
            print("Install with: pip install pyRfactor2SharedMemory")
            print(
                "Also: install rFactor2SharedMemoryMapPlugin64.dll into "
                "LMU's Plugins folder and enable it in CustomPluginVariables.JSON"
            )
            self.available = False

    def read(self):
        if not self.available:
            self._last_read_ok = False
            return None
        # Field extraction lands in Task 3.
        self._last_read_ok = False
        return None

    def is_connected(self):
        if not self.available:
            return False
        return self._last_read_ok
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lmu_reader.py::test_lmu_reader_unavailable_when_import_fails -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add s1napse/readers/lmu.py tests/test_lmu_reader.py
git commit -m "feat(lmu): add LMUReader skeleton with graceful unavailability"
```

---

## Task 3: Field extraction — basic physics (speed, rpm, gear, pedals, fuel)

**Files:**
- Modify: `s1napse/readers/lmu.py`
- Modify: `tests/test_lmu_reader.py`

Implement the `Telemetry` block portion of `read()`. Use a fake `SimInfoAPI` in tests.

- [ ] **Step 1: Add the test fixture and physics tests**

Append to `tests/test_lmu_reader.py`:

```python
import math


def _make_fake_telemetry(**overrides):
    """Build a MagicMock matching the rF2 Telemetry struct shape we use."""
    telem = MagicMock()
    telem.mEngineRPM = 7000.0
    telem.mEngineMaxRPM = 9000.0
    telem.mGear = 3
    telem.mUnfilteredThrottle = 0.85
    telem.mUnfilteredBrake = 0.10
    telem.mUnfilteredSteering = -0.25
    telem.mFuel = 42.5
    telem.mFuelCapacity = 100.0
    telem.mLocalVel = MagicMock(x=10.0, y=0.0, z=0.0)  # |v| = 10 m/s = 36 km/h
    telem.mRearBrakeBias = 0.55
    telem.mElapsedTime = 123.456
    telem.mFrontTireCompoundName = b"Hard\x00\x00"
    # 4 wheels, default zeros — Task 4 fills these.
    wheel = MagicMock(
        mTireCarcassTemperature=300.0,  # Kelvin
        mPressure=180.0,
        mBrakeTemp=400.0,  # Kelvin
        mWear=0.0,
    )
    telem.mWheels = [wheel, wheel, wheel, wheel]
    for k, v in overrides.items():
        setattr(telem, k, v)
    return telem


def _make_fake_scoring(**overrides):
    """Build a MagicMock matching the rF2 Scoring struct shape we use."""
    veh = MagicMock()
    veh.mLastLapTime = 91.234
    veh.mPlace = 4
    veh.mVehicleName = b"Ferrari 499P\x00"
    veh.mTotalLaps = 7
    veh.mLapStartET = 100.0
    veh.mLapDist = 1500.0
    veh.mPos = MagicMock(x=123.0, y=0.0, z=-456.0)
    veh.mCountLapFlag = 1
    veh.mInPits = 0
    veh.mBestLapTime = 90.5
    veh.mTimeBehindNext = 1.5

    info = MagicMock()
    info.mTrackName = b"Le Mans\x00"
    info.mAmbientTemp = 22.0
    info.mTrackTemp = 35.0
    info.mSession = 6  # race
    info.mLapDist = 13629.0
    info.mCurrentET = 191.234

    scoring = MagicMock()
    scoring.mScoringInfo = info
    scoring.mVehicles = [veh]
    for k, v in overrides.items():
        setattr(scoring, k, v)
    return scoring


def _build_reader_with_fakes(telem, scoring):
    """Bypass __init__'s real import, install fakes, return a ready reader."""
    from s1napse.readers.lmu import LMUReader
    reader = LMUReader.__new__(LMUReader)
    reader.available = True
    reader._last_read_ok = False

    api = MagicMock()
    api.playerTelemetry.return_value = telem
    api.playerScoring.return_value = scoring
    reader.info = api

    # Cbytestring decoder: strip NULs and decode utf-8.
    reader._cbytestring = lambda b: b.split(b"\x00", 1)[0].decode("utf-8", "ignore")
    return reader


def test_speed_converts_m_s_to_km_h():
    telem = _make_fake_telemetry()
    scoring = _make_fake_scoring()
    reader = _build_reader_with_fakes(telem, scoring)
    data = reader.read()
    assert math.isclose(data['speed'], 36.0, abs_tol=0.01)


def test_rpm_and_max_rpm_pass_through():
    reader = _build_reader_with_fakes(_make_fake_telemetry(), _make_fake_scoring())
    data = reader.read()
    assert data['rpm'] == 7000.0
    assert data['max_rpm'] == 9000.0


def test_gear_normalization():
    """rF2: -1=R, 0=N, 1+=fwd → ACC: 0=R, 1=N, 2+=fwd. Add 1."""
    for rf2_gear, acc_gear in [(-1, 0), (0, 1), (1, 2), (5, 6)]:
        reader = _build_reader_with_fakes(
            _make_fake_telemetry(mGear=rf2_gear),
            _make_fake_scoring(),
        )
        assert reader.read()['gear'] == acc_gear, f"gear={rf2_gear}"


def test_pedals_scale_to_percent():
    reader = _build_reader_with_fakes(
        _make_fake_telemetry(mUnfilteredThrottle=0.85, mUnfilteredBrake=0.10),
        _make_fake_scoring(),
    )
    data = reader.read()
    assert math.isclose(data['throttle'], 85.0, abs_tol=0.01)
    assert math.isclose(data['brake'], 10.0, abs_tol=0.01)


def test_fuel_passthrough():
    reader = _build_reader_with_fakes(
        _make_fake_telemetry(mFuel=42.5, mFuelCapacity=100.0),
        _make_fake_scoring(),
    )
    data = reader.read()
    assert data['fuel'] == 42.5
    assert data['max_fuel'] == 100.0
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `pytest tests/test_lmu_reader.py -v`

Expected: New tests FAIL because `read()` still returns `None`.

- [ ] **Step 3: Implement physics field extraction**

Replace the `read()` body in `s1napse/readers/lmu.py` with:

```python
    def read(self):
        if not self.available:
            self._last_read_ok = False
            return None
        try:
            telem = self.info.playerTelemetry()
            scoring = self.info.playerScoring()
            if telem is None or scoring is None:
                self._last_read_ok = False
                return None

            # Speed: |mLocalVel| in m/s → km/h
            v = telem.mLocalVel
            speed_ms = (v.x * v.x + v.y * v.y + v.z * v.z) ** 0.5
            speed_kmh = speed_ms * 3.6

            # Gear: rF2 (-1=R, 0=N, 1+=fwd) → ACC (0=R, 1=N, 2+=fwd)
            gear = telem.mGear + 1

            self._last_read_ok = True
            return {
                'speed':       speed_kmh,
                'rpm':         telem.mEngineRPM,
                'max_rpm':     telem.mEngineMaxRPM,
                'gear':        gear,
                'throttle':    telem.mUnfilteredThrottle * 100.0,
                'brake':       telem.mUnfilteredBrake * 100.0,
                'steer_angle': telem.mUnfilteredSteering,
                'abs':         0.0,
                'tc':          0.0,
                'fuel':        telem.mFuel,
                'max_fuel':    telem.mFuelCapacity,
                'brake_bias':  float(telem.mRearBrakeBias),
            }
        except Exception as e:
            print(f"LMU read error: {e}")
            self._last_read_ok = False
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lmu_reader.py -v`

Expected: All physics tests PASS.

- [ ] **Step 5: Commit**

```bash
git add s1napse/readers/lmu.py tests/test_lmu_reader.py
git commit -m "feat(lmu): extract basic physics (speed, rpm, gear, pedals, fuel)"
```

---

## Task 4: Field extraction — wheels (tyre temp / pressure / wear, brake temp)

**Files:**
- Modify: `s1napse/readers/lmu.py`
- Modify: `tests/test_lmu_reader.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lmu_reader.py`:

```python
def test_tyre_temp_kelvin_to_celsius():
    """rF2 tire carcass temp is Kelvin; ACC dict expects Celsius."""
    wheels = [
        MagicMock(mTireCarcassTemperature=350.0, mPressure=180.0,
                  mBrakeTemp=500.0, mWear=0.05),
        MagicMock(mTireCarcassTemperature=355.0, mPressure=181.0,
                  mBrakeTemp=505.0, mWear=0.06),
        MagicMock(mTireCarcassTemperature=340.0, mPressure=175.0,
                  mBrakeTemp=480.0, mWear=0.04),
        MagicMock(mTireCarcassTemperature=345.0, mPressure=176.0,
                  mBrakeTemp=485.0, mWear=0.045),
    ]
    telem = _make_fake_telemetry()
    telem.mWheels = wheels
    reader = _build_reader_with_fakes(telem, _make_fake_scoring())
    data = reader.read()
    # Kelvin - 273.15
    assert math.isclose(data['tyre_temp'][0], 350.0 - 273.15, abs_tol=0.01)
    assert math.isclose(data['tyre_temp'][3], 345.0 - 273.15, abs_tol=0.01)


def test_brake_temp_kelvin_to_celsius():
    wheels = [
        MagicMock(mTireCarcassTemperature=300.0, mPressure=180.0,
                  mBrakeTemp=600.0, mWear=0.0),
    ] * 4
    telem = _make_fake_telemetry()
    telem.mWheels = wheels
    reader = _build_reader_with_fakes(telem, _make_fake_scoring())
    data = reader.read()
    for v in data['brake_temp']:
        assert math.isclose(v, 600.0 - 273.15, abs_tol=0.01)


def test_tyre_pressure_passthrough():
    """rF2 pressure is kPa; ACC also kPa — no conversion."""
    wheels = [
        MagicMock(mTireCarcassTemperature=300.0, mPressure=178.0,
                  mBrakeTemp=400.0, mWear=0.0),
    ] * 4
    telem = _make_fake_telemetry()
    telem.mWheels = wheels
    reader = _build_reader_with_fakes(telem, _make_fake_scoring())
    data = reader.read()
    assert data['tyre_pressure'] == [178.0, 178.0, 178.0, 178.0]


def test_tyre_wear_scales_to_percent():
    """rF2 mWear is 0..1; ACC reader returns 0..100."""
    wheels = [
        MagicMock(mTireCarcassTemperature=300.0, mPressure=180.0,
                  mBrakeTemp=400.0, mWear=0.25),
    ] * 4
    telem = _make_fake_telemetry()
    telem.mWheels = wheels
    reader = _build_reader_with_fakes(telem, _make_fake_scoring())
    data = reader.read()
    assert data['tyre_wear'] == [25.0, 25.0, 25.0, 25.0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lmu_reader.py -v`

Expected: 4 new tests FAIL because the wheel fields aren't in the dict yet.

- [ ] **Step 3: Add wheel field extraction**

In `s1napse/readers/lmu.py`, inside `read()` just before `return {`, add:

```python
            wheels = telem.mWheels
            tyre_temp = [float(w.mTireCarcassTemperature) - 273.15 for w in wheels]
            tyre_pressure = [float(w.mPressure) for w in wheels]
            brake_temp = [float(w.mBrakeTemp) - 273.15 for w in wheels]
            tyre_wear = [float(w.mWear) * 100.0 for w in wheels]
```

Then add these keys to the returned dict (anywhere before the closing brace):

```python
                'tyre_temp':     tyre_temp,
                'tyre_pressure': tyre_pressure,
                'brake_temp':    brake_temp,
                'tyre_wear':     tyre_wear,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lmu_reader.py -v`

Expected: All wheel tests PASS.

- [ ] **Step 5: Commit**

```bash
git add s1napse/readers/lmu.py tests/test_lmu_reader.py
git commit -m "feat(lmu): extract wheel fields (tyre temp/pressure/wear, brake temp)"
```

---

## Task 5: Field extraction — scoring (laps, position, names, session, world pos)

**Files:**
- Modify: `s1napse/readers/lmu.py`
- Modify: `tests/test_lmu_reader.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lmu_reader.py`:

```python
def test_lap_fields():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mLastLapTime = 91.234
    scoring.mVehicles[0].mTotalLaps = 7
    scoring.mScoringInfo.mCurrentET = 200.0
    scoring.mVehicles[0].mLapStartET = 105.0
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    data = reader.read()
    assert math.isclose(data['lap_time'], 91.234, abs_tol=0.001)
    assert data['lap_count'] == 7
    # current_time is (mCurrentET - mLapStartET) seconds × 1000 → ms
    assert math.isclose(data['current_time'], 95.0 * 1000.0, abs_tol=0.1)


def test_position_passthrough():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mPlace = 12
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    assert reader.read()['position'] == 12


def test_lap_dist_pct_normalised():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mLapDist = 1500.0
    scoring.mScoringInfo.mLapDist = 6000.0
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    assert math.isclose(reader.read()['lap_dist_pct'], 0.25, abs_tol=0.001)


def test_world_position_xz():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mPos = MagicMock(x=111.0, y=2.0, z=-222.0)
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    data = reader.read()
    assert data['world_x'] == 111.0
    assert data['world_z'] == -222.0


def test_pit_and_lap_validity_flags():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mInPits = 1
    scoring.mVehicles[0].mCountLapFlag = 0  # invalid
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    data = reader.read()
    assert data['is_in_pit_lane'] is True
    assert data['lap_valid'] is False


def test_byte_string_names_decode():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mVehicleName = b"Porsche 963\x00\x00\x00"
    scoring.mScoringInfo.mTrackName = b"Sebring International\x00"
    telem = _make_fake_telemetry()
    telem.mFrontTireCompoundName = b"Soft\x00\x00\x00"
    reader = _build_reader_with_fakes(telem, scoring)
    data = reader.read()
    assert data['car_name'] == "Porsche 963"
    assert data['track_name'] == "Sebring International"
    assert data['tyre_compound'] == "Soft"


def test_session_type_mapping():
    """rF2 mSession: 0=test, 1-4=practice, 5-8=qualify, 9=warmup, 10-13=race."""
    cases = [
        (1, 'PRACTICE'),
        (5, 'QUALIFY'),
        (9, 'PRACTICE'),  # warmup → treat as practice
        (10, 'RACE'),
        (13, 'RACE'),
    ]
    for code, expected in cases:
        scoring = _make_fake_scoring()
        scoring.mScoringInfo.mSession = code
        reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
        assert reader.read()['session_type'] == expected, f"code={code}"


def test_weather_passthrough():
    scoring = _make_fake_scoring()
    scoring.mScoringInfo.mAmbientTemp = 18.5
    scoring.mScoringInfo.mTrackTemp = 28.0
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    data = reader.read()
    assert data['air_temp'] == 18.5
    assert data['road_temp'] == 28.0


def test_estimated_lap_seconds_to_ms():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mBestLapTime = 89.123
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    assert math.isclose(reader.read()['estimated_lap'], 89123.0, abs_tol=1.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lmu_reader.py -v`

Expected: New tests FAIL.

- [ ] **Step 3: Add scoring field extraction**

Update `read()` in `s1napse/readers/lmu.py`. Add a session-type mapping helper at module top (after imports):

```python
def _map_session_type(code: int) -> str:
    """rF2 mSession codes → ACC-style labels.
    0=test day, 1-4=practice, 5-8=qualify, 9=warmup, 10-13=race.
    """
    if 5 <= code <= 8:
        return 'QUALIFY'
    if 10 <= code <= 13:
        return 'RACE'
    return 'PRACTICE'
```

Inside `read()`, after the wheels block, add:

```python
            veh = scoring.mVehicles[0]
            info = scoring.mScoringInfo

            decode = self._cbytestring
            car_name   = decode(veh.mVehicleName)   if veh.mVehicleName   else ''
            track_name = decode(info.mTrackName)    if info.mTrackName    else ''
            compound   = decode(telem.mFrontTireCompoundName) \
                         if telem.mFrontTireCompoundName else ''

            current_time_ms = (info.mCurrentET - veh.mLapStartET) * 1000.0
            track_len = float(info.mLapDist) or 1.0
            lap_pct = float(veh.mLapDist) / track_len
```

Then add these keys to the returned dict:

```python
                'lap_time':       float(veh.mLastLapTime),
                'position':       int(veh.mPlace),
                'car_name':       car_name,
                'track_name':     track_name,
                'lap_count':      int(veh.mTotalLaps),
                'current_time':   current_time_ms,
                'lap_dist_pct':   lap_pct,
                'world_x':        float(veh.mPos.x),
                'world_z':        float(veh.mPos.z),
                'lap_valid':      bool(veh.mCountLapFlag),
                'is_in_pit_lane': bool(veh.mInPits),
                'tyre_compound':  compound,
                'air_temp':       float(info.mAmbientTemp),
                'road_temp':      float(info.mTrackTemp),
                'session_type':   _map_session_type(int(info.mSession)),
                'estimated_lap':  float(veh.mBestLapTime) * 1000.0,
                'gap_ahead':      0,
                'gap_behind':     0,
                'stint_time_left': 0,
                'delta_lap_time': 0,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lmu_reader.py -v`

Expected: All scoring tests PASS.

- [ ] **Step 5: Commit**

```bash
git add s1napse/readers/lmu.py tests/test_lmu_reader.py
git commit -m "feat(lmu): extract scoring fields (laps, position, names, session, world pos)"
```

---

## Task 6: Failure-mode tests (no session, exceptions, no-op when unavailable)

**Files:**
- Modify: `s1napse/readers/lmu.py`
- Modify: `tests/test_lmu_reader.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lmu_reader.py`:

```python
def test_read_returns_none_when_no_session():
    """playerTelemetry/playerScoring may return None when no session active."""
    from s1napse.readers.lmu import LMUReader
    reader = LMUReader.__new__(LMUReader)
    reader.available = True
    reader._last_read_ok = True  # was True; should flip to False
    api = MagicMock()
    api.playerTelemetry.return_value = None
    api.playerScoring.return_value = None
    reader.info = api
    reader._cbytestring = lambda b: b.decode('utf-8', 'ignore')
    assert reader.read() is None
    assert reader._last_read_ok is False


def test_read_swallows_field_exceptions():
    """If any field access raises, read() returns None rather than crashing."""
    from s1napse.readers.lmu import LMUReader
    reader = LMUReader.__new__(LMUReader)
    reader.available = True
    reader._last_read_ok = True
    api = MagicMock()
    bad_telem = MagicMock()
    # Accessing mLocalVel raises.
    type(bad_telem).mLocalVel = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("kaboom"))
    )
    api.playerTelemetry.return_value = bad_telem
    api.playerScoring.return_value = _make_fake_scoring()
    reader.info = api
    reader._cbytestring = lambda b: b.decode('utf-8', 'ignore')
    assert reader.read() is None
    assert reader._last_read_ok is False


def test_is_connected_caches_last_read_state():
    """is_connected() should reflect the latest read() outcome."""
    reader = _build_reader_with_fakes(_make_fake_telemetry(), _make_fake_scoring())
    assert reader.is_connected() is False  # nothing read yet
    reader.read()
    assert reader.is_connected() is True
```

- [ ] **Step 2: Run tests to verify their state**

Run: `pytest tests/test_lmu_reader.py -v`

Expected: `test_read_returns_none_when_no_session` likely already passes (the early return is in place from Task 3). The exception test should also pass (the try/except wrap is in place). The `is_connected` cache test should pass. If any fail, fix the implementation.

- [ ] **Step 3: Verify the full suite**

Run: `pytest tests/test_lmu_reader.py -v`

Expected: All ~17 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_lmu_reader.py
git commit -m "test(lmu): cover failure modes (no session, exceptions, is_connected cache)"
```

---

## Task 7: ACC-shape conformance test

**Files:**
- Modify: `tests/test_lmu_reader.py`

This is the safety net for blind-build mapping errors. It compares the key set of `LMUReader.read()` against `ACCReader.read()` to catch any field we forgot.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lmu_reader.py`:

```python
def test_lmu_dict_keys_match_acc_dict_keys():
    """LMUReader.read() must return the same key set as ACCReader.read().
    This guarantees existing widgets work unchanged."""
    # Reference key set from ACCReader.read() — extracted from
    # s1napse/readers/acc.py. Update this set if ACCReader's shape changes.
    acc_keys = {
        'speed', 'rpm', 'max_rpm', 'gear', 'throttle', 'brake', 'steer_angle',
        'abs', 'tc', 'fuel', 'max_fuel', 'lap_time', 'position', 'car_name',
        'track_name', 'lap_count', 'current_time', 'lap_dist_pct', 'world_x',
        'world_z', 'lap_valid', 'is_in_pit_lane', 'tyre_temp', 'tyre_pressure',
        'brake_temp', 'tyre_compound', 'air_temp', 'road_temp', 'session_type',
        'gap_ahead', 'gap_behind', 'stint_time_left', 'delta_lap_time',
        'estimated_lap', 'tyre_wear', 'brake_bias',
    }
    reader = _build_reader_with_fakes(_make_fake_telemetry(), _make_fake_scoring())
    data = reader.read()
    lmu_keys = set(data.keys())
    missing = acc_keys - lmu_keys
    extra = lmu_keys - acc_keys
    assert not missing, f"LMU dict missing ACC keys: {missing}"
    assert not extra, f"LMU dict has unexpected keys: {extra}"
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_lmu_reader.py::test_lmu_dict_keys_match_acc_dict_keys -v`

Expected: PASS if Tasks 3-5 covered everything. If FAIL, the assertion message tells you which keys are missing — add them to `read()` (likely with placeholder zero values per the spec's mapping table).

- [ ] **Step 3: Commit**

```bash
git add tests/test_lmu_reader.py
git commit -m "test(lmu): assert LMU dict shape matches ACCReader exactly"
```

---

## Task 8: Register `LMUReader` in the readers package

**Files:**
- Modify: `s1napse/readers/__init__.py`

- [ ] **Step 1: Edit `__init__.py`**

Open `s1napse/readers/__init__.py` and update both the import and `__all__`:

```python
"""Telemetry reader implementations for different data sources."""

from .base import TelemetryReader
from .ac_udp import ACUDPReader
from .acc import ACCReader
from .iracing import IRacingReader
from .lmu import LMUReader
from .elm327 import ELM327Reader

__all__ = [
    'TelemetryReader',
    'ACUDPReader',
    'ACCReader',
    'IRacingReader',
    'LMUReader',
    'ELM327Reader',
]
```

- [ ] **Step 2: Verify the import works**

Run: `python -c "from s1napse.readers import LMUReader; print(LMUReader().available)"`

Expected: prints `False` (on macOS/Linux) plus the install hints, no traceback.

- [ ] **Step 3: Commit**

```bash
git add s1napse/readers/__init__.py
git commit -m "feat(lmu): export LMUReader from readers package"
```

---

## Task 9: Wire `LMUReader` into [app.py](../../../s1napse/app.py)

**Files:**
- Modify: `s1napse/app.py` (5 sites)

This task touches 5 specific lines/blocks. Apply each edit exactly as shown.

- [ ] **Step 1: Edit 1 — import (line 47)**

Find:
```python
from .readers import ACUDPReader, ACCReader, IRacingReader, ELM327Reader
```

Replace with:
```python
from .readers import ACUDPReader, ACCReader, IRacingReader, LMUReader, ELM327Reader
```

- [ ] **Step 2: Edit 2 — construction (line 138 area)**

Find:
```python
        self.acc_reader = ACCReader()
        self.ir_reader  = IRacingReader()
        self.elm_reader = None
```

Replace with:
```python
        self.acc_reader = ACCReader()
        self.ir_reader  = IRacingReader()
        self.lmu_reader = LMUReader()
        self.elm_reader = None
```

- [ ] **Step 3: Edit 3 — game combo box (line 1327)**

Find:
```python
        self.game_combo.addItems(['Auto-Detect', 'ACC', 'AC', 'iRacing'])
```

Replace with:
```python
        self.game_combo.addItems(['Auto-Detect', 'ACC', 'AC', 'iRacing', 'LMU'])
```

- [ ] **Step 4: Edit 4 — `_on_game_changed` dispatch (line 2793 area)**

Find:
```python
        elif game == 'ACC':
            self.current_reader = self.acc_reader
        elif game == 'iRacing':
            self.current_reader = self.ir_reader
        else:  # 'AC'
```

Replace with:
```python
        elif game == 'ACC':
            self.current_reader = self.acc_reader
        elif game == 'iRacing':
            self.current_reader = self.ir_reader
        elif game == 'LMU':
            self.current_reader = self.lmu_reader
        else:  # 'AC'
```

- [ ] **Step 5: Edit 5 — `_detect_game` priority (line 2811 area)**

Find:
```python
        if self.acc_reader.is_connected():
            return self.acc_reader
        if self.ir_reader.is_connected():
            return self.ir_reader
```

Replace with:
```python
        if self.acc_reader.is_connected():
            return self.acc_reader
        if self.ir_reader.is_connected():
            return self.ir_reader
        if self.lmu_reader.is_connected():
            return self.lmu_reader
```

- [ ] **Step 6: Edit 6 — game-type label dispatch (line 3268 area)**

Find:
```python
        if isinstance(self.current_reader, ELM327Reader):
            game_type = 'OBD-II'
        elif isinstance(self.current_reader, ACUDPReader):
            game_type = 'AC'
        elif isinstance(self.current_reader, IRacingReader):
            game_type = 'iRacing'
        else:
            game_type = 'ACC'
```

Replace with:
```python
        if isinstance(self.current_reader, ELM327Reader):
            game_type = 'OBD-II'
        elif isinstance(self.current_reader, ACUDPReader):
            game_type = 'AC'
        elif isinstance(self.current_reader, IRacingReader):
            game_type = 'iRacing'
        elif isinstance(self.current_reader, LMUReader):
            game_type = 'LMU'
        else:
            game_type = 'ACC'
```

- [ ] **Step 7: Smoke-test the app launches**

Run: `python s1napse.py` (or however the app is started — check README if unsure).

Expected: app launches without traceback. `LMU` appears in the game-source dropdown. Selecting it on macOS/Linux shows the disconnected indicator (because `available=False`), but does not crash.

Close the app.

- [ ] **Step 8: Run the full test suite**

Run: `pytest`

Expected: existing tests still pass; LMU tests still pass.

- [ ] **Step 9: Commit**

```bash
git add s1napse/app.py
git commit -m "feat(lmu): wire LMUReader into game selector and auto-detect"
```

---

## Task 10: Setup documentation for the Windows tester

**Files:**
- Create: `docs/lmu-setup.md`

- [ ] **Step 1: Create the setup guide**

Create `docs/lmu-setup.md`:

```markdown
# Le Mans Ultimate Setup

S1napse reads LMU telemetry through the rFactor 2 Shared Memory Plugin.
Studio 397 ships LMU on the rF2 engine, so the same plugin works for both
games.

## 1. Install the plugin

1. Download `rFactor2SharedMemoryMapPlugin64.dll` from the
   [TheIronWolfModding/rF2SharedMemoryMapPlugin releases page](https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin/releases).
2. Copy the DLL into LMU's plugin folder, typically:
   `<Steam>/steamapps/common/Le Mans Ultimate/Plugins/`
3. Open `<Steam>/steamapps/common/Le Mans Ultimate/UserData/player/CustomPluginVariables.JSON`
   in a text editor.
4. Find the `"rFactor2SharedMemoryMapPlugin64.dll"` entry (or add it if
   missing) and ensure it has:
   ```json
   "rFactor2SharedMemoryMapPlugin64.dll": {
       " Enabled": 1
   }
   ```
   **Note the leading space before `Enabled`** — this is required by the
   game and is not a typo.

## 2. Install the Python dependency

```bash
pip install pyRfactor2SharedMemory
```

This package only works on Windows.

## 3. Verify

1. Launch LMU and start a session (Practice is fine).
2. Launch S1napse.
3. In the source dropdown, select `LMU` (or leave on `Auto-Detect`).
4. The connection indicator should turn green and show `CONNECTED · LMU`.

## Known caveats

- **Online races may restrict telemetry.** Some multiplayer modes zero out
  physics fields as an anti-cheat measure. If the indicator says connected
  but speed/RPM are stuck at zero during driving, that is the cause —
  switch to single-player or a non-restricted server to confirm.
- **Plugin install can be silent.** If you copy the DLL but forget the
  `CustomPluginVariables.JSON` step (or miss the leading space in
  `" Enabled"`), the plugin loads but does not publish. S1napse will read
  zeros.
- **Paid DLC content works.** The plugin reads telemetry for whatever car
  and track LMU is currently simulating. It is not a content unlock — you
  still need to own the DLC to drive that car, but if you can drive it,
  S1napse can read it.
```

- [ ] **Step 2: Commit**

```bash
git add docs/lmu-setup.md
git commit -m "docs: LMU setup guide for Windows testers"
```

---

## Task 11: Final verification

**Files:** none (validation only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -v`

Expected: all tests pass.

- [ ] **Step 2: Confirm no straggler imports / typos**

Run: `python -c "import s1napse.app"`

Expected: no traceback. (Confirms all 5 app.py edits at least parse.)

- [ ] **Step 3: Confirm git log is clean and bite-sized**

Run: `git log --oneline feat/lmu-listener ^main`

Expected: ~10 commits matching the task structure (chore: dep, feat: skeleton, feat: physics, feat: wheels, feat: scoring, test: failure modes, test: shape conformance, feat: register, feat: wire, docs: setup).

- [ ] **Step 4: Hand off to Windows tester**

The PR description should reference the Windows verification checklist from the spec ([2026-05-09-lmu-reader-design.md](../specs/2026-05-09-lmu-reader-design.md), "Windows verification checklist" section). Those items are the acceptance criteria the tester ticks off against a live LMU install.

---

## Self-review notes

- **Spec coverage:**
  - Library choice → Task 1
  - Field mapping (physics) → Task 3
  - Field mapping (wheels) → Task 4
  - Field mapping (scoring + session_type + names) → Task 5
  - Lifecycle / `available=False` / `is_connected` cache → Task 2 + Task 6
  - Wiring (5 sites) → Task 9
  - Testing strategy (unit + shape conformance) → Tasks 3–7
  - Setup documentation → Task 10
- **Open questions from the spec** (`steer_angle` units, `gap_ahead`/`gap_behind` derivation, tyre temp source) — left as v1 defaults per the spec; the Windows verification checklist is where the tester resolves them.
- **No placeholders, no "TBD", no "similar to Task N".**
