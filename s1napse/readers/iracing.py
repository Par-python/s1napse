"""iRacing telemetry via irsdk shared memory (Windows only)."""

from .base import TelemetryReader


class IRacingReader(TelemetryReader):
    """iRacing telemetry via irsdk shared memory (Windows only).
    Install: pip install irsdk
    """

    def __init__(self):
        self.ir = None
        self.available = False
        try:
            import irsdk  # type: ignore[import]
            self.ir = irsdk.IRSDK()
            self.ir.startup()
            self.available = True
        except Exception as e:
            print(f"iRacing SDK init failed (Windows + iRacing required): {e}")

    def read(self):
        if not self.available or self.ir is None:
            return None
        try:
            if not (self.ir.is_initialized and self.ir.is_connected):
                return None
            self.ir.freeze_var_buffer_latest()

            speed_ms = self.ir['Speed'] or 0.0
            rpm      = self.ir['RPM']   or 0.0
            gear_raw = self.ir['Gear']  or 0
            throttle = (self.ir['Throttle'] or 0.0) * 100.0
            brake    = (self.ir['Brake']    or 0.0) * 100.0
            steer    = self.ir['SteeringWheelAngle'] or 0.0
            fuel     = self.ir['FuelLevel']    or 0.0
            fuel_pct = self.ir['FuelLevelPct'] or 0.0
            lap      = self.ir['Lap']              or 0
            cur_s    = self.ir['LapCurrentLapTime'] or 0.0
            last_lap = self.ir['LapLastLapTime']    or 0.0
            lap_pct  = self.ir['LapDistPct']        or 0.0

            try:
                position = int(self.ir['PlayerCarPosition'] or 0)
            except Exception:
                position = 0

            max_rpm = 10000.0
            try:
                max_rpm = float(self.ir['DriverInfo']['DriverCarRedLine'] or 10000)
            except Exception:
                pass

            max_fuel = (fuel / fuel_pct) if fuel_pct > 0.001 else 100.0

            car_name = 'iRacing Car'
            try:
                idx = self.ir['PlayerCarIdx'] or 0
                car_name = self.ir['DriverInfo']['Drivers'][idx]['CarScreenName']
            except Exception:
                pass

            track_name = 'iRacing Track'
            try:
                track_name = self.ir['WeekendInfo']['TrackName']
            except Exception:
                pass

            # Normalise to app convention: 0=R, 1=N, 2+=1st,2nd,...
            if gear_raw < 0:
                gear = 0
            elif gear_raw == 0:
                gear = 1
            else:
                gear = gear_raw + 1

            # World position for track recording
            world_x = world_z = 0.0
            try:
                player_idx = int(self.ir['PlayerCarIdx'] or 0)
                car_x = self.ir['CarIdxX']
                car_z = self.ir['CarIdxZ']
                if car_x and car_z:
                    world_x = float(car_x[player_idx])
                    world_z = float(car_z[player_idx])
            except Exception:
                pass

            return {
                'speed':        speed_ms * 3.6,
                'rpm':          rpm,
                'max_rpm':      max_rpm,
                'gear':         gear,
                'throttle':     throttle,
                'brake':        brake,
                'steer_angle':  steer,
                'abs':          0.0,
                'tc':           0.0,
                'fuel':         fuel,
                'max_fuel':     max_fuel,
                'lap_time':     last_lap,
                'position':     position,
                'car_name':     car_name,
                'track_name':   track_name,
                'lap_count':    lap,
                'current_time': cur_s * 1000.0,
                'lap_dist_pct': lap_pct,
                'world_x':      world_x,
                'world_z':      world_z,
                'tyre_temp':     self._ir_tyre_temps(),
                'tyre_pressure': self._ir_tyre_pressures(),
                'brake_temp':    [0.0, 0.0, 0.0, 0.0],
                'tyre_compound': '',
                'air_temp':  float(self.ir.get('AirTemp') or 0.0),
                'road_temp': float(self.ir.get('TrackTemp') or 0.0),
                'tyre_wear': [
                    float(self.ir.get('LFwearM') or 0.0) * 100,
                    float(self.ir.get('RFwearM') or 0.0) * 100,
                    float(self.ir.get('LRwearM') or 0.0) * 100,
                    float(self.ir.get('RRwearM') or 0.0) * 100,
                ],
                'brake_bias': 0.0,
            }
        except Exception as e:
            print(f"iRacing read error: {e}")
            return None

    def _ir_tyre_temps(self):
        """Return [FL, FR, RL, RR] tyre centre temps in C, or zeros."""
        try:
            fl = float(self.ir.get('LFtempCM') or 0.0)
            fr = float(self.ir.get('RFtempCM') or 0.0)
            rl = float(self.ir.get('LRtempCM') or 0.0)
            rr = float(self.ir.get('RRtempCM') or 0.0)
            return [fl, fr, rl, rr]
        except Exception:
            return [0.0, 0.0, 0.0, 0.0]

    def _ir_tyre_pressures(self):
        """Return [FL, FR, RL, RR] tyre pressures in PSI, or zeros."""
        try:
            fl = float(self.ir.get('LFpressure') or 0.0)
            fr = float(self.ir.get('RFpressure') or 0.0)
            rl = float(self.ir.get('LRpressure') or 0.0)
            rr = float(self.ir.get('RRpressure') or 0.0)
            return [fl, fr, rl, rr]
        except Exception:
            return [0.0, 0.0, 0.0, 0.0]

    def is_connected(self):
        if not self.available or self.ir is None:
            return False
        try:
            return bool(self.ir.is_initialized and self.ir.is_connected)
        except Exception:
            return False

    def shutdown(self):
        if self.ir:
            try:
                self.ir.shutdown()
            except Exception:
                pass
