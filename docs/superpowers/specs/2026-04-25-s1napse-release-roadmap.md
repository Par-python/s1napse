# S1napse — Release Roadmap

**Date:** 2026-04-25
**Target release:** late October 2026 (~6 months)
**Status:** Living document — update when scope changes
**Companion docs:** [Strategy tab roadmap](./2026-04-25-strategy-tab-roadmap.md), [Monetization strategy](./2026-04-24-monetization-strategy.md), [Market validation](./2026-04-25-market-validation.md), [TODO.md](../../../TODO.md)

This is the order of operations from "now" to "S1napse v1.0 release-ready." If you're trying to remember what's next or in what order, start here.

## Guiding principles

- **The desktop app is and stays free.** No Pro tier, no caps. ([Monetization decision](./2026-04-24-monetization-strategy.md).) The paid product is the future companion website.
- **Live in-session experience is the moat.** Web-first competitors (RaceData AI) can't match a tight desktop HUD. Every feature should ask "does this make the live experience tighter?"
- **No-AI honest-tool positioning.** Calculations are transparent and labeled, not black-box. RaceData AI leads with AI; we differentiate by being the trustworthy alternative.
- **Shipping cadence matters.** RaceData AI ships monthly with a 7-person team. We can't out-feature them; we can be more focused and ship credibly. Don't let perfect be the enemy of shipped.

## Current state (as of 2026-04-25)

- Telemetry sampling at 50 Hz, lap exports gzipped (`.json.gz`). Done.
- Race tab exists with position, gap, tyres, fuel-save calculator, undercut/overcut, pit-strategy, lap-trend.
- Replay tab and lap-comparison tab functional.
- Coaching tab and math channels functional.
- Track recorder builds track maps from live laps.
- TODO.md tracks deferred work: lap-RAM optimizations, telemetry-rate setting, dedup of repeated samples.
- No website yet. No release infrastructure yet (no code signing, no installer, no auto-update).

## Phases

### Phase 1 — Strategy tab v1 (May 2026, ~3-4 weeks)

The next big chunk. See [Strategy tab v1 design](./2026-04-25-strategy-tab-v1-design.md) for full detail.

- Six cards on a new Strategy tab + Race-tab headline banner.
- First pytest scaffolding in the repo (for `StrategyEngine`).
- ACC broadcasting NOT yet integrated; rival-watch uses a "(inferred)" gap-jump heuristic.

**Exit criteria:** Strategy tab ships, runs cleanly through a 5+ lap stint in ACC, headline banner correctly fires.

### Phase 2 — Strategy tab v2 (June-July 2026, ~3-4 weeks)

