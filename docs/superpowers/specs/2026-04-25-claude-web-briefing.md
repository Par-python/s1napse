# S1napse — context briefing for Claude (web)

**Purpose:** paste this into a fresh Claude.ai conversation as the first message. It's self-contained — the model doesn't need access to the repo or any other docs.

**How to use:** copy everything below the `---` line and paste it in. Then ask your question.

---

I'm working on a product called **S1napse** and I want to continue a strategy conversation here. Below is the full context so you don't need to ask. After this message I'll send my actual question.

# What S1napse is

S1napse is a **free Windows desktop telemetry app** for sim racing and real-car track-day driving. One app for both worlds.

**Sim support:** ACC (Assetto Corsa Competizione), Assetto Corsa, iRacing — auto-detects whichever is running.
**Real-car support:** any car with an ELM327 OBD-II adapter (Bluetooth or USB).

**Current features:**
- Live HUD / dashboard during a session
- Lap analysis tab (per-lap channel data — throttle, brake, gear, speed, etc.)
- Lap comparison tab (overlay two laps)
- Replay tab
- Coaching tab + math channels
- Self-building track map (records track geometry from live driving)
- Race strategy tab (position, gap, tyres, fuel-save calculator, undercut/overcut, pit-strategy, lap-trend)
- Telemetry sampling at 50 Hz, lap exports as gzipped JSON (`.json.gz`)

**Tech:** Python desktop app, packaged with PyInstaller, distributed as a single `.exe` on GitHub Releases. Currently unsigned (Windows SmartScreen warns on download). Solo dev.

**Stage:** working prototype, pre-release, pre-revenue. Target v1.0 release: late October 2026.

# The business plan (decided)

- **Desktop app: 100% free, forever.** No Pro tier, no caps, no license keys. The app is the acquisition funnel.
- **Companion website (s1napse.gg, future): paid subscription.** Lap history, PBs across sessions, friend leaderboards, lap overlays, sharing. Target ~$3–5/mo or ~$30/yr.
- **Free website tier with no caps on lap count.** This is a deliberate counter-positioning against the main competitor (RaceData AI) whose free tier is 30 stints/month and feels like a demo.
- **Why this model:** code signing isn't a launch blocker for a free app. Recurring revenue belongs on the website (it has compounding value — history, leaderboards, social — that a local desktop app doesn't). The app being free maximizes top-of-funnel.

# Competitive landscape (researched 2026-04-25)

**Sim-side competitors:**
- **Racelab** — live overlays, free + ~€3.90/mo Pro. iRacing/AC/ACC/rF2/LMU/AMS2/F1. No web component.
- **SimHub** — dashboards, hardware effects. Free + donations. No real-car support.
- **Garage 61** — telemetry analysis + leaderboards + setups. **iRacing only.** Free + ~€5/mo annual / $7/mo. 50M+ laps. Web app.
- **Coach Dave Delta** — AI coaching + setups + telemetry. iRacing/ACC/LMU/GT7/AC/AMS2/AC Evo. $12.99/mo or $109/yr.
- **trackTitan** — AI-powered telemetry coaching. Subscription only, no free tier.
- **TinyPedal** — free open-source overlays. rF2/LMU only.
- **VRS / iSpeed** — telemetry coaching, iRacing-only, subscription.

**Real-car-side competitors:**
- **Harry's LapTimer** — iOS/Android, real cars only. $8.99 / $12.99 / $27.99 one-time tiers.
- **RaceChrono Pro** — iOS/Android, real cars only (imports iRacing .ibt files post-session, no live sim). $17.99 one-time.
- **TrackAddict** — iOS/Android, real cars only. Free + Pro upgrade.
- **AiM Solo 2 DL / Garmin Catalyst** — hardware lap timers, $400–$1000+.

**Cross-over (sim + real-car) competitors:**
- **vTelemetry PRO (Renovatio)** — pro-leaning, sim + real-car comparison via MoTeC/AIM/Atlas/Pi/Wintax converters. CHF 99 base. Targets pros, not consumers.
- **MoTeC i2** — pro telemetry analysis. Free reader, paid pro. Steep learning curve.

**The biggest competitor — RaceData AI (the one I want to talk about):**
- 7-person bootstrapped team in San Mateo, CA. Founder: Josef Karaburun (mechanical engineer, ex-defense, Formula Student racer, b. 1995). Dedicated designer with two A' Design Awards.
- Founded 2024. Launched beta Oct 2024. Ships **monthly** without slipping.
- Sim support: iRacing, AC, ACC, LMU, AMS2, rF2. F1 + GT7 + AC Evo on roadmap (June + Sept 2026).
- **Already shipped:** leaderboards (Feb 2025), user-vs-user lap comparison (Feb 2025), AI coaching, **real-world racing integration (Dec 2025)**.
- Web-based (no desktop app, no live in-session HUD).
- Pricing: free 30 stints/month + 1 AI hint/month → $3/mo Performance (unlimited stints, 10 AI hints) → $12/mo Pro (unlimited + 1 coaching session) → $100/mo Paddock (real-world race upload).
- Bootstrapped (no VC pressure, no exit clock).

