# Strategy Tab v1 — Design

**Date:** 2026-04-25
**Status:** Approved — ready for implementation plan
**Companion docs:** [Strategy tab roadmap](./2026-04-25-strategy-tab-roadmap.md), [S1napse release roadmap](./2026-04-25-s1napse-release-roadmap.md), [Market validation](./2026-04-25-market-validation.md)

## Goal

Add a new **Strategy** tab that surfaces six live race-strategy cards driven by a shared `StrategyEngine`, plus a one-line strategy headline banner on the Race tab. Move the existing fuel-save calculator, undercut/overcut, and pit-strategy cards from Race → Strategy. ACC broadcasting integration is out of scope (see roadmap for v2).

The Strategy tab is intended as the project's strongest live-experience differentiator against web-first competitors (per the market validation).

## Non-goals

- ACC broadcasting integration (full-field rival data) — deferred to v2.
- A what-if pit-stop planner (use-case is between stints, not during them).
- Per-compound learned degradation curves.
- Two-phase warmup-then-degradation model.
- Automatic compound recommendations from weather/track-temp data.
- AI-anything. Honest, transparent calculations only.

## Architecture

A new `StrategyEngine` class lives in `s1napse/coaching/strategy_engine.py`. It holds per-stint state and is updated once per processed sample inside `_process_sample()` — so its `update()` runs at the sampler rate (~50 Hz worth of samples, drained in batches at the 5 Hz render tick). The engine has no Qt dependency — it produces a `StrategyState` dataclass that the UI reads.

Two consumers of `StrategyState`:

1. The **Strategy tab** widgets (six cards, each one method on a new `StrategyTab` widget class).
2. The **Race tab's headline banner** (one label that reads `state.headline()` per render tick).

This split mirrors how `LapCoach` and `MathEngine` are organized today — pure logic in `coaching/`, UI in `widgets/`. Keeps the strategy logic testable in isolation.

### File structure

- `s1napse/coaching/strategy_engine.py` — **new** — `StrategyEngine` class, `StrategyState` dataclass, `Headline` dataclass.
- `s1napse/widgets/strategy_tab.py` — **new** — `StrategyTab` widget hosting all six cards.
- `s1napse/widgets/__init__.py` — **modified** — export `StrategyTab`.
- `s1napse/app.py` — **modified** — register the new tab, wire `StrategyEngine` into `_process_sample`, move three existing cards out of Race tab, add the headline banner widget.
- `tests/__init__.py` + `tests/test_strategy_engine.py` — **new** — first pytest module in the project.
- `pyproject.toml` or `pytest.ini` — **new** — pytest config (root layout).

## Data flow

```
sampler thread (50 Hz)
   → buffer (drained at 5 Hz)
   → _process_sample(s)
       → existing per-lap data appends
       → StrategyEngine.update(s, current_lap_data, session_laps)
           → recompute StrategyState (cheap, idempotent)

render tick (5 Hz)
   → if Strategy tab visible: redraw all six cards from StrategyState
   → Race tab banner: always set text from StrategyState.headline()
```

The engine's `update()` call is cheap (linear regression over ≤5 lap times, two gap-delta comparisons, a handful of arithmetic ops). Recomputing on every sample (~10 samples per render tick at 50 Hz) is fine.

The Strategy tab guards redraws behind `isVisible()` — when the user is on a different tab, only the engine ticks (which it must, to detect events live).

## Components

### Card 1 — Tyre-degradation projector

**What it shows.** Three large numbers and a small line chart:
- **Pace baseline** — average of laps 2-3 of the current stint (s).
- **Degradation** — slope of the linear fit (s/lap of slowdown per lap).
- **Projected end-of-stint pace** — baseline + (degradation × laps_remaining_in_stint).

A 100 px tall line chart shows recorded lap times for the current stint and the linear projection extending forward to the end of the planned stint.

**Model.** Linear regression (`numpy.polyfit(degree=1)`) over the trailing 3-5 lap times on the current stint. Reset on pit exit (tyre stint reset). Show R² as a "fit confidence" pip (●●● strong / ●●○ ok / ●○○ weak).

**Visibility.** Hidden behind a "Need 3 laps to project" placeholder until lap 3 of the current stint.

### Card 2 — Pit-window estimator

