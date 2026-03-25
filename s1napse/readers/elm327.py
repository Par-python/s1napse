"""Real car telemetry via ELM327 OBD-II adapter (WiFi or Bluetooth/serial)."""

import threading
import time
import math
import random

from .base import TelemetryReader


class ELM327Reader(TelemetryReader):
    """Real car telemetry via ELM327 OBD-II adapter (WiFi or Bluetooth/serial)."""

    def __init__(self, connection_string: str = '', simulate: bool = False):
        self.connection_string = connection_string
        self._simulate = simulate
        self.obd_connection = None
        self.connected = False
        self.running = False
        self.poll_thread = None
        self.latest_data = None
        self._lock = threading.Lock()

        # Internal lap timing
        self._lap_count = 0
        self._lap_start_time: float | None = None
        self._last_lap_time_s: float = 0.0
        self._session_start_time: float | None = None

        # Speed-integrated distance for approximate lap_dist_pct
        self._cum_distance_m: float = 0.0
        self._distance_at_lap_start: float = 0.0
        self._lap_length_estimate: float = 0.0
        self._last_poll_time: float | None = None

    # ---- connection -------------------------------------------------------

    def connect(self) -> bool:
        if self._simulate:
            self.connected = True
            now = time.monotonic()
            self._session_start_time = now
            self._lap_start_time = now
            self._last_poll_time = now
            self.running = True
            self.poll_thread = threading.Thread(target=self._sim_poll_loop, daemon=True)
            self.poll_thread.start()
            return True
        try:
            import obd
            cs = self.connection_string.strip()
            if ':' in cs and not cs.startswith('/'):
                self.obd_connection = obd.OBD(portstr=cs, fast=False)
            else:
                self.obd_connection = obd.OBD(portstr=cs or None, fast=False)

            if self.obd_connection.is_connected():
                self.connected = True
                now = time.monotonic()
                self._session_start_time = now
                self._lap_start_time = now
                self._last_poll_time = now
                self.running = True
                self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
                self.poll_thread.start()
                return True
        except Exception as e:
            print(f'ELM327 connection error: {e}')
        return False

    def disconnect(self):
        self.running = False
        if self.obd_connection:
            try:
                self.obd_connection.close()
            except Exception:
                pass
        self.connected = False

    # ---- TelemetryReader interface ----------------------------------------

    def read(self):
        with self._lock:
            return self.latest_data

    def is_connected(self):
        if self._simulate:
            return self.connected
        if not self.connected or self.obd_connection is None:
            return False
        try:
            return self.obd_connection.is_connected()
        except Exception:
            return False

    # ---- manual lap trigger -----------------------------------------------

    def trigger_lap(self):
        now = time.monotonic()
        if self._lap_start_time is not None:
            self._last_lap_time_s = now - self._lap_start_time
        self._lap_count += 1
        self._lap_length_estimate = self._cum_distance_m - self._distance_at_lap_start
        self._distance_at_lap_start = self._cum_distance_m
        self._lap_start_time = now

    # ---- background polling -----------------------------------------------

    def _query_value(self, command, default=0.0):
        try:
            resp = self.obd_connection.query(command)
            if resp and not resp.is_null():
                return float(resp.value.magnitude)
            return default
        except Exception:
            return default

    def _estimate_gear(self, speed_kmh: float, rpm: float) -> int:
        if rpm < 100 or speed_kmh < 2:
            return 1  # Neutral
        ratio = rpm / (speed_kmh / 3.6)  # rpm per m/s
        if ratio > 200:  return 2   # 1st
        if ratio > 130:  return 3   # 2nd
        if ratio > 90:   return 4   # 3rd
        if ratio > 65:   return 5   # 4th
        if ratio > 50:   return 6   # 5th
        return 7                    # 6th

    # ---- simulation loop (no adapter needed) ------------------------------

    def _sim_poll_loop(self):
        """Generate realistic fake OBD-II data for testing without hardware."""
        _t0 = time.monotonic()
        _fuel = 72.0
        while self.running:
            try:
                now = time.monotonic()
                dt = now - self._last_poll_time if self._last_poll_time else 0.05
                self._last_poll_time = now
                elapsed = now - _t0

                # Simulate a car doing laps: oscillating speed with acceleration/braking
                phase = (elapsed % 90.0) / 90.0  # 90-second lap cycle
                if phase < 0.15:
                    speed = 40 + phase / 0.15 * 120
                    throttle = 85 + random.random() * 15
                elif phase < 0.45:
                    speed = 160 + 30 * math.sin(phase * 20) + random.random() * 5
                    throttle = 70 + random.random() * 30
                elif phase < 0.55:
                    bp = (phase - 0.45) / 0.10
                    speed = 190 - bp * 130
                    throttle = max(0, 10 - bp * 15)
                elif phase < 0.70:
                    speed = 60 + 30 * math.sin((phase - 0.55) * 40)
                    throttle = 30 + random.random() * 30
                elif phase < 0.80:
                    ap = (phase - 0.70) / 0.10
                    speed = 70 + ap * 100
                    throttle = 75 + random.random() * 25
                else:
                    speed = 170 - (phase - 0.80) / 0.20 * 80
                    throttle = 20 + random.random() * 30

                speed = max(5, speed + random.gauss(0, 2))
                throttle = max(0, min(100, throttle))

                if speed < 60:
                    rpm = speed / 60 * 4000 + 2000
                elif speed < 120:
                    rpm = (speed - 60) / 60 * 3500 + 3000
                else:
                    rpm = (speed - 120) / 80 * 2500 + 4500
                rpm = max(800, min(7500, rpm + random.gauss(0, 50)))

                gear = self._estimate_gear(speed, rpm)
                _fuel = max(0, _fuel - 0.00005 * dt * speed)
                coolant = 88 + random.gauss(0, 1.5)
                intake = 32 + random.gauss(0, 1)

                self._cum_distance_m += (speed / 3.6) * dt
                lap_dist_m = self._cum_distance_m - self._distance_at_lap_start
                if self._lap_length_estimate > 0:
                    lap_dist_pct = min(1.0, lap_dist_m / self._lap_length_estimate)
                else:
                    lap_dist_pct = 0.0

                current_time_ms = int((now - self._lap_start_time) * 1000) \
                    if self._lap_start_time else 0

                data = {
                    'speed':           round(speed, 1),
                    'rpm':             round(rpm, 0),
                    'max_rpm':         7500.0,
                    'gear':            gear,
                    'throttle':        round(throttle, 1),
                    'brake':           0.0,
                    'steer_angle':     0.0,
                    'abs':             0.0,
                    'tc':              0.0,
                    'fuel':            round(_fuel, 1),
                    'max_fuel':        100.0,
                    'lap_time':        self._last_lap_time_s,
                    'position':        0,
                    'car_name':        'OBD-II Demo',
                    'track_name':      'Demo Track',
                    'lap_count':       self._lap_count,
                    'current_time':    current_time_ms,
                    'lap_dist_pct':    lap_dist_pct,
                    'world_x':         0.0,
                    'world_z':         0.0,
                    'lap_valid':       True,
                    'is_in_pit_lane':  False,
                    'tyre_temp':       [0.0, 0.0, 0.0, 0.0],
                    'tyre_pressure':   [0.0, 0.0, 0.0, 0.0],
                    'brake_temp':      [0.0, 0.0, 0.0, 0.0],
                    'tyre_wear':       [0.0, 0.0, 0.0, 0.0],
                    'tyre_compound':   '',
                    'air_temp':        round(intake, 1),
                    'road_temp':       round(coolant, 1),
                    'brake_bias':      0.0,
                    'gap_ahead':       0,
                    'gap_behind':      0,
                    'delta_lap_time':  0,
                    'estimated_lap':   0,
                    'stint_time_left': 0,
                    'session_type':    'PRACTICE',
                }

                with self._lock:
                    self.latest_data = data

                time.sleep(0.05)  # ~20 Hz simulated polling

            except Exception as e:
                print(f'ELM327 sim error: {e}')
                time.sleep(0.5)

    # ---- real OBD polling -------------------------------------------------

    def _poll_loop(self):
        import obd
        while self.running:
            try:
                if not self.obd_connection or not self.obd_connection.is_connected():
                    time.sleep(1.0)
                    continue

                speed     = self._query_value(obd.commands.SPEED, 0.0)
                rpm       = self._query_value(obd.commands.RPM, 0.0)
                throttle  = self._query_value(obd.commands.THROTTLE_POS, 0.0)
                coolant_t = self._query_value(obd.commands.COOLANT_TEMP, 0.0)
                intake_t  = self._query_value(obd.commands.INTAKE_TEMP, 0.0)
                fuel_lvl  = self._query_value(obd.commands.FUEL_LEVEL, 0.0)

                now = time.monotonic()
                dt = now - self._last_poll_time if self._last_poll_time else 0.0
                self._last_poll_time = now

                self._cum_distance_m += (speed / 3.6) * dt
                lap_dist_m = self._cum_distance_m - self._distance_at_lap_start

                if self._lap_length_estimate > 0:
                    lap_dist_pct = min(1.0, lap_dist_m / self._lap_length_estimate)
                else:
                    lap_dist_pct = 0.0

                current_time_ms = int((now - self._lap_start_time) * 1000) \
                    if self._lap_start_time else 0

                data = {
                    'speed':           speed,
                    'rpm':             rpm,
                    'max_rpm':         7000.0,
                    'gear':            self._estimate_gear(speed, rpm),
                    'throttle':        throttle,
                    'brake':           0.0,
                    'steer_angle':     0.0,
                    'abs':             0.0,
                    'tc':              0.0,
                    'fuel':            fuel_lvl,
                    'max_fuel':        100.0,
                    'lap_time':        self._last_lap_time_s,
                    'position':        0,
                    'car_name':        'OBD-II Vehicle',
                    'track_name':      'Real Track',
                    'lap_count':       self._lap_count,
                    'current_time':    current_time_ms,
                    'lap_dist_pct':    lap_dist_pct,
                    'world_x':         0.0,
                    'world_z':         0.0,
                    'lap_valid':       True,
                    'is_in_pit_lane':  False,
                    'tyre_temp':       [0.0, 0.0, 0.0, 0.0],
                    'tyre_pressure':   [0.0, 0.0, 0.0, 0.0],
                    'brake_temp':      [0.0, 0.0, 0.0, 0.0],
                    'tyre_wear':       [0.0, 0.0, 0.0, 0.0],
                    'tyre_compound':   '',
                    'air_temp':        intake_t,
                    'road_temp':       coolant_t,
                    'brake_bias':      0.0,
                    'gap_ahead':       0,
                    'gap_behind':      0,
                    'delta_lap_time':  0,
                    'estimated_lap':   0,
                    'stint_time_left': 0,
                    'session_type':    'PRACTICE',
                }

                with self._lock:
                    self.latest_data = data

            except Exception as e:
                print(f'ELM327 poll error: {e}')
                time.sleep(0.5)
