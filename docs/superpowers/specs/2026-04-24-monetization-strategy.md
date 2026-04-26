# S1napse Monetization Strategy

**Date:** 2026-04-24
**Status:** Decided (strategy only — no implementation plan yet)

## Decision

S1napse is a **free desktop app** paired with a **paid companion website**. The app is the acquisition funnel; the website is the revenue product.

- **App:** 100% free, fully functional, no caps, no Pro tier, no license keys.
- **Website (future):** paid subscription for lap history, PBs, leaderboards, and lap comparisons.

## Why this model

Two other models were considered and rejected:

1. **Paid app, one-time purchase (~$10–15).** Rejected because:
   - Windows SmartScreen warnings on an unsigned .exe kill conversion at a paywall. Code signing (~$200–400/yr) would be a prerequisite.
   - One-time revenue requires constant new-user acquisition.
   - Piracy of local Windows binaries is trivial.

2. **Paid app, cheap subscription (~$10/yr).** Rejected because:
   - Recurring billing infra (Stripe/Paddle, renewal emails, card-expiry handling, grace periods, churn) is disproportionate work for ~$800/yr at 100 users.
   - A local desktop app has none of the properties that make subscriptions feel fair to users (no ongoing server cost, no content that compounds).
   - Subscriptions belong on the website, not the app.

The chosen model wins on three points:

- **No code-signing blocker for launch.** SmartScreen warnings are tolerable for a free app; they are fatal for a paid one.
- **Recurring revenue naturally belongs on the website.** Users intuitively pay monthly for storage, leaderboards, and social features — not for local software.
- **The app becomes a zero-friction acquisition funnel** for the website, which is the real long-term business.

## Website product shape (future)

- **Free tier:** last ~20 laps visible, no leaderboards, no comparisons. Effectively a teaser.
- **Paid tier:** unlimited history, PBs across all sessions, global + friend leaderboards, lap overlays, sharing. Price point TBD, expected range ~$3–5/mo or ~$30/yr.
- **Payments:** Stripe (or Paddle/Lemon Squeezy as merchant of record if VAT handling becomes a burden).

## Roadmap implications

### Keep doing

- All perf/RAM work in `TODO.md`. Free users still need a rock-solid app — the app is the product people judge S1napse by, even though it's not what they pay for.
- The current `.json.gz` lap export direction — a gzipped lap file is essentially the future upload payload for the website. Good accident.

### Drop (previously considered, no longer needed)

- In-app license key system.
- In-app paywall UI / Pro unlock flow.
- Code signing as a launch blocker (still nice-to-have eventually, but not gating anything).
- Payment provider integration in the desktop app (Lemon Squeezy, Paddle, etc.).

### Add later (website phase)

- Website backend: auth, lap upload API, lap storage, leaderboard compute.
- Website frontend: dashboard, lap viewer, PB tracking, leaderboards.
- Stripe subscription integration.
- In-app "upload to s1napse.gg" (or chosen domain) button — the only app-side change the website requires.

## Open questions

- Domain / brand name for the website. Pick early so the app can start pointing at it (even if only as a waitlist page).
- Whether the website launches with leaderboards or adds them later. Leaderboards are the strongest social/viral feature but need anti-cheat thought (at minimum, tie laps to a verified session + track + car combo and flag implausible deltas).
- Whether uploads are manual (user clicks) or automatic (opt-in, on lap completion). Leaning automatic-with-toggle.

## Explicitly out of scope for this document

- Implementation plan for the website. That gets its own spec when the app work is further along.
- Pricing of the paid website tier. Decide closer to launch based on what the free tier actually looks like.
- Any paid feature in the desktop app. The app stays free. If this ever changes, it needs a new strategy doc, not an amendment to this one.

---

## Pitches

### Public pitch (for users — landing page, Reddit, Discord)

**S1napse — your telemetry, in one place.**

S1napse is a free telemetry dashboard for sim racers and real-car track-day drivers. Plug in your sim or your car's OBD-II port and get a live HUD, lap analysis, and a track map that builds itself as you drive. No setup files, no plugins, no MoTeC export dance — launch it and go.

It works with **ACC, Assetto Corsa, iRacing**, and any real car with an **ELM327 OBD-II adapter**. One app for both worlds.

