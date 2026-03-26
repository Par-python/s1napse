# S1napse — Coaching & Insights System: Implementation Prompt

> **Purpose:** This document is a detailed engineering prompt for Claude Code to implement a real-time coaching and insights layer on top of the existing S1napse telemetry app. Read this entire document before writing any code.

---

## 1. Project Context

S1napse is a PyQt6-based real-time telemetry dashboard for sim racing (ACC, Assetto Corsa, iRacing) and real racing (ELM327 OBD-II). The main entry point is `s1napse.py`. The app already collects and displays:

- Speed, RPM, gear, throttle %, brake %, steering angle (20 Hz in sim, ~2-4 Hz OBD-II)
- Tyre temperatures (inner/middle/outer per corner), tyre pressures, brake temps
- Lap times, sector splits (S1/S2/S3), lap validity flags
- Distance-based telemetry traces per lap (speed, throttle, brake, steering, RPM, gear)
- A self-building track map from real car coordinates (X/Z or lat/lon)
- Delta time vs a reference lap at every point on track
- Fuel remaining, ABS/TC activity

The app stores per-lap telemetry as distance-indexed arrays and saves track maps as JSON in a `tracks/` folder.

**Your job is to build a coaching/insights engine that consumes this existing data and produces actionable, beginner-friendly feedback.** You are NOT rebuilding the UI from scratch — you are adding a new analysis layer and a "Coach" tab/panel that integrates into the existing PyQt6 application.

---

## 2. Target User

The primary user is a **beginner sim racer** who:

- Doesn't know how to read telemetry graphs
- Doesn't understand what trail braking is, or why their lap times plateau
- Needs plain-language explanations, not raw numbers
- Responds well to positive reinforcement when they improve
- May not know which corner is "Turn 4" — needs visual context on the track map

Design every insight, label, and message with this user in mind. Technical data should exist in expandable/secondary views, never as the primary output.

---

## 3. Feature Specifications

### 3.1 — Corner Detection & Segmentation

**Goal:** Automatically divide the track into numbered corners so all other features can reference them.

**Algorithm:**

1. Take the distance-based steering trace from a completed lap
2. Smooth the steering signal (use a Savitzky-Golay filter or simple moving average, window ~15-25 samples depending on Hz)
3. Detect corners where `abs(smoothed_steering) > threshold` for a sustained duration
   - Entry threshold: steering exceeds ~10-15% of max observed steering for that lap
   - Exit threshold: steering drops below the entry threshold
   - Minimum corner duration: ~50m of distance to avoid counting chicane kinks as separate corners
4. For each detected corner, record:
   - `corner_id`: sequential number (Turn 1, Turn 2, ...)
   - `entry_distance`: distance where braking begins (look backward from steering onset to find where brake first exceeds ~5%)
   - `turn_in_distance`: distance where steering exceeds the threshold
   - `apex_distance`: distance of minimum speed within the corner
   - `exit_distance`: distance where steering drops below threshold AND throttle exceeds ~80%
   - `direction`: LEFT or RIGHT (sign of average steering in the zone)
5. Merge corners that are < 30m apart (treat as one complex corner)
6. Cache the corner map per track — once detected, reuse on subsequent laps unless the user resets it

**Data structures:**

```python
@dataclass
class Corner:
    corner_id: int              # 1-indexed
    direction: str              # "LEFT" or "RIGHT"
    entry_distance: float       # meters from start/finish
    turn_in_distance: float
    apex_distance: float
    exit_distance: float
    braking_start_distance: float  # where brake > threshold before entry

@dataclass
class CornerPerformance:
    corner: Corner
    lap_number: int
    entry_speed: float          # km/h at turn_in_distance
    min_speed: float            # km/h at apex_distance
    exit_speed: float           # km/h at exit_distance
    braking_distance: float     # meters from brake start to apex
    peak_brake_pressure: float  # 0.0 - 1.0, max brake % in the zone
    trail_brake_detected: bool
    trail_brake_duration_m: float  # meters of overlap (brake > 0 AND steering > threshold)
    trail_brake_release_quality: str  # "smooth", "abrupt", "none"
    time_in_corner: float       # seconds from entry to exit
    delta_vs_best: float        # seconds gained/lost vs personal best in this corner
    throttle_application_distance: float  # distance from apex where throttle > 20%
```