**What it shows.** Two lap numbers and a horizontal bar:
- **Window opens** — earliest pit lap. Driven by fuel: the lap by which staying out one more lap would not leave enough fuel to finish.
- **Window closes** — latest pit lap. Driven by tyres: the lap at which projected lap-time loss exceeds 1.5 s/lap above baseline (using Card 1's degradation slope).

A horizontal bar (current_lap / closes_lap) shows where you are inside the window. Color is amber inside the window, red after it closes, neutral before it opens.

**Edge case — no lap finished yet.** Show "Complete a lap to estimate." If only fuel data is available (degradation not yet projecting), show only the open-edge.

### Card 3 — Fuel-save cost

**What it shows.** Reads the existing `_fs_laps_spin` value from the relocated fuel-save calculator. When user enters "save 0.5 L/lap," shows:
- **Estimated time cost: ~0.35 s/lap.**
- A small caption: *"Approximation: ~0.7 s/lap per L/lap saved (industry rule of thumb). Real cost varies by car/track."*

**Model.** `time_cost_s_per_lap = liters_saved_per_lap × 0.7`. Hard-coded constant in v1. v2 may learn per-car or per-track from session history.

### Card 4 — Rival-watch (gap-jump heuristic, "(inferred)" labeled)

**What it shows.** Two rows — one for the car ahead, one for the car behind. Each row shows the current gap and a status:
- **Stable** (default) — gap is steady or drifting normally.
- **PITTED LIKELY** (amber, with timestamp) — gap jumped by ≥ pit_loss × 0.7 (default 15 s) within one lap.
- **In undercut/overcut range** (green) — after a rival pit, calculate whether their out-lap pace + your remaining stint puts you in position.

A subtitle reads *"Inferred from gap delta. May fire on rival crash/spin. ACC broadcasting integration in v2 will use real data."*

**Model.**
- Buffer last ~30 s of `gap_ahead` and `gap_behind` (one value per render tick = ~150 samples).
- Compute one-second median to filter sampler jitter.
- If `current_gap - smoothed_gap_5s_ago > pit_loss × 0.7`, fire the alert and start a 60 s suppression window so it doesn't re-fire.

### Card 5 — Weather/track-temp watch

**What it shows.** A 200×80 px chart plotting `air_temp` and `road_temp` over the entire session. Below the chart, a one-line note:
- *"Track stable at 28°C."* (default, if delta-from-stint-start ≤ 5°C)
- *"Track cooling 6°C since stint start — expect more tyre life."*
- *"Track heating 7°C since stint start — expect more degradation."*

No automatic compound recommendation in v1; that needs per-compound knowledge we don't have.

### Card 6 — Pit strategy summary (relocated from Race tab)

The existing Pit Strategy card from [`s1napse/app.py:3722`](../../../s1napse/app.py#L3722) — fuel laps left, tyre stint, tyre condition, recommendation text — moved as-is, no logic change. It's already strategy material; the move is just deduplication.

### Plus relocated, unchanged

- **Fuel-save calculator** (currently at [`app.py:3786`](../../../s1napse/app.py#L3786)) — moved to Strategy tab.
- **Undercut/overcut** card (currently at [`app.py:3813`](../../../s1napse/app.py#L3813)) — moved to Strategy tab.

The Race tab keeps everything else (position, gap, tyres, timing, lap-time trend) — it remains the "what's happening now" view.

## Headline banner (Race tab)

A 40 px tall label inserted at the top of the Race tab (above the existing session banner), reading `StrategyState.headline().text`. Color matches `headline().severity`.

**Fixed priority order** (first active wins):

| Priority | Card | Trigger | Banner text | Severity |
|---|---|---|---|---|
| 1 | #4 Rival-watch | Rival pit detected within last 30 s | `UNDERCUT NOW · CAR AHEAD PITTED` | red |
| 2 | #2 Pit-window | Inside open window | `PIT WINDOW OPEN · CLOSES LAP {Y}` | red |
| 3 | #6 Pit strategy | Fuel laps left ≤ 2 | `FUEL: SAVE {x} L/LAP TO FINISH` | red |
| 4 | #1 Degradation | Projected ≥ 1.5 s/lap loss within next 2 laps | `TYRES: {N} LAPS TO {x} s/LAP DROP` | amber |
| 5 | (default) | Nothing else firing | `STRATEGY: STABLE` | neutral |

The banner is clickable and switches the active tab to Strategy.

## Error handling

- The engine never raises. Missing inputs (e.g. no completed lap yet) produce a "stable" state with appropriate placeholder text.
- Each card guards against its own missing inputs and shows "—" plus a one-line "needs N more laps" hint.
- The headline banner falls back to "STRATEGY: STABLE" if anything upstream is unavailable.

## Testing

This adds the first non-trivial pure-logic module to the project. Worth introducing pytest scaffolding for it — the existing repo has none.

**`tests/test_strategy_engine.py`** covers:

- Linear-fit degradation on a known lap-time series (assert slope within tolerance, R² > 0.9 on synthetic clean data).
- Pit-window edges: fuel-driven open edge correct, tyre-driven close edge correct, edge case where they cross (window already closed).
- Rival-watch: gap-jump above threshold fires alert; gap-jump below threshold does not fire; fired alert suppresses re-fire for 60 s.
- Headline-priority ordering: when multiple categories are active, the highest-priority text is returned.
- StrategyState always non-throwing for empty / minimal inputs.

UI cards are tested manually in ACC (no PyQt6 in CI; matches existing repo norms).

## Risks

- **Card 4 false positives.** Gap-jump heuristic will fire on rival crashes/spins. Mitigated by the "(inferred)" label and the v2 broadcasting plan; not eliminated.
- **Card 1 fit instability.** Three lap times is the minimum — the linear fit will be noisy. R² indicator helps the user judge confidence; the projected number is shown but not styled as authoritative.
- **Card 3 industry rule of thumb (0.7 s/lap per L).** Wrong for some car/track combos. Mitigated by the explicit caption that flags the approximation.
- **Tab proliferation.** Adding a 10th tab (Strategy makes it 10) starts to crowd the tab bar. v1 acceptable; if it grows further, consider a left-rail nav as a v2 task.

## Verification

Manual smoke test (the user runs ACC):

1. Start the app, run a 5+ lap stint in ACC.
2. Confirm Strategy tab appears, all six cards render without errors.
3. Card 1 — confirm fit appears at lap 3, slope is plausible (positive small number for slow degradation).
4. Card 2 — confirm window numbers are sensible given remaining fuel/tyre state.
5. Card 4 — manually pit during a session, observe gap-jump on the next lap, confirm the alert fires for the car behind.
6. Race tab banner — confirm it changes color and text as conditions evolve; click jumps to Strategy tab.
7. Confirm relocated cards (fuel-save, undercut/overcut, pit-strategy) work identically to before, just on the new tab.

## Out of scope (v2+, captured in roadmap)

See [Strategy tab roadmap](./2026-04-25-strategy-tab-roadmap.md) for the full v2 / release breakdown.
