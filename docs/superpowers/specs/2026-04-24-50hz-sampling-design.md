# 50 Hz telemetry sampling with gzipped lap exports

**Date:** 2026-04-24
**Status:** Approved — ready for implementation plan

## Goal

Increase telemetry data fidelity from ~22 Hz to ~50 Hz (matching ACC's Graphics shared-memory rate) without harming app responsiveness, and switch lap JSON exports/imports to gzip-compressed `.json.gz` files.

## Background

Today the background sampler reads ACC shared memory every 45 ms (~22 Hz) and pushes each read into a buffer. The render timer drains that buffer at 5 Hz and appends every sample to per-lap arrays that get exported to disk on lap completion. ACC's Graphics shared memory updates at ~50 Hz natively, so 22 Hz under-samples it; raising the sampler to ~50 Hz captures all available updates for position/lap-distance/gap fields.

The render/animation loops are already decoupled from the sampler (5 Hz render, 60 Hz animation), so raising the sample rate does not directly change UI cost.

## Non-goals

- No architectural refactor — the sampler/render/animation split is correct as-is.
- No batched per-sample processing — premature for the volume involved.
- No drop-oldest guardrail in the buffer — would silently lose data, contradicts the goal.
- No backward-compat shim for existing `.json` lap files — clean break to `.json.gz` (per user direction).
- No changes to AC UDP, iRacing, or ELM327 readers — they have their own native rates.
- No changes to track JSON files (`tracks-db/*.json`) — different format, different lifecycle.

## Design

### 1. Sampler rate (~22 Hz → ~50 Hz)

[`s1napse/app.py:83`](../../../s1napse/app.py#L83): `time.sleep(0.045)` → `time.sleep(0.020)`.

Update the docstring at [`s1napse/app.py:58`](../../../s1napse/app.py#L58) and the inline comment at [`s1napse/app.py:183`](../../../s1napse/app.py#L183) from "~22 Hz" to "~50 Hz".

That single sleep change is the entire perf-side modification. The buffer/drain machinery is unchanged.

### 2. Lap export → `.json.gz`

Three export sites in [`s1napse/app.py`](../../../s1napse/app.py):

- Line 2393–2408 — lap export
- Line 2542–2550 — full lap export (the `*-full.json` form)
- Line 2592–2607 — additional lap export site

For each site:

- Change the default filename suffix from `.json` to `.json.gz`.
- Replace `open(path, 'w')` + `json.dump(payload, f)` with `gzip.open(path, 'wt', encoding='utf-8')` + `json.dump(payload, f)`.
- Pass `compresslevel=6` to `gzip.open(...)` for a good size/speed balance (the library default is 9, which is slower for marginal size gains).
- Update the file-picker filter (if any) from `*.json` to `*.json.gz`.

Add `import gzip` at the top of [`s1napse/app.py`](../../../s1napse/app.py).

### 3. Lap import → read `.json.gz`

Two import sites:

- Line 2619 — `payload = json.load(f)` (lap re-load)
- Line 3196 — `payload = json.load(f)` (replay tab import)

For each site:

- Replace `open(path, 'r')` + `json.load(f)` with `gzip.open(path, 'rt', encoding='utf-8')` + `json.load(f)`.
- Update the file-picker filter from `*.json` to `*.json.gz`.

Per user direction, no backward-compat for old `.json` files. Existing plain-JSON lap files on disk will not load after this change; user accepts this.

The track-data load at [`s1napse/app.py:4212`](../../../s1napse/app.py#L4212) is unaffected — that's `tracks-db/*.json`, a different file type.

## Verification

Manual smoke test (the user runs ACC; we cannot run it from CI):

1. Start the app, run a single lap in ACC.
2. Confirm the saved file is `*.json.gz` and the lap re-loads in the replay tab.
3. Eyeball CPU usage during a live lap — should be in the same ballpark as before the change.
4. Open the saved file and confirm `len(payload['data']['speed'])` is roughly 2× what a comparable old lap had at 22 Hz.

## Risk

- **Duplicate samples for Graphics-bound fields.** ACC's Graphics shared memory updates at ~50 Hz; sampling at ~50 Hz means consecutive reads may return identical `lap_dist_pct` / `world_x` / `world_z` if the sampler runs slightly faster than the source. Not harmful — they are just repeated values in the array — but worth being aware of when reading lap files.
- **Lap memory growth ~2.3×.** A 90 s lap goes from ~2,000 samples/channel to ~4,500. With ~30 channels and 8-byte floats, that is ~1 MB per lap in RAM. Trivial.
- **Gzip load CPU cost.** A typical lap takes ~10–50 ms extra to decompress on import. Imperceptible during replay-open.

## Deferred work (out of scope for this change)

These were considered and explicitly deferred:

- **Migration tool for existing `.json` lap files** — user accepted clean break; can be added later if needed (a `tools/gzip_old_laps.py` script).
- **Batched per-sample processing** — pre-allocated arrays, chunked appends. Not justified at 50 Hz; revisit only if profiling shows `_process_sample` as a bottleneck.
- **Drop-oldest buffer guardrail** — would bound worst-case latency at the cost of dropping real telemetry. Add only if the render loop is observed falling behind in practice.
- **Higher rates (e.g. 100 Hz, split-rate per channel)** — would require dedup or multi-stream architecture. Revisit if 50 Hz proves insufficient.
- **Telemetry-rate setting in the UI** — let the user pick 20/33/50 Hz. Not needed now; can be added if multiple users hit different perf ceilings.