**Important edge cases:**

- Outlap / in-lap: skip entirely (already handled by S1napse)
- Invalid laps: still analyze but flag as invalid — beginners can still learn from them
- Straights: the zones between corners, also worth tracking (acceleration, top speed, gear usage)
- Oval tracks or tracks with very few corners: algorithm should still work, just fewer segments

---

### 3.2 — Corner-by-Corner Coaching

**Goal:** After each lap, show a report card for every corner. One glance tells the driver where they gained/lost time and what to fix.

**Per-corner report card:**

For each corner, compare the current lap to the **personal best sector** (not overall best lap — the best performance _at that specific corner_).

Display:

1. **Corner grade:** Color-coded (green / yellow / red)
   - Green: within 0.15s of personal best at this corner
   - Yellow: 0.15s to 0.5s slower
   - Red: more than 0.5s slower
2. **Delta time:** "+0.32s" or "-0.12s" vs personal best at this corner
3. **Primary issue** (pick the single biggest problem — do NOT overwhelm with multiple issues):
   - "Braked too early" — braking_start_distance is significantly before best lap's
   - "Braked too late" — entry speed much higher but min speed much lower (overcooked it)
   - "Too slow at apex" — min_speed significantly below best
   - "Slow exit" — exit_speed significantly below best
   - "Late throttle" — throttle_application_distance much further from apex than best
   - "No trail braking" — trail_brake_detected is False when best lap had it
   - "Hesitant braking" — peak brake pressure well below best lap (not committing)
   - "Great lap!" — within 0.1s or faster than previous best
4. **Actionable tip** — one sentence, plain language:
   - "Try braking ~15m later — you have room before the turn-in point."
   - "You lifted off the brake completely before turning in. Keep ~20% brake as you start to steer."
   - "Get on the throttle as you pass the apex, even if it's just 30% at first."
   - "You nailed this corner! Entry and exit are both within 1 km/h of your best."

**Message templates & tone:**

- Always frame improvements positively: "You're getting closer" not "You're still too slow"
- When a corner improves, celebrate it: "Turn 3 improved by 0.4s — your braking point is much more consistent now"
- Use the corner number AND direction: "Turn 7 (left)" so the driver can orient on the track map
- Never show more than one problem per corner — pick the one with the highest time cost
- Include a "Quick Wins" summary at the top: "Your biggest opportunity this lap is Turn 4 — braking 20m earlier than your best. Fix this one corner for ~0.5s."

---

### 3.3 — Braking Zone Analysis

**Goal:** Teach the driver what good braking looks like and help them build consistency.

**Per-corner braking metrics to compute:**

```python
@dataclass
class BrakingAnalysis:
    corner: Corner
    lap_number: int

    # Braking point
    brake_start_distance: float     # where brake > 5%
    brake_start_speed: float        # speed at brake initiation
    brake_start_delta_vs_best: float  # meters early/late vs best lap (negative = later = braver)

    # Pressure profile
    peak_brake_pct: float           # max brake % (0-100)
    time_to_peak_ms: int            # milliseconds from brake start to peak
    brake_application_shape: str    # "progressive", "spike", "hesitant" (see below)

    # Duration and result
    total_brake_duration_m: float   # meters from brake start to brake = 0
    speed_scrubbed: float           # brake_start_speed - min_speed
    deceleration_efficiency: float  # speed_scrubbed / total_brake_duration_m (higher = more efficient)
```

**Brake application shape classification:**

Use the brake trace from brake_start to peak to classify:

- **"Progressive" (ideal for beginners):** Brake pressure ramps up over 50-150ms to peak, then holds or gradually releases. The trace looks like a smooth ramp-up. Detect: time_to_peak > 80ms AND the derivative of brake % is relatively constant (low variance in the ramp-up phase).

- **"Spike" (common beginner mistake):** Brake pressure jumps from 0 to near-peak in < 50ms. The trace looks like a step function. Detect: time_to_peak < 50ms AND peak > 70%. This risks locking wheels and unsettling the car.

