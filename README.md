# S1napse

A real-time telemetry dashboard for **sim racing** and **real racing**. Connects directly to your sim or to your car's OBD-II port via an ELM327 adapter, and displays live data, lap analysis, race strategy, post-session coaching, and a self-building track map.

Built around a violet/dark design system with two density modes — dense, glance-while-driving live tabs (Dashboard, Race, Strategy, Tyres, Coach) and roomy analysis tabs (Telemetry, Lap Analysis, Lap Comparison, Session, Replay).

---

## Download & Install (Beta — Windows)

### Step 1 — Download the installer

1. Open the [latest release](https://github.com/Par-python/s1napse/releases/latest).
2. Under **Assets**, download **`Synapse-Setup-<version>.exe`** (about 150–200 MB).

---

### Step 2 — Run the installer

1. Double-click `Synapse-Setup-<version>.exe`.
2. **Windows may show "Windows protected your PC."** Click **More info** → **Run anyway**. This is normal for an unsigned beta build; the warning will go away once SmartScreen has seen enough installs.
3. Pick a Start Menu group (default `Synapse`) and optionally a desktop shortcut, then finish the wizard.

> **Antivirus warning?** Some antivirus tools flag PyInstaller executables as suspicious. The app is safe — you can add it as an exception or check the source code in this repo.

Synapse will check for new beta releases on startup and show a small banner at the top of the window when one is available — click **Download** to jump straight to the release page.

To uninstall: **Settings → Apps → Synapse → Uninstall**.

---

### Step 3 — Choose your mode

When S1napse launches you'll see a welcome screen with two options:

#### Sim Racing

1. Select **SIM RACING** and click **NEXT**
2. Launch your sim first, then open S1napse
3. S1napse will **auto-detect** whichever sim is running
4. The status bar at the top will show **● CONNECTED** when it picks up data

| Sim                       | What to do                                                                                                                                                                            |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ACC**                   | Just launch the game — S1napse connects automatically                                                                                                                                 |
| **Assetto Corsa**         | Enable UDP telemetry in AC's settings: `Options → General → Enable Custom Shaders Patch` is not required — just go to `Options → General` and enable **UDP telemetry** on port `9996` |
| **iRacing**               | Launch iRacing, go to the track — S1napse connects automatically                                                                                                                      |
| **Le Mans Ultimate (LMU)**| One-time plugin install required (rF2 Shared Memory Plugin). See [docs/lmu-setup.md](docs/lmu-setup.md). After that, just launch the game — S1napse connects automatically.            |

#### Real Racing (ELM327 OBD-II)

1. Select **REAL RACING** and click **NEXT**
2. Choose your connection type — **WiFi** or **Bluetooth**
3. Enter your adapter's connection details (IP:port for WiFi, serial port for Bluetooth)
4. Click **CONNECT** — or use **DEMO MODE** to test without hardware
5. The real racing dashboard shows live speed, RPM, throttle, gear, fuel, and temperatures

> See [REAL_RACING_GUIDE.md](REAL_RACING_GUIDE.md) for full setup instructions, adapter recommendations, and troubleshooting.

---

## Supported Platforms

### Sim Racing

| Game                             | Windows |
| -------------------------------- | ------- |
| Assetto Corsa Competizione (ACC) | ✅      |
| Assetto Corsa (AC)               | ✅      |
| iRacing                          | ✅      |
| Le Mans Ultimate (LMU)           | ✅      |

### Real Racing

| Source                    | Windows | Mac |
| ------------------------- | ------- | --- |
| ELM327 OBD-II (WiFi)      | ✅      | ✅  |
| ELM327 OBD-II (Bluetooth) | ✅      | ✅  |

---

## What's inside

The app samples telemetry at 50 Hz in the background and renders the UI at ~5 Hz. A title bar at the top is always visible: brand, live source pill (with green dot when a reader is connected), session context (lap / stint / last lap), and the source/track/host/port controls.

### Dashboard

Selective gauges row — RevBar, throttle and brake PedalBars, SteeringBar — plus a 2×2 stat-card grid for Speed, Gear, Last lap, and Fuel.

### Telemetry Graphs

Rolling graphs for the current lap: speed, throttle/brake, steering, RPM, gear, ABS/TC. Math-channel side panel for user-defined formulas.

### Lap Analysis

Multi-panel view:

- **Sectors** — running lap timer + S1/S2/S3 splits vs your reference lap (green = faster, red = slower)
- **Track Map** — builds itself from real car coordinates as you drive. Color-coded by throttle (green) and braking (red). Saved automatically after each lap so it loads instantly next session.
- **Telemetry graphs** — distance-based speed, throttle, gear, RPM, steering for the current lap
- **Delta graph** — time gained/lost vs your reference lap at every point on track

### Race

Live, glance-while-driving layout in three columns plus a headline strip:

- **Headline** — current race position (P4/22 style) with the active strategy banner inline next to it
- **Pace column** — last lap time, lap-trend sparkline (last 12 laps with PB reference), S1/S2/S3 sector splits
- **Position column** — gap to rivals ahead/behind in seconds, ±3s gap-bar visualizer, per-lap gap-trend ("closing/opening +0.18s this lap"), pit window range from the strategy engine
- **Car column** — live tyre temps quad (cold/hot tinting), tyre stint laps + degradation projection, fuel remaining, stint summary (lap, average, best)

### Strategy

Headline strip on top + two columns:

- **Now** — pit window, fuel-save cost, rival watch (gap-jump pit detection), weather/track-temp watch
- **Plan** — tyre degradation projection (fits a slope to recent lap times — needs ≥3 laps), pit summary, fuel-save calculator (laps-to-go input), undercut/overcut calculator (pit-loss + pace-delta inputs)

The headline reads from `StrategyState.headline()` and surfaces the highest-priority active alert (rival pit, pit window open, weather change, etc.).

### Tyres

Per-corner TyreCard quad on the left, plus pressure / wear / IMO temp distribution panels on the right.

### Lap Comparison

Pick any two laps from your session and overlay them on the same graphs. See exactly where you gained or lost time.

### Session

Full lap table with times, sector splits, and validity flags. Export everything to CSV with one click.

### Replay

Scrub through any saved lap with playback controls, telemetry graphs, and a time-synced track-map cursor.

### Coach

Post-lap analysis: a "quick win" tip card, per-tyre temperature feedback, and a session-progress card with a lap-time sparkline and per-corner grade history. Driven by the LapCoach engine.

### Real Racing Dashboard

A dedicated single-page layout for real car telemetry via ELM327 OBD-II:

- **Speed, RPM, Gear** — large hero gauges front and center
- **Throttle** — live percentage with fill bar
- **Fuel level** — percentage remaining with fill bar
- **Coolant & intake temps** — engine temperature monitoring
- **Live graphs** — scrolling speed, throttle, and RPM traces (~10 seconds of history)
- **Manual lap trigger** — press the **LAP** button or **L** key to mark laps
- **Lap timer** — live running time and last lap display

> Standard OBD-II does not provide brake, steering, tyre, or ABS/TC data — these channels are only available in sim racing mode.

---

## Track Map

S1napsse builds the track map automatically — no pre-loaded layouts needed.

1. Load into any session on a new track
2. Complete the outlap (S1napsse skips it to avoid pit-exit noise)
3. Drive — the map builds in real time
4. Cross the finish line — the map saves automatically

On your next session at the same track it loads instantly. Track files are saved in a `tracks\` folder next to `S1napsse.exe`.

You can also press **⏺ REC** in the top bar to start/stop a recording manually.

---

## For Developers

Clone the repo and run from source:

```bash
pip install -r requirements.txt
python -m s1napse        # or: python s1napse.py
```

Run the test suite:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Build the EXE yourself:

```bash
pip install pyinstaller
pyinstaller Synapse.spec
# Output: dist/S1napsse.exe
```

**Project structure:**

```
acc-telemetry/
├── s1napse.py                     # Thin entry point
├── s1napse/                       # Application package
│   ├── __main__.py                # `python -m s1napse`
│   ├── app.py                     # Main window + render orchestration
│   ├── theme.py                   # Design tokens + QSS builder
│   ├── constants.py               # Channel colors + track constants
│   ├── readers/                   # ACC, AC-UDP, iRacing, LMU, ELM327 readers
│   ├── vendor/                    # Third-party libs vendored into the repo (MIT)
│   ├── coaching/                  # LapCoach, MathEngine, StrategyEngine
│   ├── widgets/
│   │   ├── primitives.py          # Card, Pill, Stat, Sparkline, GapBar
│   │   ├── title_bar.py           # Always-visible top strip
│   │   ├── tab_bar.py             # LiveTabBar (per-tab live-state dot)
│   │   ├── tabs/                  # Per-tab modules (race, dashboard, tyres, ...)
│   │   ├── strategy_tab.py        # Strategy tab (headline + 2-col)
│   │   ├── coach_tab.py           # Coach tab
│   │   └── ... (gauges, graphs, panels, track_map, etc.)
│   ├── tracks/                    # Auto-generated track JSON files
│   └── racelines/                 # Saved racelines
├── tests/                         # pytest test suite
├── installer/                     # Inno Setup installer script
├── tools/                         # Build helpers (build_installer.py, etc.)
├── docs/                          # User-facing documentation
├── Synapse.spec                   # PyInstaller build config
├── requirements.txt               # Runtime dependencies
├── requirements-dev.txt           # Test/dev dependencies
└── README.md
```

---

## Troubleshooting

**S1napsse shows DISCONNECTED**

- Make sure the sim is running and you are in a session (not the main menu)
- For AC, confirm UDP telemetry is enabled in game settings
- Try selecting the source manually from the **SOURCE** dropdown instead of Auto-Detect

**Track map is not building**

- The outlap is always skipped — drive one full lap first
- If the lap is invalid (track cut, penalty) the map pauses recording to stay clean

**The exe is being blocked by antivirus**

- This is a known false positive with PyInstaller-built apps
- Add `S1napsse.exe` as an exception in your antivirus, or build from source

---

## Notes

- ACC, iRacing, and Le Mans Ultimate use shared memory — S1napse must be running on the **same Windows PC** as the sim
- AC UDP works over a local network too (change the HOST field in the top bar)
- ELM327 OBD-II works on Windows and Mac via WiFi or Bluetooth — see [REAL_RACING_GUIDE.md](REAL_RACING_GUIDE.md)
- OBD-II polling is slower than sim telemetry (~2-4 Hz vs 20 Hz) — this is a hardware limitation, not a bug

---

## License

S1napse is licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0). See [LICENSE](LICENSE) for the full text.

In short: you are free to use, modify, and redistribute this software, but any modified version — including network-deployed versions — must be made available under the same license.

### Third-party components

This repository vendors the following third-party code, retained under its original license:

- **`s1napse/vendor/pyRfactor2SharedMemory/`** — Python bindings for the rFactor 2 Shared Memory Plugin. Copyright © 2021 Tony Whitley. Licensed under the MIT License (see `s1napse/vendor/pyRfactor2SharedMemory/License.txt`). Used by `s1napse/readers/lmu.py` to read Le Mans Ultimate telemetry. Source: <https://github.com/TonyWhitley/pyRfactor2SharedMemory>.
- **`pyaccsharedmemory`** — Python bindings for the Assetto Corsa Competizione Shared Memory API. Copyright © rrennoir. Licensed under the MIT License. Installed as a PyPI dependency (`requirements.txt`) and used by `s1napse/readers/acc.py` to read ACC telemetry. Source: <https://github.com/rrennoir/PyAccSharedMemory>.
- **`TUMFTM/racetrack-database`** — Open racetrack centerline and raceline dataset. Licensed under the GNU Lesser General Public License v3.0 (LGPL-3.0). Consumed offline by `tools/import_tracks.py` to generate the pre-built track JSON files shipped in `s1napse/tracks/`. Source: <https://github.com/TUMFTM/racetrack-database>.
