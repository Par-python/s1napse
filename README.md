# S1napse

A real-time telemetry dashboard for racing simulators. Connects directly to your sim and displays live car data, lap analysis, race strategy, and a self-building track map.

---

## Download & Install

### Step 1 — Download S1napse

1. Go to the [**Releases**](../../releases) page (top right of this GitHub page, or click the "Releases" link on the right sidebar)
2. Click the latest release (e.g. `v1.0.0`)
3. Under **Assets**, click **`S1napsse.exe`** to download it

> The file is about 150–200 MB. This is normal — it includes everything the app needs to run.

---

### Step 2 — Run it

1. Move `S1napsse.exe` to a folder of your choice (e.g. `Documents\S1napsse\`)
2. Double-click `S1napsse.exe`

> **Windows SmartScreen warning?** This is normal for unsigned apps.
> Click **"More info"** → **"Run anyway"** to proceed.

> **Antivirus warning?** Some antivirus tools flag PyInstaller executables as suspicious. The app is safe — you can add it as an exception or check the source code in this repo.

That's it. No Python, no installation, no setup.

---

### Step 3 — Connect to your sim

1. Launch your sim first, then open S1napsse
2. S1napsse will **auto-detect** whichever sim is running
3. The status bar at the top will show **● CONNECTED** when it picks up data

| Sim               | What to do                                                                                                                                                                            |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ACC**           | Just launch the game — S1napsse connects automatically                                                                                                                                 |
| **Assetto Corsa** | Enable UDP telemetry in AC's settings: `Options → General → Enable Custom Shaders Patch` is not required — just go to `Options → General` and enable **UDP telemetry** on port `9996` |
| **iRacing**       | Launch iRacing, go to the track — S1napsse connects automatically                                                                                                                      |

---

## Supported Games

| Game                             | Windows | Mac |
| -------------------------------- | ------- | --- |
| Assetto Corsa Competizione (ACC) | ✅      | ❌  |
| Assetto Corsa (AC)               | ✅      | ❌  |
| iRacing                          | ✅      | ❌  |

---

## What's inside

### Dashboard

Live car data at 20 Hz — speed, gear, RPM, throttle, brake, steering wheel, tyre temps & pressures, fuel remaining, lap time, ABS/TC activity.

### Telemetry Graphs

Rolling graphs for the current lap: speed, throttle/brake, steering, RPM, gear, ABS/TC.

### Lap Analysis

Three-panel view:

- **Sectors** — running lap timer + S1/S2/S3 splits vs your reference lap (green = faster, red = slower)
- **Track Map** — builds itself from real car coordinates as you drive. Color-coded by throttle (green) and braking (red). Saved automatically after each lap so it loads instantly next session.
- **Telemetry graphs** — distance-based speed, throttle, gear, RPM, steering for the current lap
- **Delta graph** — time gained/lost vs your reference lap at every point on track

### Race Tab

Race-specific data: position, gap to car ahead/behind, tyre compound & stint age, pit window recommendation, lap time trend, undercut/overcut calculator, fuel save calculator.

### Tyres Tab

Per-corner tyre temperatures, pressures, and brake temperatures.

### Lap Comparison

Pick any two laps from your session and overlay them on the same graphs. See exactly where you gained or lost time.

### Session Tab

Full lap table with times, sector splits, and validity flags. Export everything to CSV with one click.

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
pip install PyQt6 matplotlib pyaccsharedmemory irsdk
python test-listener.py
```

Build the EXE yourself:

```bash
pip install pyinstaller
pyinstaller S1napsse.spec
# Output: dist/S1napsse.exe
```

**Project structure:**

```
S1napsse/
├── test-listener.py   # Main application
├── S1napsse.spec       # PyInstaller build config
├── requirements.txt   # Python dependencies
├── tracks/            # Auto-generated track JSON files
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

- ACC and iRacing use shared memory — S1napsse must be running on the **same Windows PC** as the sim
- AC UDP works over a local network too (change the HOST field in the top bar)