- **"Hesitant" (also common):** Brake pressure is light (peak < 50%) and ramps slowly (time_to_peak > 200ms). The driver is scared of braking hard. Detect: peak < 50% AND total_brake_duration_m is long relative to the corner's demands.

**Braking consistency tracking:**

Across the last N laps (default 5), for each corner track:

- Standard deviation of brake_start_distance — high variance = inconsistent marker
- Standard deviation of peak_brake_pct — high variance = inconsistent commitment
- Show a mini "consistency score" (0-100%) where 100% = identical braking every lap

**Insight messages for braking:**

| Situation                  | Message                                                                                                                                                                 |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Spike braking              | "Turn 2: You're slamming the brake to {peak}% instantly. Try squeezing it on over half a second — this keeps the car more stable and gives you better control."         |
| Hesitant braking           | "Turn 5: Your peak brake pressure is only {peak}%. The car can handle much more. Try braking harder and shorter — firm initial pressure, then ease off as you turn in." |
| Inconsistent braking point | "Turn 8: Your braking point varies by {var}m lap to lap. Pick a visual marker on track (a sign, a patch of tarmac) and brake at the same spot every time."              |
| Braking too early          | "Turn 3: You're braking {delta}m before your best. That's almost {time}s of free time — try braking a little later each lap until you find the limit."                  |
| Good braking               | "Turn 6: Clean braking — progressive application, consistent point, good pressure. This is textbook."                                                                   |

---

### 3.4 — Trail Braking Detection & Coaching

**Goal:** Detect whether the driver is trail braking, teach them what it is, and coach them to do it better.

**Detection algorithm:**

1. For each corner, find the "overlap zone" — the distance range where BOTH:
   - `brake_pct > 3%` (still on the brake, above noise floor)
   - `abs(steering_angle) > 10% of max steering` (actively turning)
2. Measure:
   - `overlap_distance`: total meters of overlap
   - `overlap_entry_brake_pct`: brake % at the moment steering begins
   - `brake_release_gradient`: rate of brake release through the overlap zone (brake_pct per meter)
   - `brake_at_apex`: brake % at the apex distance

**Trail brake release quality classification:**

- **"Smooth" (ideal):** Brake % decreases linearly or near-linearly through the overlap zone. The gradient is consistent (low variance in brake_pct per meter). The brake reaches 0% at or just after the apex.

- **"Abrupt":** Brake % drops from >20% to 0% within a very short distance (<10m) during the overlap. This unsettles the car.

- **"None":** No overlap detected — driver releases brake fully before turning in, or releases brake and turns in simultaneously with no overlap.

**Trail braking coaching state machine:**

Track the driver's trail braking progression per corner across laps:

```
Stage 0 — "No trail braking detected"
  → Message: "Turn {n}: Right now you're releasing the brake before you start turning.
     Trail braking means keeping a bit of brake pressure as you turn in, then
     gradually releasing it. This pushes weight onto the front tyres and helps the
     car turn. Try keeping ~20-30% brake as you start to steer into the corner."

Stage 1 — "Trail braking detected but abrupt release"
  → Message: "Turn {n}: You're starting to trail brake — that's a big step!
     Right now you're releasing the brake suddenly mid-corner. Try to ease off the
     brake gradually, like slowly lifting your foot, so the car stays balanced."

Stage 2 — "Trail braking with smooth release"
  → Message: "Turn {n}: Excellent trail braking here. Smooth brake release through
     the turn-in — this is exactly what fast drivers do. Your min speed is {x} km/h
     faster than when you weren't trail braking."
```

**Visual indicator on track map:**

On the track map, for each corner, show a small icon:

- ❌ No trail braking
- ⚠️ Trail braking detected but needs work (abrupt)
- ✅ Good trail braking

This gives an instant visual overview of which corners the driver has "unlocked" trail braking on.

---

### 3.5 — Tyre Management Insights

**Goal:** Help the driver understand why their lap times degrade and how their driving affects tyre life.

**Data collection per lap:**