**RaceData AI's structural strengths:** 7-person team, monthly cadence, award-winning UX, broad sim coverage, 18 months of head start.

**RaceData AI's structural weaknesses (S1napse openings):**
- Free tier is stingy (30 stints, 1 AI hint/mo) — feels like a demo, not a usable product.
- No mobile, no roadmap for it.
- Web-only — can't do live in-session HUD overlay (web-app structural limitation).
- AI is the headline; users tired of AI-everything are an underserved segment.
- "Stints" as a unit is unintuitive; users think in laps and sessions.
- 7-person team has overhead a solo dev doesn't (meetings, planning, design reviews).

# Demand signals (what users actually say)

- **MoTeC export friction is a recurring complaint** in sim racing forums. Sim tools rarely export `.ld`/`.ldx` cleanly; CSV is "not very useful."
- **OBD-II is the established budget telemetry path for track-day drivers** (PistonHeads, Lotus, Grassroots Motorsports threads). Caveat users repeatedly note: *"OBD-II will give you telemetry, but it will be a little bit delayed and out of sync with your drive — it's not a realtime protocol."*
- **Guest leaderboards / friend comparison drives engagement** — "creates a fun and competitive atmosphere for family and friends." Validates the website's leaderboard pitch.
- **Garage 61's "private laps" friction is a known complaint.** Lesson: leaderboard data needs sensible default visibility (default public, opt-out per session).
- **No clear demand signal for "one tool for sim AND real-car"** — searched specifically, no forum threads found voicing this need. The "both worlds" angle is a real product gap but not a validated customer pull.

**Caveat on this section:** Reddit was unreachable during research (anti-scraping). Demand-side signals lean on aggregator sites (Auto Express, Coach Dave Academy, zleague.gg) and forums I could fetch (PistonHeads, Lotus, Grassroots Motorsports, OverTake.gg). r/simracing, r/iRacing, r/ACCompetizione direct-comment data was NOT accessible.

# Strategic positioning (current thinking)

Three options on the table from the market validation work — I haven't fully committed to one yet:

**Option A — Live-experience moat (current lean).** The desktop app's *real-time* capabilities (HUD, self-building track map, race strategy) are the headline. Web competitors structurally can't match a tight live overlay. Website is a cheap or free companion, not the revenue product.

**Option B — Niche down to ACC + iRacing only.** Be the *best* tool for those two, deeper integration than RaceData AI's 6-sim breadth. Solo-dev velocity matters most when scope is tight. Risk: smaller addressable market.

**Option C — Consumer real-car wedge.** There's a real gap between free phone OBD-II apps and $100/mo pro real-car telemetry. S1napse could be the consumer-priced sim + OBD-II tool. Demand-side unproven.

# Release roadmap (target: late Oct 2026, ~6 months)

1. **Phase 1 — Strategy tab v1** (May 2026, 3–4 weeks). Six cards on a new Strategy tab + Race-tab headline banner. ACC broadcasting NOT yet integrated; rival-watch uses an inferred gap-jump heuristic.
2. **Phase 2 — Strategy tab v2** (June–July 2026, 3–4 weeks). Wire ACC broadcasting API. What-if pit planner. Two-phase warmup-then-degradation tyre model.
3. **Phase 3 — Companion website MVP** (July–August 2026, 4–5 weeks). User accounts, lap upload, history view, PBs, public leaderboards (default public, opt-out per session), lap comparison, Stripe.
4. **Phase 4 — Pre-release polish** (September 2026, 3–4 weeks). Lap-RAM optimizations (NumPy-backed channel storage, dtype quantization), user-facing telemetry-rate setting, onboarding, bug-bash week.
5. **Phase 5 — Release infrastructure** (October 2026, 2–3 weeks). Code signing, auto-updater, installer/uninstaller, GitHub release workflow, README rewrite, privacy policy + ToS.
6. **Phase 6 — Launch** (late Oct 2026). Soft launch on r/ACCompetizione, r/iRacing, r/simracing. Discord for early adopters.

**Out of scope for v1.0:** mobile companion app, iRacing-specific deep features beyond ACC parity, niching to ACC+iRacing only as a positioning shift, deep real-car OBD-II features.

# Guiding principles

- The desktop app is and stays free. Paid product is the website.
- Live in-session experience is the moat. Every feature should ask "does this make the live experience tighter?"
- No-AI honest-tool positioning. Calculations transparent and labeled, not black-box.
- Shipping cadence matters. Can't out-feature RaceData AI; can be more focused.

# What I want help with

[Replace this section with your actual question. Examples: "I'm wrestling with whether Option A or B above is the better move — push back on my reasoning"; "Help me brainstorm what 'live-experience moat' features would actually look like in the Strategy tab"; "Sketch what the website MVP scope should be in Phase 3 given the 4–5 week budget."]
