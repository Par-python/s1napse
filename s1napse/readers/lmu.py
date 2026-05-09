"""Le Mans Ultimate via the rFactor 2 Shared Memory Plugin.

Uses the vendored pyRfactor2SharedMemory bindings under
``s1napse/vendor/pyRfactor2SharedMemory/`` (the upstream library is not on
PyPI). Requires that ``rFactor2SharedMemoryMapPlugin64.dll`` is installed
in LMU's Plugins folder and enabled in ``CustomPluginVariables.JSON``
(note the leading-space ' Enabled' key — required by the game).
"""

from .base import TelemetryReader


def _map_session_type(code: int) -> str:
    """rF2 mSession codes → ACC-style labels.
    0=test day, 1-4=practice, 5-8=qualify, 9=warmup, 10-13=race.
    """
    if 5 <= code <= 8:
        return 'QUALIFY'
    if 10 <= code <= 13:
        return 'RACE'
    return 'PRACTICE'


class LMUReader(TelemetryReader):
    """Le Mans Ultimate via the rFactor 2 Shared Memory Plugin."""

    def __init__(self):
        self._last_read_ok = False
        self.info = None
        self._cbytestring = None
        try:
            from ..vendor.pyRfactor2SharedMemory.sharedMemoryAPI import (
                Cbytestring2Python,
                SimInfoAPI,
            )
            self.info = SimInfoAPI()
            self._cbytestring = Cbytestring2Python
            self.available = True
        except Exception as e:
            print(f"LMU Reader initialization failed: {e}")
            print(
                "Install rFactor2SharedMemoryMapPlugin64.dll into LMU's "
                "Plugins folder and enable it in CustomPluginVariables.JSON. "
                "Also ensure psutil is installed (pip install psutil)."
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

            veh = scoring.mVehicles[0]
            info = scoring.mScoringInfo

            decode = self._cbytestring
            car_name   = decode(veh.mVehicleName)   if veh.mVehicleName   else ''
            track_name = decode(info.mTrackName)    if info.mTrackName    else ''
            compound   = decode(telem.mFrontTireCompoundName) \
                         if telem.mFrontTireCompoundName else ''

            current_time_ms = (info.mCurrentET - veh.mLapStartET) * 1000.0
            track_len = float(info.mLapDist) or 1.0
            lap_pct = float(veh.mLapDist) / track_len

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
                'lap_time':       float(veh.mLastLapTime),
                'position':       int(veh.mPlace),
                'car_name':       car_name,
                'track_name':     track_name,
                'lap_count':      int(veh.mTotalLaps),
                'current_time':   current_time_ms,
                'lap_dist_pct':   lap_pct,
                'world_x':        float(veh.mPos.x),
                'world_z':        float(veh.mPos.z),
                'lap_valid':      bool(veh.mCountLapFlag),
                'is_in_pit_lane': bool(veh.mInPits),
                'tyre_compound':  compound,
                'air_temp':       float(info.mAmbientTemp),
                'road_temp':      float(info.mTrackTemp),
                'session_type':   _map_session_type(int(info.mSession)),
                'estimated_lap':  float(veh.mBestLapTime) * 1000.0,
                'gap_ahead':      0,
                'gap_behind':     0,
                'stint_time_left': 0,
                'delta_lap_time': 0,
            }
        except Exception as e:
            print(f"LMU read error: {e}")
            self._last_read_ok = False
            return None

    def is_connected(self):
        if not self.available:
            return False
        if self._last_read_ok:
            return True
        # First-time probe: try a read so auto-detect can pick us up
        # on the first polling cycle instead of the second.
        try:
            return self.read() is not None
        except Exception:
            return False