```python
@dataclass
class TyreSnapshot:
    lap_number: int
    tyre_position: str          # "FL", "FR", "RL", "RR"
    temp_inner: float           # °C
    temp_middle: float
    temp_outer: float
    temp_avg: float             # average of inner/middle/outer
    pressure: float             # PSI
    brake_temp: float           # °C (if available)
```

**Analysis computations:**

1. **Cross-tyre balance:**
   - Front avg temp vs rear avg temp → "front-biased" or "rear-biased" or "balanced"
   - Left avg temp vs right avg temp → flags if one side is consistently hotter (track has more corners in one direction, or setup issue)

2. **Per-tyre health indicators:**
   - Inner-outer spread: `abs(temp_inner - temp_outer)` — if > 10°C, flag as uneven wear
     - Inner hotter than outer → "too much camber" or "overloading the inside of the tyre in corners"
     - Outer hotter than inner → "understeering through corners, scrubbing the outer edge"
   - Middle vs edges: if middle is significantly hotter than inner+outer average → "tyre over-inflated"
   - If inner+outer average is hotter than middle → "tyre under-inflated"

3. **Degradation curve:**
   - Track `temp_avg` per tyre per lap over the stint
   - If temps steadily increase lap over lap → tyres are building heat (early stint, normal)
   - If temps plateau → tyres are in their window (good)
   - If temps drop AND lap times increase → tyres are going off (graining or wear)
   - If temps spike AND lap times increase → overheating / blistering

4. **Pressure drift:**
   - Track pressure per tyre per lap
   - Flag if pressure has risen by > 1.5 PSI from starting pressure → "pressures are climbing, tyres may be over their optimal window"

5. **Corner-specific tyre abuse:**
   - Correlate corners where the driver brakes hardest or has the most steering lock with per-tyre temp spikes
   - "Your front-left gets hottest after the Turn 3–4–5 complex — smoother steering through these turns would reduce front-left wear"

**Insight messages:**

| Situation               | Message                                                                                                                                                                                         |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Front-biased temps      | "Your front tyres are {x}°C hotter than the rears. This usually means heavy braking or aggressive turn-in. Lighter trail braking and earlier throttle would shift load to the rear."            |
| High inner-outer spread | "The {tyre} tyre has a {x}°C spread between inner and outer temps. The inner edge is hotter — you might be carrying too much speed into corners and overloading the inside of the tyre."        |
| Pressure climbing       | "Tyre pressures have climbed by {x} PSI since the start. Consider starting with lower pressures next session so they land in the optimal window after a few laps."                              |
| Over-inflated indicator | "The {tyre} tyre's middle temperature is much higher than the edges. This suggests over-inflation — the contact patch is too narrow in the center."                                             |
| Tyres going off         | "Your tyres peaked around lap {n} and temps are now dropping while lap times increase. This is normal tyre degradation — consider pitting soon or driving at 95% to manage the remaining life." |
| Good balance            | "Tyre temps are well balanced across all four corners — the car's setup looks solid for this track."                                                                                            |

---

### 3.6 — Lap Summary & Progress Tracking

**Goal:** After each lap, show a concise summary. Over a session, show the driver's improvement arc.

**Post-lap summary (appears automatically after crossing the line):**

```
LAP 7 — 1:43.621 (+0.8s vs best)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏆 Quick Win: Turn 4 — braking 18m too early. Fix this for ~0.5s.

Corners:  🟢 5  🟡 3  🔴 2
Trail braking: ✅ T1 T3 T5 T7  ⚠️ T2 T9  ❌ T4 T6 T8 T10
Tyres: Balanced — fronts 87°C, rears 84°C
Braking: Consistency 72% (improving — was 58% five laps ago)

Best corner: Turn 7 — 0.15s faster than your previous best!
Worst corner: Turn 4 — 0.52s lost (braked too early)
```

**Session progress view:**

- Line chart: lap time over the session with a trend line
- Highlight the "learning curve" — are they getting faster over time?
- Mark significant improvements: "You dropped 1.2s in the last 10 laps"
- Track per-corner improvement: "Turn 3 has improved by an average of 0.3s since lap 5"
- Consistency metric: standard deviation of lap times over the last 10 laps (lower = more consistent = better)

---

## 4. Architecture & Integration

### 4.1 — Where this fits in the existing codebase

