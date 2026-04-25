# Strategy Tab — Roadmap (v1 → v2 → release)

**Date:** 2026-04-25
**Status:** Living document — update when scope changes
**Companion docs:** [v1 design spec](./2026-04-25-strategy-tab-v1-design.md), [release roadmap](./2026-04-25-s1napse-release-roadmap.md)

This is the per-feature roadmap for the Strategy tab. The whole-app order-of-operations lives in the [release roadmap](./2026-04-25-s1napse-release-roadmap.md); this doc only covers Strategy tab evolution.

## v1 — May 2026 (~3-4 weeks)

Six cards + Race-tab headline banner. See [v1 design spec](./2026-04-25-strategy-tab-v1-design.md) for full detail.

- Tyre-degradation projector (linear regression, 3-5 trailing laps)
- Pit-window estimator (fuel-edge + tyre-edge)
- Fuel-save cost (industry rule of thumb)
- Rival-watch (gap-jump heuristic, "(inferred)" labeled)
- Weather/track-temp watch
- Pit strategy summary (relocated, unchanged)
- Race-tab headline banner with fixed-priority order
- pytest scaffolding for `StrategyEngine`

**Success criteria:** All six cards render in ACC during a 5+ lap stint without errors. Headline banner correctly fires its top-priority active state.

## v2 — July 2026 (~3-4 weeks)

The "real data" upgrade. Replaces the gap-jump heuristic in card #4 with the ACC broadcasting API, and adds the higher-effort cards that v1 deferred.

### v2.1 — ACC broadcasting integration (highest priority)

Wire the ACC broadcasting UDP API as a separate connection alongside `ACCReader`. This unlocks full-field rival data: every car's lap count, position, last lap time, and pit status.

- Pick a wrapper (probable: `accapi` (Apache-2.0, EmperorCookie) or fork it). Verify the data fields it exposes by reading the source.
- Add `s1napse/readers/acc_broadcast.py` as a third reader running in parallel with `ACCReader`. Handles its own UDP socket, handshake, heartbeat, and reconnection.
- Surface rival entries into a new `data['rivals']` list keyed by car number.
- Replace card #4's gap-jump inference with real "rival pitted" events. Drop the "(inferred)" label.
- Document the user-side setup (ACC's `broadcasting.json` configuration) in the README.

**Risk.** Undocumented protocol, unmaintained wrappers. Plan for ~50% schedule buffer.

### v2.2 — What-if pit planner card

A separate card that lets the user simulate pit decisions: "if I pit lap N with compound X, what's my projected finish vs. staying out?" Used between stints or under yellow flag, not during driving.

- Inputs: pit-on-lap dropdown, compound dropdown, target stint length.
- Output: projected finish time vs. baseline, gap to current rivals at finish.
- Reuses `StrategyEngine`'s degradation model and rival data from v2.1.

### v2.3 — Two-phase warmup-then-degradation model

Improves card #1's accuracy by detecting tyre warmup phase (first 1-2 laps) before fitting the linear degradation. Optional: fall back to the v1 single-line fit if the warmup detection is uncertain.

## Release v1.0 — October 2026

Polish and trust-building work to ship the Strategy tab as a release-quality feature.

- **Per-compound learned curves.** Persist degradation slopes per (track, compound) across sessions. After 3+ stints on the same combo, use the historical curve as a prior, with the live regression as a confidence-weighted update.
- **Per-car/track fuel-save calibration.** Replace the 0.7 s/L hardcoded constant in card #3 with per-(car, track) values learned from session history.
- **iRacing parity.** Wire iRacing's full-field API into the rival-watch card so card #4 works on both sims.
- **Telemetry replay support.** When the user opens a saved lap in the replay tab, also reconstruct that lap's `StrategyState` for after-the-fact review.
- **Documentation.** README section explaining each card, the model assumptions, and the broadcasting setup.

## Long-term (post-release, no committed date)

- AC support for rival-watch (no broadcasting API exists; would need a different approach or staying inferred).
- Mobile companion that surfaces the headline banner remotely (paired with the website product).
- Setup-influence card: correlate setup changes with degradation slope changes across sessions.
- Multi-stint planner for endurance racing.

## What this doc is NOT

- Not the spec for any specific version. v1 has its own [design spec](./2026-04-25-strategy-tab-v1-design.md); v2 will get its own when we get there.
- Not the implementation plan. Plans live in `docs/superpowers/plans/`.
- Not committed dates. Dates are estimates that move as work happens. Update them when scope changes.
