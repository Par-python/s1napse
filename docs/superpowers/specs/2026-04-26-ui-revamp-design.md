# S1napse — UI revamp design

**Date:** 2026-04-26
**Target:** 48-hour sprint, all 10 tabs reskinned + relayouted
**Status:** Direction validated in brainstorm, spec pending user review before implementation plan
**Companion docs:** [Release roadmap](./2026-04-25-s1napse-release-roadmap.md)

## Goal

Replace the current UI — described by the user as "AI slop" — with a clean, dense-where-it-counts, roomy-where-it-helps look that reads as a deliberately designed product, not a stack of QtWidgets with a dark stylesheet over them.

The whole desktop app must look meaningfully better at the end of the sprint. Strategy v2 work continues after this lands.

## Non-goals

- No new features. No data sources. No business logic changes.
- No light theme this sprint (dark only, redone properly — light is a future swap thanks to tokens).
- No information-architecture changes (10 tabs stay 10 tabs).
- No changes to data-channel colors (`C_SPEED`, `C_THROTTLE`, etc. — those stay; they belong to graphs, not chrome).
- Coach tab logic untouched. Strategy tab logic untouched (it just shipped).

## Visual direction

**Influence mix:** Linear-polish + Bloomberg-legibility. Linear's restraint and refinement on chrome (typography, spacing, borders, accent discipline). Bloomberg's density and respect-the-reader posture on data layout (tabular figures, no chartjunk, every pixel justifies itself).

**Tone:** "Software product that takes itself seriously," not "racing tool from 2014."

## Design tokens

### Surface scale

Replaces the muddled `#0b/#11/#18/#22` set. Each step has a purpose:

| Token | Hex | Use |
|---|---|---|
| `bg` | `#0A0B0D` | App canvas, title bar, tab bar |
| `surface` | `#0E0F12` | Default card background |
| `surface_raised` | `#14161A` | Inputs, nested cards (e.g. tyre quad inside a card) |
| `surface_hover` | `#1C1F25` | Hover state |
| `border_subtle` | `#1A1D23` | Default card border, tab bar bottom |
| `border_strong` | `#262A31` | Inputs, dividers that need to be seen |

### Text scale

| Token | Hex | Use |
|---|---|---|
| `text_primary` | `#F2F3F5` | Numbers, headings, focused values |
| `text_secondary` | `#C2C7D0` | Body text |
| `text_muted` | `#8B94A3` | Labels, sub-text |
| `text_faint` | `#5A626F` | Axis ticks, disabled |

### Accent — violet

