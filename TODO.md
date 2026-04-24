# TODO

Backlog of fixes and follow-ups to be addressed later. Add freely; prune when done.

## Deferred from 50 Hz sampling change (2026-04-24)

- Migration script for existing `.json` lap files → `.json.gz` (one-shot tool under `tools/`).
- Profile `_process_sample` under sustained 50 Hz to confirm no CPU regression on slower hardware.
- Decide whether to dedupe consecutive identical Graphics-bound samples (`lap_dist_pct`, `world_x`, `world_z`) when sampler outpaces ACC's ~50 Hz Graphics rate.
- Consider a user-facing telemetry-rate setting (20 / 33 / 50 Hz) if perf becomes hardware-dependent.
