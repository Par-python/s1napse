"""Le Mans Ultimate via the rFactor 2 Shared Memory Plugin.

Requires:
    - pip install pyRfactor2SharedMemory
    - rFactor2SharedMemoryMapPlugin64.dll installed in LMU's Plugins folder
      and enabled in CustomPluginVariables.JSON (note the leading-space
      ' Enabled' key — required by the game).
"""

from .base import TelemetryReader


class LMUReader(TelemetryReader):
    """Le Mans Ultimate via the rFactor 2 Shared Memory Plugin."""

    def __init__(self):
        self._last_read_ok = False
        self.info = None
        self._cbytestring = None
        try:
            from pyRfactor2SharedMemory.sharedMemoryAPI import (
                Cbytestring2Python,
                SimInfoAPI,
            )
            self.info = SimInfoAPI()
            self._cbytestring = Cbytestring2Python
            self.available = True
        except Exception as e:
            print(f"LMU Reader initialization failed: {e}")
            print("Install with: pip install pyRfactor2SharedMemory")
            print(
                "Also: install rFactor2SharedMemoryMapPlugin64.dll into "
                "LMU's Plugins folder and enable it in CustomPluginVariables.JSON"
            )
            self.available = False

    def read(self):
        if not self.available:
            self._last_read_ok = False
            return None
        try:
            telem = self.info.playerTelemetry()
            scoring = self.info.playerScoring()
            if telem is None or scoring is None:
                self._last_read_ok = False
                return None

            # Speed: |mLocalVel| in m/s → km/h
            v = telem.mLocalVel
            speed_ms = (v.x * v.x + v.y * v.y + v.z * v.z) ** 0.5
            speed_kmh = speed_ms * 3.6

            # Gear: rF2 (-1=R, 0=N, 1+=fwd) → ACC (0=R, 1=N, 2+=fwd)
            gear = telem.mGear + 1

            wheels = telem.mWheels
            tyre_temp = [float(w.mTireCarcassTemperature) - 273.15 for w in wheels]
            tyre_pressure = [float(w.mPressure) for w in wheels]
            brake_temp = [float(w.mBrakeTemp) - 273.15 for w in wheels]
            tyre_wear = [float(w.mWear) * 100.0 for w in wheels]

            self._last_read_ok = True
            return {
                'speed':       speed_kmh,
                'rpm':         telem.mEngineRPM,
                'max_rpm':     telem.mEngineMaxRPM,
                'gear':        gear,
                'throttle':    telem.mUnfilteredThrottle * 100.0,
                'brake':       telem.mUnfilteredBrake * 100.0,
                'steer_angle': telem.mUnfilteredSteering,
                'abs':         0.0,
                'tc':          0.0,
                'fuel':        telem.mFuel,
                'max_fuel':    telem.mFuelCapacity,
                'brake_bias':  float(telem.mRearBrakeBias),
                'tyre_temp':     tyre_temp,
                'tyre_pressure': tyre_pressure,
                'brake_temp':    brake_temp,
                'tyre_wear':     tyre_wear,
            }
        except Exception as e:
            print(f"LMU read error: {e}")
            self._last_read_ok = False
            return None

    def is_connected(self):
        if not self.available:
            return False
        return self._last_read_ok