`#8B5CF6` is the only saturated color in the chrome. Used for: active tab underline, focus ring, primary buttons, "self/focus" indicators (the user's own car/lap), brand dot. Never for data channels.

### State colors

| Token | Hex | Meaning |
|---|---|---|
| `good` | `#22C55E` | Improving, valid, live, OK |
| `warn` | `#F59E0B` | Caution, fuel-short, getting hot |
| `bad`  | `#EF4444` | Degrading, invalid, critical |
| `info` | `#22D3EE` | Cold (e.g. cold tyres) — reuses Speed channel cyan |

Color is **state only**, never decoration.

### Spacing scale

`4 / 8 / 12 / 16 / 20 / 24` px. Anything that wants a different number is wrong.

### Radius scale

`4` (pills, small), `6` (nested cards, inputs), `8` (default card), `10` (window, big container).

### Typography

- **UI font:** Inter, fallback `system-ui, -apple-system, sans-serif`.
- **Mono font:** JetBrains Mono, fallback `ui-monospace, Consolas, monospace`.
- All numbers use the mono font with `font-feature-settings: 'tnum'` (tabular figures — digits don't jitter as values change).

| Style | Size | Weight | Letter-spacing | Use |
|---|---|---|---|---|
| `display` | 22-26 | 600 | -0.01em | Page-defining numbers (race position, last lap) |
| `numeric_lg` | 17-22 mono | 500 | -0.005em | Card headline numbers |
| `numeric_md` | 13 mono | 400 | 0 | Inline values, mini-rows |
| `heading` | 14 | 600 | 0 | Card heading when needed |
| `body` | 12 | 400 | 0 | Prose, descriptions |
| `label` | 10 | 500 | +0.6em | UPPERCASE LABELS |

Density bucket adjusts the `body` size (11 dense / 12 roomy) and card padding (12 dense / 16 roomy). All other tokens stay the same.

## Architecture

The 4,879-line `app.py` is the structural reason every tab feels like AI slop today: every screen is built imperatively in one file with no shared vocabulary. Fixing the look requires fixing the structure. New layout:

```
s1napse/
  theme.py                    # NEW — tokens + QSS builder
  constants.py                # KEEP — channel colors, track constants only
  app.py                      # SHRINKS — orchestration only (~1500 lines target)
  widgets/
    primitives.py             # NEW — Card, CardHeader, Stat, Pill, Sparkline, GapBar
    title_bar.py              # NEW — always-visible top strip
    tabs/                     # NEW package — one file per tab
      __init__.py
      dashboard.py
      telemetry.py
      lap_analysis.py
      race.py
      strategy.py             # already exists, moves here
      tyres.py
      comparison.py
      session.py
      replay.py
      coach.py                # already exists, moves here
    # existing widget files (graphs.py, gauges.py, track_map.py, etc.) stay
    # — they're inner-widgets, not tabs.
```

### What `theme.py` exports

- All token constants above.
- `build_app_qss()` — returns the full QSS string. Replaces `APP_STYLE` in `constants.py`. Imports tokens, composes by tag (QMainWindow, QTabBar, QPushButton, ...).
- A small `density(card_padding=…, base_size=…)` helper used by primitives.

### Primitives (`widgets/primitives.py`)

| Primitive | Job | Props |
|---|---|---|
| `Card` | Bordered container, default surface, optional warn/bad variant | `title`, `pill`, `variant=normal/warn/bad`, `dense=True/False`, `padding` |
| `CardHeader` | Internal — label + optional pill | used by `Card` |
| `Stat` | Label + big number + optional sub-text + optional delta | `label`, `value`, `unit`, `sub`, `delta`, `delta_state` |
| `Pill` | Status pill (top-right of cards, also used inline) | `text`, `tone=neutral/violet/good/warn/bad` |
| `Sparkline` | Minimal trend line, supports a reference line (e.g. PB) | `points`, `ref_value`, `accent=violet/good/bad` |
| `GapBar` | The ±3s rival visualizer from the Race tab | `gap_ahead`, `gap_behind`, `range_s` |

Each primitive: ~30-80 lines, paints itself with `QPainter`, takes only the props it needs, no imports from `app.py`.

### Title bar (`widgets/title_bar.py`)

Single row, never moves. Contents:
- Brand: violet dot (pulsing when live) + "S1NAPSE" wordmark.
- Source pill: `<live-dot> ACC · MONZA · 28°C / 34°C` — shows live data source + track + air/road temp. Hidden when no source.
- Right block: `Lap 8 / —` · `Stint 2` · `1:29.871` (last lap time, monospace, tabular).

### Tab bar restyle

- Flat, no chrome below.
- Lowercase-but-uppercase-label tabs (`Dashboard`, not `DASHBOARD`).
- Violet underline on active tab.
- Green dot indicator on tabs with active live alerts (Race when banner is firing, Strategy when any card is in alert state).

## Tab work — density buckets

### Dense bucket (live tabs, glance-while-driving)

Single-screen at 1640×980, no scroll. 11px Inter base, 12px card padding, 8px gaps.

| Tab | Layout work |
|---|---|
| **Race** | 3-column: pace / position / car. Headline strip with P-position display + inline strategy banner. Inline visualizers (sparkline, gap-bar, pit-window strip). *(Mockup approved.)* |
| **Strategy** | Reskin only — card-grid pattern already aligns. |
| **Tyres** | Dense quad (FL/FR/RL/RR) primary card, with surrounding cards for pressure, wear, IMO temp distribution. |
| **Coach** | Live tip cards at top, history feed below. |
| **Dashboard** | Selective gauges (rev/pedals/steering — these are visual by nature) + summary card grid for non-visual values. Today it's a wall of gauges; we keep what gauges express well, replace the rest with cards. |

### Roomy bucket (analysis tabs, you-read-for-minutes)

Scrolling allowed where it earns more chart real estate. 12px Inter base, 16-18px card padding, 12px gaps.

| Tab | Layout work |
|---|---|
| **Telemetry Graphs** | Channel toggles become a pill row at top. Charts use a rewritten `_style_ax` that respects theme (no Matplotlib defaults). |
| **Lap Analysis** | Sector panel + scrub + multi-channel graph each get their own row instead of fighting for space. |
| **Lap Comparison** | Lap-A / lap-B panel pair as equal-weight columns; full-width delta chart below. |
| **Session** | Laps table with proper tabular figures, sticky header, per-lap mini-sparklines. |
| **Replay** | Scrub + playback controls consolidate into a single bottom strip; graphs above. |

## Color discipline rules

Apply everywhere:

1. **Accent (violet) = self / focus.** The user's lap line, the user's position marker on the gap bar, the active tab.
2. **Green = improving.** Lap getting faster, gap closing, tyre cooling toward ideal.
3. **Red = degrading.** Lap getting slower, gap opening, tyre overheating.
4. **Amber = warning, not yet failing.** Fuel short, pit window opening, weather changing.
5. **Channel colors stay channel colors.** Speed cyan, throttle green, brake red — these only appear inside graphs, never on chrome.
6. **No decorative color.** If a color is on the screen, it's communicating state.

## Execution order (informs implementation plan)

Phased so each batch is independently shippable. If the 48-hour budget runs out, the cut line lands cleanly between batches:

**Batch 1 — Foundation (~4-6h)**
- `theme.py` with all tokens + QSS builder.
- `widgets/primitives.py` with all six primitives.
- `widgets/title_bar.py`.
- Tab bar restyle.
- Existing app boots, every tab inherits new tokens automatically.

**Batch 2 — Race tab (~4-6h)**
- Apply approved Race-tab v1 design. Validates primitives under live density.

**Batch 3 — Dense bucket (~10-14h)**
- Tyres, Coach, Dashboard relayouted.
- Strategy reskin (no layout work).

**Batch 4 — Roomy bucket (~12-16h)**
- Telemetry, Lap Analysis, Lap Comparison, Session, Replay relayouted.
- Matplotlib `_style_ax` rewrite — themed charts.

**`app.py` slimming** happens incrementally as each tab moves into `widgets/tabs/`. Not a separate batch.

## Risks

1. **Qt QSS limitations.** Qt stylesheets are not CSS — some properties don't exist (no flexbox, limited gradients on some widgets). If a primitive needs a paint workaround, the primitive owns it; the rest of the app stays declarative.
2. **Matplotlib charts looking off.** Themed charts via `_style_ax` is the easy part; getting tick fonts, grid colors, and figure-background to match the Qt theme without flicker is fiddly. Allocate buffer in batch 4.
3. **`app.py` refactor regressions.** Moving 5,000 lines of tab construction into separate files is the largest risk. Mitigation: move tab-by-tab, keep the existing render-tick wiring intact, verify each tab still updates after extraction.
4. **48-hour budget.** Honest read: ~30-42 hours of focused work. If under-running, ship batch 4 in waves. If over-running, ship through batch 3 and the remainder lands as a follow-up — every tab will at least have the new tokens by end of batch 1.

## Acceptance criteria

- App launches with the new title bar, tab bar, and at least batch 1 + batch 2 visibly applied.
- Race tab matches the approved mockup at production parity (real data, not placeholders).
- No regression in: data flow, render tick timing, reader switching, lap recording, replay scrubbing, math channels, coaching tips, strategy banner.
- `app.py` is meaningfully smaller (target ≤ 2000 lines).
- All cards in the app use the same `Card` primitive — no bespoke card paint code outside `primitives.py`.
- All numeric displays use the mono font with tabular figures.

## What this doc is NOT

- Not the implementation plan (that's the next doc, written via writing-plans skill).
- Not a marketing brief.
- Not a final pixel-spec — primitives are the spec.
