# Le Mans Ultimate Setup

S1napse reads LMU telemetry through the rFactor 2 Shared Memory Plugin.
Studio 397 ships LMU on the rF2 engine, so the same plugin works for both
games.

## 1. Install the plugin

1. Download `rFactor2SharedMemoryMapPlugin64.dll` from the
   [TheIronWolfModding/rF2SharedMemoryMapPlugin releases page](https://github.com/TheIronWolfModding/rF2SharedMemoryMapPlugin/releases).
2. Copy the DLL into LMU's plugin folder, typically:
   `<Steam>/steamapps/common/Le Mans Ultimate/Plugins/`
3. Open `<Steam>/steamapps/common/Le Mans Ultimate/UserData/player/CustomPluginVariables.JSON`
   in a text editor.
4. Find the `"rFactor2SharedMemoryMapPlugin64.dll"` entry (or add it if
   missing) and ensure it has:
   ```json
   "rFactor2SharedMemoryMapPlugin64.dll": {
       " Enabled": 1
   }
   ```
   **Note the leading space before `Enabled`** — this is required by the
   game and is not a typo.

## 2. Python dependencies

The rF2 Python bindings (`pyRfactor2SharedMemory`) are not published on
PyPI, so they are vendored into this repo at
`s1napse/vendor/pyRfactor2SharedMemory/` (MIT licensed, copied verbatim
from [TonyWhitley's repo](https://github.com/TonyWhitley/pyRfactor2SharedMemory)).
You do not need to install them separately.

The only extra runtime dep is `psutil`, already pinned in
`requirements.txt`. If you have already run
`pip install -r requirements.txt`, you are done.

## 3. Verify

1. Launch LMU and start a session (Practice is fine).
2. Launch S1napse.
3. In the source dropdown, select `LMU` (or leave on `Auto-Detect`).
4. The connection indicator should turn green and show `CONNECTED · LMU`.

## Known caveats

- **Online races may restrict telemetry.** Some multiplayer modes zero out
  physics fields as an anti-cheat measure. If the indicator says connected
  but speed/RPM are stuck at zero during driving, that is the cause —
  switch to single-player or a non-restricted server to confirm.
- **Plugin install can be silent.** If you copy the DLL but forget the
  `CustomPluginVariables.JSON` step (or miss the leading space in
  `" Enabled"`), the plugin loads but does not publish. S1napse will read
  zeros.
- **Paid DLC content works.** The plugin reads telemetry for whatever car
  and track LMU is currently simulating. It is not a content unlock — you
  still need to own the DLC to drive that car, but if you can drive it,
  S1napse can read it.
- **`estimated_lap` is the session best, not a live prediction.** ACC
  exposes a rolling estimate that updates mid-lap; rF2 does not, so the
  LMU reader reports `mBestLapTime` instead. Expect this field to read
  zero until the first lap is complete, then stay static until a new
  best is set.
