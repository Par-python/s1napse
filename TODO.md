# TODO

Backlog of fixes and follow-ups to be addressed later. Add freely; prune when done.

## Deferred from 50 Hz sampling change (2026-04-24)

- Migration script for existing `.json` lap files → `.json.gz` (one-shot tool under `tools/`).
- Profile `_process_sample` under sustained 50 Hz to confirm no CPU regression on slower hardware.
- Decide whether to dedupe consecutive identical Graphics-bound samples (`lap_dist_pct`, `world_x`, `world_z`) when sampler outpaces ACC's ~50 Hz Graphics rate.
- Consider a user-facing telemetry-rate setting (20 / 33 / 50 Hz) if perf becomes hardware-dependent.

## Lap RAM growth (matters at endurance scale, ~40 MB+ per long session)

Today: ~1 MB per lap in Python lists. Trivial per lap, but compounds across long sessions or many loaded sessions. Tackle in priority order — first two give the biggest win per unit of work.

- Switch per-lap channel storage from `list[float]` to NumPy arrays. ~3.5× smaller in RAM (8-byte floats vs ~28-byte boxed PyObjects). Requires pre-allocation or batched extends since arrays don't append cheaply.
- Quantize channels to smaller dtypes: `throttle`/`brake`/`abs`/`tc` → `uint8`, `gear` → `int8`, `rpm` → `uint16`, `speed` → `float16`, `world_x`/`world_z` → `float32`. Combined with NumPy storage this is another ~4–8× per channel. Make sure JSON export still round-trips.
- Run-length encode Graphics-bound channels (`lap_dist_pct`, `world_x`, `world_z`) to drop the duplicate samples produced when the sampler outpaces ACC's Graphics rate. Invasive — every reader needs to know about the index.
- Page completed laps to disk: once a lap is exported to `.json.gz`, drop it from `session_laps[]` and reload on demand when the user opens it. Cleanest scaling story for long sessions; medium refactor for analysis/comparison code paths.
- Ring-buffer the in-memory session history (e.g. last 50 laps resident, older ones disk-only). Cheap if disk paging is in place.