The existing app (`s1napse.py`) has a main window with tabs (Dashboard, Telemetry, Lap Analysis, Race, Tyres, Lap Comparison, Session). You are adding:

1. **A new "Coach" tab** in the main tab bar — this is the primary home for all insights
2. **An analysis engine** that runs asynchronously after each lap completes
3. **Overlay additions** to the existing track map (corner numbers, trail brake icons)

### 4.2 — Module structure

Create these new modules:

```
s1napse/
├── coaching/
│   ├── __init__.py
│   ├── corner_detector.py      # Corner detection & segmentation algorithm
│   ├── corner_analyzer.py      # Per-corner performance analysis
│   ├── braking_analyzer.py     # Braking zone analysis & classification
│   ├── trail_brake_analyzer.py # Trail braking detection & staging
│   ├── tyre_analyzer.py        # Tyre management insights
│   ├── lap_coach.py            # Orchestrator: runs all analyzers, picks top insights
│   ├── insight_messages.py     # All message templates & tone logic
│   └── models.py               # Dataclasses (Corner, CornerPerformance, BrakingAnalysis, etc.)
├── widgets/
│   └── coach_tab.py            # PyQt6 widget for the Coach tab UI
```

### 4.3 — Data flow

```
Telemetry arrives (20 Hz)
    │
    ▼
Existing lap buffer fills (distance-indexed arrays)
    │
    ▼
Lap completes (cross start/finish)
    │
    ▼
coaching/lap_coach.py is triggered with the completed lap data:
    │
    ├── corner_detector.py → detect/load corners for this track
    ├── corner_analyzer.py → score each corner vs personal best
    ├── braking_analyzer.py → classify braking per corner
    ├── trail_brake_analyzer.py → detect trail braking per corner
    ├── tyre_analyzer.py → snapshot tyre state, compute trends
    │
    ▼
lap_coach.py assembles a LapReport:
    │
    ├── Picks top "Quick Win" (biggest single time gain)
    ├── Generates corner grades
    ├── Generates per-corner messages (max 1 issue per corner)
    ├── Generates tyre summary
    ├── Generates session progress update
    │
    ▼
widgets/coach_tab.py receives LapReport and updates the UI
```

### 4.4 — Performance requirements

