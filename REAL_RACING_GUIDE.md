# s1napse — Real Racing Mode Guide

Real racing mode connects to your car's OBD-II diagnostic port via an ELM327 adapter,
streaming live engine telemetry directly into s1napse.

---

## 1. What You Need

- **ELM327 OBD-II adapter** — Bluetooth or WiFi version (v1.5 or newer recommended)
- **A vehicle with an OBD-II port** — all cars sold in North America since 1996 and Europe since 2001 have one
- **A laptop or device** running s1napse

### Where is the OBD-II port?

The port is usually located under the dashboard on the driver's side, near the steering
column. Check your vehicle's manual if you can't find it — common spots include below the
steering wheel, near the fuse box, or behind a small panel to the left of the pedals.

### Recommended adapters

Use a **genuine** ELM327 adapter. Cheap clones may not support all PIDs or may drop
connections. Trusted brands include OBDLink, Vgate, and BAFX Products.

---

## 2. Connecting the Adapter

### Step 1: Plug in the adapter

Insert the ELM327 adapter into your car's OBD-II port. Turn the ignition to **ON**
(engine can be off or running). The adapter's LED should start blinking.

### Step 2a: Bluetooth setup

1. Open your laptop/phone's Bluetooth settings
2. Scan for new devices — the adapter shows up as `OBDII`, `ELM327`, `Vgate`, or similar
3. Pair with PIN code **1234** (or **0000** on some adapters)
4. Note the serial port assigned:
   - **macOS / Linux**: `/dev/rfcomm0` or `/dev/tty.OBD...`
   - **Windows**: `COM3`, `COM4`, etc. — check Device Manager > Ports

### Step 2b: WiFi setup

1. The adapter creates its own WiFi hotspot (e.g. `WiFi_OBDII`, `OBDLink`)
2. Connect your laptop to that WiFi network
3. Default connection: **192.168.0.10** port **35000**
   (some adapters use `192.168.1.10` — check your adapter's manual)

> **Note:** While connected to the adapter's WiFi, your laptop won't have internet access.

---

## 3. Using the App

### Launch and connect

1. Open **s1napse**
2. On the welcome screen, select **REAL RACING**
3. Click **NEXT** — you'll see the OBD-II setup page
4. Choose your connection type:
   - **WiFi**: Enter the adapter's IP address and port
   - **Bluetooth / Serial**: Enter the serial port path
5. Click **CONNECT**
6. If successful, the app transitions to the main dashboard

### What data is available?

| Channel          | Available | Source          |
|------------------|-----------|-----------------|
| Speed            | Yes       | OBD-II PID 0x0D |
| RPM              | Yes       | OBD-II PID 0x0C |
| Throttle         | Yes       | OBD-II PID 0x11 |
| Engine temp      | Yes       | OBD-II PID 0x05 |
| Intake air temp  | Yes       | OBD-II PID 0x0F |
| Fuel level       | Yes       | OBD-II PID 0x2F |
| Gear (estimated) | Yes       | Speed/RPM ratio  |
| Brake            | No        | Not in standard OBD-II |
| Steering angle   | No        | Not in standard OBD-II |
| Tyre temps       | No        | Not in standard OBD-II |
| Tyre pressures   | No        | Not in standard OBD-II |
| ABS / TC         | No        | Not in standard OBD-II |

Unavailable channels display as dashes or zeros on the dashboard.

### Update rate

OBD-II polling is slower than sim telemetry — expect updates at **2-4 Hz** (every
250-500 ms). This is normal and sufficient for lap analysis.

---

## 4. Recording Laps

OBD-II cannot automatically detect when you cross the start/finish line, so laps
are triggered **manually**.

### How to mark a lap

- Click the green **LAP** button in the connection strip, OR
- Press the **L** key on your keyboard

Each press completes the current lap and starts the next one. The app records:
- Lap time
- All telemetry channels over the lap
- Approximate distance (integrated from speed)

### Tips for accurate laps

- Pick a clear reference point on track (start/finish line, a cone, a landmark)
- Press L at the same point each lap for consistent timing
- The first lap establishes the track length estimate — subsequent laps use this
  for distance-based analysis

### Exporting lap data

- Use **EXPORT JSON** in the Telemetry Graphs tab to save a lap file
- This JSON can be imported in the **REPLAY** tab for post-session review

---

## 5. Troubleshooting

### "Connection failed"

- Ensure the adapter is plugged in and the LED is blinking
- Check that the ignition is ON (not just accessory mode)
- Verify the IP/port (WiFi) or serial port path (Bluetooth) is correct
- Try disconnecting and reconnecting the adapter
- On Bluetooth: ensure the adapter is paired in your OS settings first

### No data showing after connection

- Some cars take a few seconds to start responding to PID queries
- Try turning the engine on (not just ignition)
- Some older vehicles may not support all standard PIDs

### Slow or choppy updates

- This is normal — OBD-II is limited to ~2-4 Hz with 6 parameters
- WiFi adapters tend to be slightly faster than Bluetooth
- Ensure no other OBD apps are connected simultaneously

### Gear estimation seems wrong

The gear is estimated from the speed/RPM ratio using generic thresholds. Different
vehicles have different gear ratios, so the estimate may be off by one gear in
some situations. This does not affect other telemetry channels.

### WiFi adapter: can't connect

- Make sure your laptop is connected to the adapter's WiFi network (not your home WiFi)
- Some firewalls block the connection — try disabling the firewall temporarily
- Default IP is usually `192.168.0.10:35000` but check your adapter's documentation

---

## 6. Wireless Range

- **Bluetooth adapters**: 5-15 meters (16-50 feet) typical range
- **WiFi adapters**: 10-30 meters (30-100 feet) under ideal conditions

Both work well for in-car use since the adapter sits in the OBD-II port and your
laptop is typically on the passenger seat or mounted on the dashboard.