The "real data" upgrade. See [Strategy tab roadmap v2](./2026-04-25-strategy-tab-roadmap.md#v2--july-2026-3-4-weeks).

- Wire ACC broadcasting API as a third reader. Drop the "(inferred)" label on rival-watch.
- Add what-if pit planner card.
- Two-phase warmup-then-degradation model in card #1.

**Risk.** Broadcasting protocol is undocumented. Plan ~50% schedule buffer.

### Phase 3 — Companion website MVP (July-August 2026, ~4-5 weeks)

The paid product begins. Goal: a credible v0 launch, not a polished v1.

- User accounts, lap upload from desktop app (`.json.gz` is already the upload payload — it's stable, see [monetization decision](./2026-04-24-monetization-strategy.md)).
- Lap history view (date, track, car, time, sectors).
- Personal best tracking per (track, car).
- Public leaderboards per (track, car). Default visibility public; user can opt out per session. (Per market validation: Garage 61's "private laps" friction is a known complaint.)
- Lap-comparison view (your lap vs. another user's, similar to the in-app comparison tab).
- Pricing: $3-5/mo or ~$30/yr range, free tier with no caps on lap count (differentiate from RaceData AI's 30-stints free tier which "feels like a demo").
- Stripe / payment provider integration.

**Exit criteria:** A signed-up user can upload a lap, see it in their history, view a leaderboard, and compare against another user. Payment processing works end-to-end.

**Decisions to make at the start of this phase:**
- Hosting (Vercel + Supabase? Fly.io + Postgres? Self-hosted?).
- Web framework (Next.js? SvelteKit?).
- Free-tier scope (unlimited uploads but visualizations gated? All free with paid for advanced analytics?).

### Phase 4 — Pre-release polish (September 2026, ~3-4 weeks)

Everything between "feature-complete" and "I'd be happy if a stranger downloaded this."

- **Lap-RAM optimizations from [TODO.md](../../../TODO.md):** NumPy-backed channel storage + dtype quantization. Matters because endurance sessions chew RAM fast at 50 Hz.
- **Telemetry-rate user setting** (20 / 33 / 50 Hz) for users on slower hardware.
- **Migration script** for any pre-`.json.gz` lap files users still have.
- **First-run onboarding flow** — connection guide, ACC setup walkthrough, link to website signup.
- **Bug-bash week** — invite ~10 users from r/ACCompetizione to try a release candidate. Fix what they hit.
- **Crash reporting / opt-in telemetry** (the meta-kind, not the racing kind). Sentry or similar.

### Phase 5 — Release infrastructure (October 2026, ~2-3 weeks)

The boring stuff that has to happen before a public launch.

- **Code signing.** Per the monetization decision this is a nice-to-have, not a launch blocker — but downloading an unsigned `.exe` is friction that hurts adoption. Get it done before the public launch.
- **Auto-updater** — sparkle/squirrel-style. Without this, every bug fix requires users to manually re-download.
- **Installer + uninstaller** (currently the app is a single `.exe`).
- **GitHub release workflow** — automate the build, sign, package, and upload steps.
- **README rewrite** for the public audience (current README is dev-facing).
- **Privacy policy + ToS** (required for the website regardless; needed for the app if it ships any opt-in telemetry).

### Phase 6 — Launch (late October 2026)

- Soft launch on r/ACCompetizione, r/iRacing, r/simracing. Direct download + website signup.
- Discord server for early adopters / bug reports.
- Post-launch: monitor, fix, iterate. Strategy tab v2 work continues if not yet done.

## What's NOT in scope for v1.0 release

These are real opportunities the [market validation](./2026-04-25-market-validation.md) flagged but they don't fit in the 6-month window. Captured for v1.1+ planning:

- **Mobile companion app** (real-car telemetry positioning needs this; track-day drivers want their phone in the car, not a Windows laptop).
- **iRacing-specific deep features** (BoP changes, full-field rival data via iRacing API beyond what's needed for parity with ACC) to compete with Garage 61 on its turf.
- **Niche-down to ACC + iRacing only** as a positioning shift (option B from market validation; would mean dropping AC/AC-UDP/OBD-II — not happening for v1.0).
- **Real-car (OBD-II) deep features** beyond what already exists. The wedge is unproven (per market validation) and OBD-II's latency is a real product constraint.

## Risks (release-level)

1. **RaceData AI keeps shipping monthly.** Six months from now they'll have shipped six more releases. Counter: stay focused on the live-experience moat; don't try to match their feature breadth.
2. **Website MVP is harder than estimated.** Phase 3 is the most uncertain in scope. If it slips, Strategy tab v2 (Phase 2) could be parallelized rather than serialized to keep momentum.
3. **ACC broadcasting integration (Phase 2) blows up.** Undocumented protocol, unmaintained wrappers. If it turns out to be 2 months instead of 1, drop it and ship without — Strategy tab v1's heuristic is "good enough" for v1.0.
4. **Solo-dev burnout.** Six months of nights-and-weekends work on a free product is hard to sustain. Plan rest weeks. Don't compound by stacking phases.

## Status check cadence

Update this doc:
- At the end of each phase (mark phase complete, add lessons-learned).
- When a date or scope item shifts by more than a week.
- When a decision in "guiding principles" gets revisited (this should be rare; if it happens, write a new monetization-style decision doc).

If this doc has been untouched for >2 weeks but work has continued, it's stale — re-sync before relying on it.

## What this doc is NOT

- Not implementation plans (those live in `docs/superpowers/plans/`).
- Not commitments (these are estimates; reality moves them).
- Not the source of truth for individual feature scope (that's the per-feature spec/roadmap docs).
- Not a marketing doc.