- Corner detection should run once per track (< 100ms for a 5km track at 20 Hz)
- Per-lap analysis should complete in < 200ms total — the driver shouldn't feel any lag
- Use numpy for all array operations (it's already a dependency via matplotlib)
- Cache the corner map per track. Store it in the existing `tracks/` folder alongside the track map JSON
- Personal bests per corner should persist across sessions — save as JSON in `tracks/{track_name}_corners.json`

### 4.5 — Dependencies

Only use libraries that are already in the project or are standard:

- **PyQt6** — UI (already installed)
- **matplotlib** — for any additional plots in the Coach tab (already installed)
- **numpy** — array math (already available)
- **scipy.signal** — for Savitzky-Golay filter in corner detection (add to requirements.txt)
- **json** — for caching corner data

Do NOT add heavy dependencies like TensorFlow, scikit-learn, or any ML frameworks. All analysis should be algorithmic / heuristic.

---

## 5. Coach Tab UI Layout

### 5.1 — Overall layout (PyQt6)

The Coach tab should use a **two-column layout**:

**Left column (60% width):** The track map with corner numbers, color-coded by grade (green/yellow/red). Clicking a corner on the map highlights its detail in the right panel. Trail braking icons (✅/⚠️/❌) shown next to each corner.

**Right column (40% width):**

1. **Lap summary header** — lap number, time, delta vs best, overall rating
2. **Quick Win card** — highlighted card showing the single biggest opportunity
3. **Corner list** — scrollable list of all corners, each showing:
   - Corner number + direction + grade color
   - Delta time
   - One-line issue description
   - Expandable detail (braking analysis, trail brake status, mini telemetry graph)
4. **Tyre summary card** — current tyre balance + any warnings
5. **Session progress** — mini sparkline of lap times with trend

### 5.2 — Visual style

- Match the existing S1napse dark theme (dark background, light text)
- Use the existing color palette from the app (green for gain, red for loss, neutral grays)
- Corner grades: green (#00C853), yellow (#FFD600), red (#FF1744)
- Trail brake icons: use text symbols (✅ ⚠️ ❌) or simple colored dots
- Cards should have subtle borders and rounded corners, consistent with the existing PyQt6 style
- Keep information density moderate — beginners get overwhelmed by too much data on screen

### 5.3 — Interaction

- **Track map click:** Clicking a corner on the track map scrolls the right panel to that corner's detail and expands it
- **Corner detail expand:** Each corner in the list is collapsed by default (one-line summary). Click to expand and see braking analysis, trail brake detail, and a mini speed/brake/steering graph for that corner zone
- **Lap selector:** Dropdown at the top to review analysis for any completed lap, not just the most recent
- **Reference lap selector:** Choose which lap is the "personal best" reference (default: fastest valid lap)

---

## 6. Message Writing Guidelines

All insight messages must follow these rules:

1. **One issue per corner.** Never list multiple problems. Pick the one with the highest estimated time cost.
2. **Plain language.** Say "brake" not "decelerate." Say "get on the gas" not "apply positive longitudinal force." The only technical term you should introduce is "trail braking" — and explain it the first time.
3. **Actionable.** Every message must include something the driver can TRY. Not just "you're slow here" — "try braking 10m later" or "keep 20% brake as you turn in."
4. **Positive first.** If a corner improved, say so before mentioning remaining issues. If the lap was a personal best, celebrate it.
5. **Specific numbers.** "Braking 18m too early" is better than "braking too early." "Exit speed is 12 km/h lower" is better than "slow exit."
6. **Comparative framing.** Always compare to the driver's own personal best, never to an external standard or alien reference. This is about self-improvement.
7. **Introduce concepts progressively.** First time trail braking is mentioned, include a brief explanation. On subsequent laps, just say "no trail braking" — they already know what it means. Track this state per session.

---

## 7. Testing Strategy

### 7.1 — Unit tests

For each analyzer module, write tests with synthetic telemetry data:

- `test_corner_detector.py`: Feed it a known track shape (e.g., a simple oval with 4 corners) and verify it detects 4 corners with correct entry/exit distances
- `test_braking_analyzer.py`: Feed it a "spike" brake trace (instant to 100%) and verify it classifies as "spike." Feed it a ramp and verify "progressive."
- `test_trail_brake_analyzer.py`: Feed it overlapping brake+steering traces and verify trail braking is detected. Feed it non-overlapping traces and verify it's not detected.
- `test_tyre_analyzer.py`: Feed it a set of tyre temps with known imbalances and verify correct diagnosis.

### 7.2 — Integration test

Create a `demo_coaching.py` script that:

1. Loads a real telemetry recording (from a saved lap)
2. Runs the full analysis pipeline
3. Prints the lap report to console
4. Verifies all fields are populated and messages are coherent

### 7.3 — Edge cases to handle

- First lap on a new track (no personal best exists yet) — show "Building your baseline" message, still show trail braking and tyre data
- Very short laps (< 30s, like a karting track) — adjust corner detection thresholds
- Wet conditions (if available from sim) — adjust all thresholds (braking distances longer, tyre temps lower)
- Pit in/out laps — skip analysis entirely
- Identical lap times — don't show "+0.0s" delta, show "Matched your best"

---

## 8. Implementation Order

Build and test in this sequence:

1. **`models.py`** — all dataclasses first
2. **`corner_detector.py`** — the foundation everything else depends on
3. **`corner_analyzer.py`** — basic corner scoring (entry/min/exit speed, delta)
4. **`braking_analyzer.py`** — braking classification
5. **`trail_brake_analyzer.py`** — trail braking detection
6. **`tyre_analyzer.py`** — tyre analysis
7. **`insight_messages.py`** — all message templates
8. **`lap_coach.py`** — orchestrator that ties everything together
9. **`coach_tab.py`** — the PyQt6 UI
10. **Integration** — hook `lap_coach.py` into the existing lap-complete event in `s1napse.py`
11. **Track map overlay** — add corner numbers and trail brake icons to the existing track map widget
12. **Persistence** — save/load corner maps and personal bests per track
13. **Testing** — unit tests, integration tests, edge case handling

---

## 9. Reference: Available Telemetry Channels

These are the data channels available from the existing telemetry layer. Use these variable names when accessing data — do NOT invent new data sources.

### Sim Racing (20 Hz)

| Channel                  | Type        | Range       | Notes                                          |
| ------------------------ | ----------- | ----------- | ---------------------------------------------- |
| `speed`                  | float       | 0-350+ km/h | Ground speed                                   |
| `rpm`                    | int         | 0-15000     | Engine RPM                                     |
| `gear`                   | int         | -1 to 8     | -1=reverse, 0=neutral                          |
| `throttle`               | float       | 0.0-1.0     | Throttle position                              |
| `brake`                  | float       | 0.0-1.0     | Brake pressure                                 |
| `steering`               | float       | -1.0 to 1.0 | Steering angle (negative=left, positive=right) |
| `tyre_temp_fl_i/m/o`     | float       | °C          | Front-left inner/middle/outer                  |
| `tyre_temp_fr_i/m/o`     | float       | °C          | Front-right inner/middle/outer                 |
| `tyre_temp_rl_i/m/o`     | float       | °C          | Rear-left inner/middle/outer                   |
| `tyre_temp_rr_i/m/o`     | float       | °C          | Rear-right inner/middle/outer                  |
| `tyre_press_fl/fr/rl/rr` | float       | PSI         | Per-corner pressure                            |
| `brake_temp_fl/fr/rl/rr` | float       | °C          | Brake disc temperature                         |
| `fuel_remaining`         | float       | liters      | Fuel in tank                                   |
| `lap_time`               | float       | seconds     | Current lap elapsed time                       |
| `sector`                 | int         | 1-3         | Current sector                                 |
| `sector_times`           | list[float] | seconds     | S1, S2, S3 splits for completed laps           |
| `lap_valid`              | bool        |             | Whether current lap is clean                   |
| `car_x` / `car_z`        | float       | meters      | World position for track map                   |
| `distance`               | float       | meters      | Distance traveled this lap                     |
| `abs_active`             | bool        |             | ABS currently intervening                      |
| `tc_active`              | bool        |             | Traction control currently intervening         |
| `delta_to_best`          | float       | seconds     | Live delta vs reference lap                    |

### Real Racing / OBD-II (2-4 Hz)

| Channel        | Type  | Notes                                   |
| -------------- | ----- | --------------------------------------- |
| `speed`        | float | Vehicle speed via OBD-II                |
| `rpm`          | int   | Engine RPM                              |
| `throttle`     | float | Throttle position (if supported by ECU) |
| `coolant_temp` | float | Engine coolant temperature              |
| `intake_temp`  | float | Intake air temperature                  |
| `fuel_level`   | float | Fuel level percentage                   |

> Note: OBD-II does NOT provide brake, steering, tyre temps, tyre pressures, or ABS/TC data. The coaching features that depend on these channels (braking analysis, trail braking, tyre management, corner-by-corner coaching) are **sim racing only**. For real racing, focus coaching on throttle smoothness, engine temp management, and fuel efficiency.

---

## 10. Final Checklist

Before considering the feature complete, verify:

- [ ] Corner detection works on at least 3 different track layouts (verify with ACC/AC/iRacing test data)
- [ ] All insight messages are beginner-friendly (no jargon without explanation)
- [ ] No analyzer crashes on missing data (e.g., first lap, no reference yet)
- [ ] Tyre analysis gracefully handles sims that don't provide tyre data
- [ ] Coach tab updates within 200ms of lap completion
- [ ] Corner map persists across sessions for the same track
- [ ] Personal bests persist across sessions
- [ ] The "Quick Win" always identifies the single highest-value improvement
- [ ] Trail braking explanations are shown only once per session (not repeated every lap)
- [ ] Session progress chart shows clear improvement trend
- [ ] Track map overlay doesn't break the existing track map functionality
- [ ] OBD-II mode shows a reduced Coach tab (throttle + engine coaching only, no brake/tyre)
- [ ] All unit tests pass
- [ ] No new dependencies beyond scipy.signal
