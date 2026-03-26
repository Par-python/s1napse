"""Assetto Corsa UDP telemetry reader."""

import socket
import struct
import threading
import time
import random

from .base import TelemetryReader


class ACUDPReader(TelemetryReader):
    def __init__(self, host='127.0.0.1', port=9996):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.latest_data = None
        self._lock = threading.Lock()
        self.handshake_sent = False
        self.running = False
        self.listener_thread = None

        self.sim_lap_start_ms = None
        self.sim_target_lap_ms = None
        self.sim_lap_count = 0
        self.sim_last_lap_ms = 0

    def connect(self):
        try:
            if self.socket:
                self.socket.close()
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.settimeout(1.0)
            identifier = 1
            version = 1
            operation_id = 0
            handshake = struct.pack('<iii', identifier, version, operation_id)
            self.socket.sendto(handshake, (self.host, self.port))
            try:
                data, addr = self.socket.recvfrom(2048)
                if data:
                    self.connected = True
                    self.handshake_sent = True
                    subscribe = struct.pack('<iii', identifier, version, 1)
                    self.socket.sendto(subscribe, (self.host, self.port))
                    self.running = True
                    self.listener_thread = threading.Thread(target=self._listen, daemon=True)
                    self.listener_thread.start()
                    return True
            except socket.timeout:
                pass
        except Exception as e:
            print(f"AC UDP connection error: {e}")
        return False

    def _listen(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(2048)
                if data and len(data) > 4:
                    packet_id = struct.unpack('<i', data[0:4])[0]
                    if packet_id == 2:
                        parsed = self._parse_car_info(data)
                        with self._lock:
                            self.latest_data = parsed
            except socket.timeout:
                continue
            except Exception:
                break

    def _parse_car_info(self, data):
        try:
            # ── Core fields (original offsets, always present) ──────────────
            speed_kmh   = struct.unpack('<f', data[4:8])[0]
            world_x     = struct.unpack('<f', data[8:12])[0]  if len(data) >= 20 else 0.0
            world_z     = struct.unpack('<f', data[16:20])[0] if len(data) >= 20 else 0.0
            rpm         = struct.unpack('<f', data[28:32])[0]
            gear        = struct.unpack('<i', data[32:36])[0]
            throttle = brake = steer_angle = abs_val = tc_val = 0.0
            if len(data) >= 56:
                throttle    = struct.unpack('<f', data[36:40])[0]
                brake       = struct.unpack('<f', data[40:44])[0]
                steer_angle = struct.unpack('<f', data[44:48])[0]
                abs_val     = struct.unpack('<f', data[48:52])[0]
                tc_val      = struct.unpack('<f', data[52:56])[0]

            # ── Extended fields (simulator v2, 188-byte packet) ─────────────
            _COMPOUNDS = {0: 'DHF', 1: 'DM', 2: 'DS', 3: 'WET'}
            _SESSIONS  = {0: 'PRACTICE', 2: 'RACE', 3: 'QUALIFY'}

            if len(data) >= 188:
                fuel          = struct.unpack('<f', data[56:60])[0]
                lap_dist_pct  = struct.unpack('<f', data[60:64])[0]
                lap_count     = struct.unpack('<i', data[64:68])[0]
                current_time  = struct.unpack('<i', data[68:72])[0]
                last_lap_ms   = struct.unpack('<i', data[72:76])[0]
                position      = struct.unpack('<i', data[76:80])[0]
                flags         = struct.unpack('<i', data[80:84])[0]
                lap_valid     = bool(flags & 0x1)
                is_in_pit     = bool(flags & 0x2)

                tyre_temp     = list(struct.unpack('<4f', data[84:100]))
                tyre_pressure = list(struct.unpack('<4f', data[100:116]))
                brake_temp    = list(struct.unpack('<4f', data[116:132]))
                tyre_wear     = list(struct.unpack('<4f', data[132:148]))

                gap_ahead     = struct.unpack('<i', data[148:152])[0]
                gap_behind    = struct.unpack('<i', data[152:156])[0]
                air_temp      = struct.unpack('<f', data[156:160])[0]
                road_temp     = struct.unpack('<f', data[160:164])[0]
                brake_bias    = struct.unpack('<f', data[164:168])[0]
                delta_lap     = struct.unpack('<i', data[168:172])[0]
                est_lap       = struct.unpack('<i', data[172:176])[0]
                stint_left    = struct.unpack('<i', data[176:180])[0]
                session_id    = struct.unpack('<i', data[180:184])[0]
                compound_id   = struct.unpack('<i', data[184:188])[0]

                lap_time      = last_lap_ms / 1000.0 if last_lap_ms > 0 else 0.0
                session_type  = _SESSIONS.get(session_id, 'PRACTICE')
                tyre_compound = _COMPOUNDS.get(compound_id, 'DHF')
            else:
                # Fallback: old short packet — synthesise basic session state
                now_ms = int(time.time() * 1000)
                if self.sim_lap_start_ms is None:
                    self.sim_lap_start_ms = now_ms
                    self.sim_target_lap_ms = random.randint(81000, 99000)
                elapsed_ms = now_ms - self.sim_lap_start_ms
                if elapsed_ms >= self.sim_target_lap_ms:
                    self.sim_last_lap_ms = elapsed_ms
                    self.sim_lap_count += 1
                    self.sim_lap_start_ms = now_ms
                    self.sim_target_lap_ms = random.randint(81000, 99000)
                    elapsed_ms = 0
                fuel = 0.0; lap_dist_pct = 0.0; lap_count = self.sim_lap_count
                current_time = elapsed_ms; lap_time = self.sim_last_lap_ms / 1000.0
                position = 0; lap_valid = True; is_in_pit = False
                tyre_temp = tyre_pressure = brake_temp = tyre_wear = [0.0, 0.0, 0.0, 0.0]
                gap_ahead = gap_behind = 0; air_temp = road_temp = 0.0
                brake_bias = 0.0; delta_lap = est_lap = stint_left = 0
                session_type = 'PRACTICE'; tyre_compound = ''

            return {
                'speed':          speed_kmh,
                'rpm':            rpm,
                'max_rpm':        8000,
                'gear':           gear,
                'throttle':       throttle,
                'brake':          brake,
                'steer_angle':    steer_angle,
                'abs':            abs_val,
                'tc':             tc_val,
                'fuel':           fuel,
                'max_fuel':       80,
                'lap_time':       lap_time,
                'position':       position,
                'car_name':       'Simulated Car',
                'track_name':     'Monza (Simulated)',
                'lap_count':      lap_count,
                'current_time':   current_time,
                'lap_dist_pct':   lap_dist_pct,
                'world_x':        world_x,
                'world_z':        world_z,
                'lap_valid':      lap_valid,
                'is_in_pit_lane': is_in_pit,
                'tyre_temp':      tyre_temp,
                'tyre_pressure':  tyre_pressure,
                'brake_temp':     brake_temp,
                'tyre_wear':      tyre_wear,
                'tyre_compound':  tyre_compound,
                'air_temp':       air_temp,
                'road_temp':      road_temp,
                'brake_bias':     brake_bias,
                'gap_ahead':      gap_ahead,
                'gap_behind':     gap_behind,
                'delta_lap_time': delta_lap,
                'estimated_lap':  est_lap,
                'stint_time_left': stint_left,
                'session_type':   session_type,
            }
        except Exception:
            return None

    def read(self):
        if not self.connected:
            if not self.connect():
                return None
        with self._lock:
            return self.latest_data

    def is_connected(self):
        return self.connected and self.latest_data is not None

    def disconnect(self):
        self.running = False
        if self.socket:
            self.socket.close()
