"""Assetto Corsa Competizione via pyaccsharedmemory (Windows shared memory)."""

from .base import TelemetryReader
from ..utils import _safe_list


class ACCReader(TelemetryReader):
    """Assetto Corsa Competizione via pyaccsharedmemory (Windows shared memory)."""

    def __init__(self):
        self._last_read_ok = False
        try:
            from pyaccsharedmemory import accSharedMemory
            self.asm = accSharedMemory()
            self.available = True
        except Exception as e:
            print(f"ACC Reader initialization failed: {e}")
            print("Install with: pip install pyaccsharedmemory")
            self.available = False

    def read(self):
        if not self.available:
            self._last_read_ok = False
            return None
        try:
            sm = self.asm.read_shared_memory()
            if sm is None:
                self._last_read_ok = False
                return None
            self._last_read_ok = True
            return {
                'speed': sm.Physics.speed_kmh,
                'rpm': sm.Physics.rpm,
                'max_rpm': sm.Static.max_rpm,
                'gear': sm.Physics.gear - 1,
                'throttle': sm.Physics.gas * 100,
                'brake': sm.Physics.brake * 100,
                'steer_angle': sm.Physics.steer_angle,
                'abs': sm.Physics.abs,
                'tc': sm.Physics.tc,
                'fuel': sm.Physics.fuel,
                'max_fuel': sm.Static.max_fuel,
                'lap_time': sm.Graphics.last_time / 1000,
                'position': sm.Graphics.position,
                'car_name': sm.Static.car_model,
                'track_name': sm.Static.track,
                'lap_count': sm.Graphics.completed_lap,
                'current_time': sm.Graphics.current_time,
                'lap_dist_pct': sm.Graphics.normalized_car_position,
                'world_x': sm.Graphics.car_coordinates[0].x,
                'world_z': sm.Graphics.car_coordinates[0].z,
                'lap_valid': sm.Graphics.is_valid_lap,
                'is_in_pit_lane': sm.Graphics.is_in_pit_lane,
                'tyre_temp': [
                    sm.Physics.tyre_core_temp.front_left,
                    sm.Physics.tyre_core_temp.front_right,
                    sm.Physics.tyre_core_temp.rear_left,
                    sm.Physics.tyre_core_temp.rear_right,
                ],
                'tyre_pressure': [
                    sm.Physics.wheel_pressure.front_left,
                    sm.Physics.wheel_pressure.front_right,
                    sm.Physics.wheel_pressure.rear_left,
                    sm.Physics.wheel_pressure.rear_right,
                ],
                'brake_temp': [
                    sm.Physics.brake_temp.front_left,
                    sm.Physics.brake_temp.front_right,
                    sm.Physics.brake_temp.rear_left,
                    sm.Physics.brake_temp.rear_right,
                ],
                'tyre_compound': sm.Graphics.tyre_compound,
                'air_temp':  sm.Physics.air_temp,
                'road_temp': sm.Physics.road_temp,
                'session_type':    sm.Graphics.session_type.name,
                'gap_ahead':       getattr(sm.Graphics, 'gap_ahead', 0) or 0,
                'gap_behind':      getattr(sm.Graphics, 'gap_behind', 0) or 0,
                'stint_time_left': getattr(sm.Graphics, 'driver_stint_time_left', 0) or 0,
                'delta_lap_time':  getattr(sm.Graphics, 'delta_lap_time', 0) or 0,
                'estimated_lap':   getattr(sm.Graphics, 'estimated_lap_time', 0) or 0,
                'tyre_wear': _safe_list(
                    getattr(sm.Physics, 'tyre_wear', None), 4),
                'brake_bias': float(getattr(sm.Physics, 'brake_bias', 0.0) or 0.0),
            }
        except Exception as e:
            print(f"ACC read error: {e}")
            self._last_read_ok = False
            return None

    def is_connected(self):
        if not self.available:
            return False
        if self._last_read_ok:
            return True
        # First-time probe
        try:
            sm = self.asm.read_shared_memory()
            self._last_read_ok = sm is not None
            return self._last_read_ok
        except Exception:
            return False