The desktop app is free and always will be. Sync your laps to **s1napse.gg** to keep your full history, track PBs across sessions, compare laps with friends, and climb track leaderboards. Free at the door, more if you want the long game.

**One-liner:**
> Free telemetry dashboard for sim and real-car racing — live HUD, self-building track map, lap analysis. Sync to the web for unlimited history, PBs, and leaderboards.

### Business pitch (for investors / partners)

**Problem.** Sim racing has exploded — millions of drivers across iRacing, ACC, and AC, plus a long tail of real-car track-day enthusiasts. They all generate telemetry, and they all want to go faster. Today that data is fragmented across half a dozen tools (Racelab, Second Monitor, MoTeC, Harry's LapTimer, TrackAddict), most of which solve one slice of the problem and none of which connect the sim and real-car worlds.

**Product.** S1napse is a free desktop telemetry app that ingests data from every major sim **and** any real car via OBD-II, normalizes it, and presents a live HUD plus session analysis. The companion website (s1napse.gg) is where that data lives long-term — full lap history, PBs, friend comparisons, and per-track global leaderboards.

**Model.** Free app, paid website subscription. The app is the acquisition funnel — zero-friction download, no paywall, no signup required. The website is the recurring-revenue product, where users pay for the things that compound: history, social, leaderboards. Target price ~$3–5/mo or ~$30/yr. Free website tier (last ~20 laps) acts as a teaser.

**Why this works.**
- **Acquisition is cheap.** Free app, organic distribution through sim-racing Discords, subreddits, YouTube. No paid ads needed to seed the funnel.
- **Retention is structural.** A user's lap history compounds over time. The longer they use S1napse, the more painful it is to leave — classic data-lock-in flywheel, but in a way users actively want.
- **Leaderboards are viral.** Per-track global rankings turn every user into a recruiter for their friends. Lap comparisons and shared overlays are inherently social.
- **The sim+real-car positioning is defensible.** Every competitor picks a side. S1napse is the only tool a user keeps whether they're in the rig or in the paddock.

**Competition.** Racelab and Second Monitor (sim-only, dashboard-focused, no web product). Garage61 and trackTitan (sim coaching/data, paid, no real-car support). Harry's LapTimer / RaceChrono / TrackAddict (real-car only, mobile, no sim integration). MoTeC (pro tool, expensive, steep learning curve). S1napse sits in the gap none of them cover.

**Stage and ask.** Pre-revenue. Desktop app is in active development with a working prototype across all three major sims and OBD-II. Next milestones: ship v1 of the app publicly, build the website MVP (upload + history + per-track leaderboards), launch paid tier. [Funding ask / partnership ask / customer-development ask — fill in based on the conversation.]

**One-liner:**
> S1napse is the free telemetry app that becomes a paid web product. Free app for sim racers and real-car drivers; subscription website for the lap history, PBs, and leaderboards that keep them coming back.

---

## Market validation (researched 2026-04-25)

Honest read on whether the S1napse positioning holds up against real competitors and demand signals.

### TL;DR

- **The "both worlds" angle is mostly real but contested.** None of the well-known sim tools (Racelab, SimHub, Garage 61, Coach Dave Delta, trackTitan) support real-car OBD-II. None of the major real-car apps (Harry's, RaceChrono, TrackAddict) support live sim telemetry. **However, two niche products explicitly target this gap:** vTelemetry PRO (Renovatio, CHF 99 base, pro-leaning) and RaceData AI ($100/mo "Paddock" tier, real-world support listed as "in progress, June 2026"). Neither is consumer-mainstream. S1napse's differentiator is real but no longer entirely uncontested — it sits at a different price/positioning point than these two.
- **The closest direct competitor to S1napse's planned website (Garage 61) is iRacing-only.** 50M+ laps, strong iRacing network effect, but ACC and AC users are completely unserved by it. That gap is real and is probably the strongest single market signal in this report.
- **A new entrant called RaceData AI is moving into the same lane S1napse is targeting** — sim telemetry for iRacing/AC/ACC, $3/mo "Performance" tier, free starter tier (30 stints), real-world racing planned for mid-2026. They're solo-founder-shaped, recently launched, won a UX design award. This is the closest thing to a direct competitor for the website plan and the most important finding in this report.
- **Telemetry-tool subscriptions in this space cluster €3–€13/mo.** Racelab Pro ~€3.90/mo, RaceData AI Performance $3/mo, Garage 61 Pro ~€5/mo annual / $7/mo, Coach Dave Delta $12.99/mo. The planned ~$3–5/mo for S1napse website fits cleanly, but RaceData AI's $3/mo Performance tier sets a credible floor — pricing higher needs a clear "why."
- **The market is real, not vibes.** Racing-simulator market projected at $1.30B in 2026 → $2.46B by 2034 (8.3% CAGR). Even if telemetry tooling is a small slice, the absolute audience supports niche subscription products.
- **Biggest unverified risk (unchanged):** I found no direct quoted demand for a *cross-sim, cross-real-car* product from regular users. The two products that target this lane (vTelemetry PRO, RaceData AI's Paddock tier) target pros and sim centers — not the hobbyist audience S1napse would serve. The "both worlds for hobbyists" angle is genuinely unproven.

### Competitive landscape

| Tool | What it does | Supports | Price | Web/cloud? |
|---|---|---|---|---|
| **Racelab** | Live overlays | iRacing, AC, ACC, rF2, LMU, AMS2, F1 | Free + Pro ~€3.90/mo | No |
| **SimHub** | Dashboards, hardware effects | Most sims | Free + donations | No |
| **Garage 61** | Telemetry analysis, community laps, setups | **iRacing only** | Free + Pro €5/mo annual / $7/mo | Yes (web app) |
| **Coach Dave Delta** | AI coaching, setups, telemetry | iRacing, ACC, LMU, GT7, AC, AMS2, AC Evo | $12.99/mo or $109/yr | Partial |
| **trackTitan** | AI-powered telemetry coaching | iRacing, ACC, AC, F1, Forza | Subscription only (no free tier) | Yes |
| **TinyPedal** | Free open-source overlays | rF2, LMU only | Free | No |
| **VRS / iSpeed** | Telemetry, coaching | iRacing | Subscription | Partial |
| **Harry's LapTimer** | Real-car GPS lap timer + OBD-II | iOS/Android, real cars only | $8.99 / $12.99 / $27.99 (one-time tiers) | No |
| **RaceChrono Pro** | Real-car GPS lap timer + OBD-II | iOS/Android, real cars; *imports* iRacing .ibt | $17.99 one-time | No |
| **TrackAddict** | Real-car GPS lap timer + OBD-II | iOS/Android, real cars only | Free + Pro upgrade | No |
| **AiM Solo 2 DL / Garmin Catalyst** | Hardware lap timers | Real cars only | $400–$1000+ hardware | Partial (companion apps) |
| **MoTeC i2** | Pro telemetry analysis | Sim + real (with logger) | Free reader, paid pro | No |
| **RaceData AI** ⚠️ | Sim telemetry, AI hints, web-based | iRacing, AC, ACC; real-world "in progress" June 2026 | Free (30 stints / 1 AI hint) → $3/mo → $12/mo → $100/mo (real-world) | Yes (web app) |
| **vTelemetry PRO (Renovatio)** | Pro telemetry, sim + real comparison | Most sims + real-car via MoTeC/AIM/Atlas/Pi/Wintax converters | CHF 99 base (Stage 1), tiered up to Motorsport Edition | No |

**Key gaps S1napse can credibly own:**

1. **ACC + AC + iRacing telemetry on a single web product, with a generous free tier.** Garage 61 owns iRacing only. Coach Dave Delta covers ACC but is desktop-first and 2.5× the price. RaceData AI is the closest match but is newer, AI-focused, and its free tier is tightly capped (30 stints, 1 AI hint/mo). A free-app + cheap-web combo with no AI gimmick could be the "honest, no-frills, multi-sim" play.
2. **Real-car OBD-II + sim in one consumer-priced app.** Not uncontested — vTelemetry PRO and RaceData AI's Paddock tier exist — but those target pros (CHF 99+ and $100/mo respectively). There is no consumer-priced product in this space.
3. **Free desktop app at the door.** Racelab and Coach Dave Delta have free tiers but the analysis-heavy tools (trackTitan, VRS, RaceData AI's useful tiers) don't. A genuinely capable free desktop app is a real wedge.

### Demand signals

The forum/Reddit dive turned up moderate but not overwhelming signal. Strongest threads:

- **MoTeC export friction is a recurring complaint.** Multiple sources note that direct `.ld`/`.ldx` export from sim telemetry tools is rare and that "without converters, [CSV] is not very useful." ([SimHub forum on MoTeC export](https://www.simhubdash.com/community-2/simhub/export-telemetry-to-motec/), [Coach Dave on iRacing+MoTeC](https://coachdaveacademy.com/tutorials/how-to-use-motec-data-in-iracing/)) — this validates the broader thesis that telemetry tooling is fragmented and friction-heavy.
- **OBD-II as a budget telemetry path is well-established for track-day drivers.** Multiple PistonHeads / Lotus / Grassroots Motorsports threads recommend "RaceChrono on Android with a Bluetooth OBD2 adapter" as the standard cheap setup. Caveat from the same threads: *"OBD-II will give you telemetry, but it will be a little bit delayed and out of sync with your drive — it's not a realtime protocol."* This is a real product constraint S1napse will face.
- **Guest leaderboards / friend comparison drives engagement.** zleague.gg piece: *"Guest leaderboards have transformed the racing experience for users by creating a fun and competitive atmosphere for family and friends, fostering camaraderie and encouraging improvement."* Validates the website's leaderboard pitch.
- **Garage 61's "private laps" friction is an active complaint.** Coach Dave article calls it out: *"a lot of the fastest times and setups can also get locked behind the user when they choose to make their data private, meaning your comparisons for improvement with other top-performing drivers can be limited."* A design lesson for S1napse: leaderboard data needs sensible default visibility.
- **No clear evidence of users asking for "one tool for sim + real car."** I searched specifically and didn't find threads voicing this need. This is the weakest part of the validation.

### Red flags / risks

1. **The "both worlds" market may be two markets, not one.** I found no demand signal that sim racers *also* want their real-car data in the same tool, or vice versa. The product can support both, but marketing will probably need to pick a primary audience and lead with that.
2. **OBD-II latency is real.** Forum users repeatedly note OBD-II is not a realtime protocol. For sim racers used to 50 Hz live data, switching to OBD-II in the same app may feel underwhelming. Set expectations carefully.
3. **iRacing's ecosystem is sticky.** Garage 61 has 50M+ laps inside iRacing. Cracking iRacing means competing with an established network effect; leading with ACC/AC (where Garage 61 doesn't play) is probably the better wedge.
4. **Hardware-bundled real-car telemetry (AiM, Garmin Catalyst) owns the high-end.** Track-day drivers serious enough to pay monthly may already own a $400+ dedicated unit. The S1napse real-car audience is the budget/casual track-day driver, not the data-serious one.
5. **App store distribution mismatch.** The strongest real-car telemetry tools are mobile (Harry's, RaceChrono, TrackAddict). S1napse is a Windows desktop app — it cannot serve track-day drivers in their car. The real-car positioning probably only works for *home review* of OBD-II data captured separately, or requires a future mobile companion.
6. **No clear failure case found, but absence of evidence isn't strong.** I did not find a "free desktop sim app + paid web companion" that tried this exact model and died. Could mean the model is unproven rather than impossible.

### Verdict

The strategy still holds up, but the second pass surfaces a real competitive risk that wasn't visible in the first round.

**What's validated:**
- The price point (~$3–5/mo) sits inside the established competitive band, with RaceData AI's $3/mo Performance tier as the credible floor.
- The website's value proposition (history, PBs, friend leaderboards) maps onto real demand signals (Garage 61's iRacing success, the zleague.gg guest-leaderboards piece).
- ACC + AC + iRacing on one web product is a real gap that Garage 61 doesn't fill.
- The market is large enough ($1.3B+ and growing) to support a niche subscription product.

**What's newly contested:**
- **RaceData AI is the most direct competitor and was missed in the first pass.** They target the same audience (iRacing/ACC/AC sim racers wanting accessible telemetry), at the same price band ($3/mo entry tier), with a free tier as the on-ramp. They launched 2024, won a 2025 UX design award, and explicitly list "real-world race integration" as in progress for mid-2026. **They are roughly six months ahead of where S1napse plans to be, in nearly the same lane.** That's not a deal-breaker, but it changes "this is an open market gap" to "this is a competitive race."
- **vTelemetry PRO already does sim + real-car comparison** at the pro/CHF 99 tier. The "both worlds" pitch is no longer technically novel — only novel at the consumer price point and only for the OBD-II (vs. pro logger) audience.

**What's not validated and needs testing:**
- Whether hobbyist sim racers genuinely want real-car telemetry in the same app. No demand-side signal found in the round-2 search.
- Whether the free-app-and-paid-website model meaningfully outperforms RaceData AI's web-only-with-free-tier model. Plausible argument either way — S1napse's free desktop app is more useful standalone than a free 30-stint web tier, but the web-only model has lower friction to try.

**Recommended adjustments to the strategy:**

1. **Stop treating "the open ACC/AC market gap" as a blank canvas.** RaceData AI is moving into it. The realistic positioning is "the open-source-spirited, no-AI-gimmick, self-hostable-feeling alternative" — lean into the things RaceData AI structurally can't do as a venture-flavored web product: a genuinely good free desktop app, no per-month stint cap, no AI hint quota, lap files you own as plain `.json.gz`.
2. **Lead marketing with sim, not "both worlds."** Real-car OBD-II becomes a quiet bonus feature, not a pillar. The "both worlds" pitch is now muddied by vTelemetry PRO and RaceData AI's roadmap; trying to own that narrative against deeper-pocketed competitors is a losing battle. Win the niche where you're actually better: low-friction, free-at-the-door, pleasant to use.
3. **Keep the ~$3–5/mo target.** Don't price below RaceData AI's $3 unless you specifically want to be the "cheap option" — that's a fragile position. Pricing equal at $3/mo with a more generous free tier is probably the strongest play.
4. **Watch RaceData AI's roadmap.** If their June 2026 real-world racing release lands well, the real-car angle gets harder. If it slips or underwhelms, S1napse has a window. Either way, don't hinge the strategy on real-car being your moat.

### Sources

- [Garage 61 Pro pricing](https://garage61.net/pro)
- [Coach Dave Delta vs Garage 61 comparison](https://coachdaveacademy.com/tutorials/coach-dave-delta-vs-garage-61-which-is-best-for-you/)
- [Racelab Pro pricing review (zleague.gg)](https://www.zleague.gg/theportal/sim-racing-the-great-overlay-price-gouge-whats-up-with-racelabs/)
- [trackTitan memberships](https://www.tracktitan.io/memberships)
- [TinyPedal (open source overlays)](https://github.com/TinyPedal/TinyPedal)
- [SimHub MoTeC export thread](https://www.simhubdash.com/community-2/simhub/export-telemetry-to-motec/)
- [Harry's LapTimer / RaceChrono / TrackAddict comparison (Auto Express)](https://www.autoexpress.co.uk/accessories-tyres/92336/gps-lap-timer-apps-tested)
- [Lap timers with OBD-II for telemetry (BimmerPost)](https://f80.bimmerpost.com/forums/showthread.php?t=2043134)
- [Data loggers thread (PistonHeads)](https://www.pistonheads.com/gassing/topic.asp?h=0&f=18&t=1360863)
- [Guest leaderboards in sim racing (zleague.gg)](https://www.zleague.gg/theportal/race-to-the-top-the-joy-of-guest-leaderboards-in-sim-racing/)
- [Racing simulator market size 2026–2034 (Fortune Business Insights)](https://www.fortunebusinessinsights.com/racing-simulator-market-115926)
- [Best sim racing apps 2026 (Coach Dave Academy)](https://coachdaveacademy.com/tutorials/the-best-sim-racing-apps/)
- [RaceData AI homepage](https://www.racedata.ai)
- [RaceData AI pricing](https://www.racedata.ai/pricing-monthly)
- [RaceData AI BoxThisLap review (Oct 2024)](https://boxthislap.org/racedata-ai-a-fresh-approach-to-telemetry-for-simracers/)
- [vTelemetry PRO (Renovatio)](https://www.renovatio-dev.com/vtelemetry-pro)
- [vTelemetry PRO at Racing Unleashed shop (CHF 99 base)](https://shop.racing-unleashed.com/products/vtelemetry-pro)
- [Telemetry Tool for ACC (OverTake)](https://www.overtake.gg/downloads/telemetry-tool-for-acc.34563/)
