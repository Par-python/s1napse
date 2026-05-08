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

The accuracy + planner upgrade. Adds the higher-effort cards that v1 deferred.

**Removed from scope (formerly v2.1): ACC broadcasting integration.** The v1 gap-jump heuristic for rival-watch stands permanently — card #4 keeps its "(inferred)" label. Rationale: undocumented protocol, unmaintained wrappers, and the live-coaching relay (post-v1.0 candidate, see release roadmap) covers most of the value broadcasting would have unlocked since a coach can read full-field data from their own ACC client. See release roadmap risk section history for the full reasoning.

### v2.1 — What-if pit planner card

A separate card that lets the user simulate pit decisions: "if I pit lap N with compound X, what's my projected finish vs. staying out?" Used between stints or under yellow flag, not during driving.

- Inputs: pit-on-lap dropdown, compound dropdown, target stint length.
- Output: projected finish time vs. baseline, projected gap to the car ahead/behind at finish (using the v1 gap-jump heuristic + own-car pace projection — no full-field data).
- Reuses `StrategyEngine`'s degradation model.

### v2.2 — Two-phase warmup-then-degradation model

Improves card #1's accuracy by detecting tyre warmup phase (first 1-2 laps) before fitting the linear degradation. Optional: fall back to the v1 single-line fit if the warmup detection is uncertain.

## Release v1.0 — October 2026

Polish and trust-building work to ship the Strategy tab as a release-quality feature.

- **Per-compound learned curves.** Persist degradation slopes per (track, compound) across sessions. After 3+ stints on the same combo, use the historical curve as a prior, with the live regression as a confidence-weighted update.
- **Per-car/track fuel-save calibration.** Replace the 0.7 s/L hardcoded constant in card #3 with per-(car, track) values learned from session history.
- **Telemetry replay support.** When the user opens a saved lap in the replay tab, also reconstruct that lap's `StrategyState` for after-the-fact review.
- **Documentation.** README section explaining each card and the model assumptions.

## Long-term (post-release, no committed date)

- Mobile companion that surfaces the headline banner remotely (paired with the website product).
- Setup-influence card: correlate setup changes with degradation slope changes across sessions.
- Multi-stint planner for endurance racing.

## What this doc is NOT

- Not the spec for any specific version. v1 has its own [design spec](./2026-04-25-strategy-tab-v1-design.md); v2 will get its own when we get there.
- Not the implementation plan. Plans live in `docs/superpowers/plans/`.
- Not committed dates. Dates are estimates that move as work happens. Update them when scope changes.
