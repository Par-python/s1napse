// Synapse full-featured telemetry simulator
//
// Simulates a complete race session with data for ALL tabs:
//   Dashboard, Telemetry Graphs, Lap Analysis, Race, Tyres, Lap Comparison, Session
//
// Usage:
//   1) node telemetry_simulator.js
//   2) python3 test-listener.py
//   3) In the app: select "AC (UDP)", Host = 127.0.0.1, Port = 9996
//
// Extended packet layout (188 bytes, all little-endian):
//  CORE (original offsets, unchanged)
//   [0-3]    int32  packet_id = 2
//   [4-7]    float  speed_kmh
//   [8-11]   float  world_x
//   [12-15]  float  world_y  (unused)
//   [16-19]  float  world_z
//   [20-27]  (reserved)
//   [28-31]  float  rpm
//   [32-35]  int32  gear
//   [36-39]  float  throttle  (0-100)
//   [40-43]  float  brake     (0-100)
//   [44-47]  float  steer_angle (radians)
//   [48-51]  float  abs       (0-100)
//   [52-55]  float  tc        (0-100)
//  EXTENDED
//   [56-59]  float  fuel_liters
//   [60-63]  float  lap_dist_pct  (0.0-1.0)
//   [64-67]  int32  lap_count
//   [68-71]  int32  current_time_ms  (ms into current lap)
//   [72-75]  int32  last_lap_ms
//   [76-79]  int32  position  (1-based race position)
//   [80-83]  int32  flags: bit0=lap_valid, bit1=is_in_pit_lane
//   [84-87]  float  tyre_temp_FL
//   [88-91]  float  tyre_temp_FR
//   [92-95]  float  tyre_temp_RL
//   [96-99]  float  tyre_temp_RR
//  [100-103] float  tyre_pres_FL
//  [104-107] float  tyre_pres_FR
//  [108-111] float  tyre_pres_RL
//  [112-115] float  tyre_pres_RR
//  [116-119] float  brake_temp_FL
//  [120-123] float  brake_temp_FR
//  [124-127] float  brake_temp_RL
//  [128-131] float  brake_temp_RR
//  [132-135] float  tyre_wear_FL  (0.0=new .. 1.0=bald)
//  [136-139] float  tyre_wear_FR
//  [140-143] float  tyre_wear_RL
//  [144-147] float  tyre_wear_RR
//  [148-151] int32  gap_ahead_ms  (positive)
//  [152-155] int32  gap_behind_ms (negative — car behind = negative)
//  [156-159] float  air_temp
//  [160-163] float  road_temp
//  [164-167] float  brake_bias    (0.0-1.0, typical 0.53-0.60)
//  [168-171] int32  delta_lap_time_ms  (negative=ahead of ref, positive=behind)
//  [172-175] int32  estimated_lap_ms
//  [176-179] int32  stint_time_left_ms
//  [180-183] int32  session_type  (0=PRACTICE, 2=RACE, 3=QUALIFY)
//  [184-187] int32  tyre_compound_id (0=DHF, 1=DM, 2=DS, 3=WET)

const dgram = require('dgram');

const PORT    = 9996;
const HOST    = '127.0.0.1';
const HZ      = 20;       // 20 Hz = 50ms interval
const LAP_SEC = 90;       // simulated lap duration in seconds
const PI      = Math.PI;

// ── Session constants ────────────────────────────────────────────────────────
const SESSION_TYPE  = 2;    // RACE
const TYRE_COMPOUND = 0;    // DHF (dry hard)
const TOTAL_LAPS    = 20;
const FUEL_FULL     = 80;   // litres at race start
const FUEL_PER_LAP  = 2.3;
const AIR_TEMP      = 22.5;
const ROAD_TEMP     = 38.0;
const BRAKE_BIAS    = 0.56;
const EST_LAP_MS    = 88500; // reference lap time in ms

const server = dgram.createSocket('udp4');
let client   = null;
let sending  = false;

// ── Simulation state ─────────────────────────────────────────────────────────
let t            = 0;
let lapCount     = 0;
let lapStartTime = null;
let lastLapMs    = 0;
let totalFuel    = FUEL_FULL;
let pitLaneTimer = 0;
let position     = 4;
let tyreWear     = [0, 0, 0, 0];

// Pit on lap 7 and lap 14
const PIT_LAPS = new Set([7, 14]);
const pitDone  = new Set();

// ── Per-lap variation state ───────────────────────────────────────────────────
// Each lap gets its own pace multiplier and optional events so the session
// looks like real data: some laps are clean, some have mistakes or traffic.

let lapSpeedMult   = 1.0;   // applied to all speed values this lap (0.96–1.02)
let lapBrakeBias   = 0.0;   // random braking point shift per lap (−0.06..+0.06)
let trafficActive  = false; // true when simulating getting stuck behind a car
let trafficTimer   = 0;     // ticks remaining in traffic event
let mistakeActive  = false; // true during a simulated lock-up / run-wide
let mistakeTimer   = 0;     // ticks remaining in mistake event
let mistakeZone    = 0;     // which brake zone the mistake is in (0-4)

function _rand(lo, hi) { return lo + Math.random() * (hi - lo); }

function newLapVariation() {
  // Base pace: fresh tyres ~1.0, degrades toward 0.965 at max wear before pit
  const avgWear    = tyreWear.reduce((s, w) => s + w, 0) / 4;
  const wearPenalty = avgWear * 0.035;             // up to −3.5% from worn rubber
  const randomDelta = _rand(-0.012, 0.012);        // ±1.2% random lap scatter
  lapSpeedMult     = clamp(1.0 - wearPenalty + randomDelta, 0.94, 1.02);

  // Random brake zone shift (driver pushing harder or more conservative)
  lapBrakeBias = _rand(-0.06, 0.06);

  // Traffic: ~20% chance of getting held up for 4–10 seconds mid-lap
  if (Math.random() < 0.20) {
    trafficActive = true;
    trafficTimer  = Math.round(_rand(4, 10) * HZ);
  }

  // Driver mistake: ~15% chance of a lock-up/run-wide in one brake zone
  if (Math.random() < 0.15) {
    mistakeActive = true;
    mistakeTimer  = Math.round(_rand(1.5, 4) * HZ);
    mistakeZone   = Math.floor(Math.random() * 5);  // 0-4 (which brake zone)
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function lerp(a, b, f)    { return a + (b - a) * f; }
function noise(f, amp)    { return amp * Math.sin(t * f); }

// ── Lap physics ───────────────────────────────────────────────────────────────
function lapPhysics(p) {
  const zones = [
    [0.02, 0.08, 1.0 ],  // T1
    [0.22, 0.28, 0.85],  // Chicane
    [0.45, 0.52, 0.90],  // Lesmo
    [0.68, 0.75, 0.95],  // Ascari
    [0.88, 0.95, 0.85],  // Parabolica
  ];

  let inZone = false, zoneI = 0, zoneIdx = -1;
  for (let i = 0; i < zones.length; i++) {
    const [s, e, intensity] = zones[i];
    if (p >= s + lapBrakeBias * 0.5 && p <= e + lapBrakeBias * 0.5) {
      inZone = true; zoneIdx = i;
      const mid = (s + e) / 2 + lapBrakeBias * 0.5, half = (e - s) / 2;
      zoneI = intensity * Math.max(0, 1 - Math.abs(p - mid) / half * 0.6);
    }
  }

  // Mistake: driver locks up / runs wide in the designated zone this lap
  const inMistakeZone = mistakeActive && mistakeTimer > 0 && zoneIdx === mistakeZone;
  if (inMistakeZone) {
    zoneI = clamp(zoneI * 0.6, 0, 1);   // braking earlier/lighter = slower corner
    mistakeTimer--;
    if (mistakeTimer <= 0) mistakeActive = false;
  }

  // Traffic: stuck behind a car — speed capped at ~160 on the straight
  const trafficCap = (trafficActive && trafficTimer > 0) ? 160 : 310;
  if (trafficActive && trafficTimer > 0) {
    trafficTimer--;
    if (trafficTimer <= 0) trafficActive = false;
  }

  const baseSpeed = inZone ? lerp(280, 70, zoneI) : 220 + 60 * Math.sin(p * 4 * PI) + noise(1.3, 8);
  const speed     = clamp(baseSpeed * lapSpeedMult, 65, trafficCap);
  const throttle  = clamp(inZone ? (1 - zoneI) * 100 : (trafficActive ? 55 + noise(0.4, 8) : 85 + noise(0.7, 15)), 0, 100);
  const brake     = inZone ? clamp(zoneI * 100, 0, 100) : 0;
  const gear      = clamp(Math.floor(1 + speed / 52), 1, 6);
  const rpm       = clamp(2500 + (speed / 310) * 5500 + noise(2, 400), 1000, 8000);
  const steer     = (90 * Math.sin(p * 6 * PI) + 60 * Math.sin(p * 20 * PI)) * (PI / 180);
  // Mistake causes ABS spike (locking up)
  const abs       = (inMistakeZone && brake > 40)
                      ? clamp(40 + noise(6, 25), 0, 100)
                      : brake > 60 ? clamp(20 + (brake - 60) * 1.8 + noise(8, 10), 0, 100) : 0;
  const tc        = (!inZone && throttle > 75) ? clamp(10 + 20 * Math.max(0, Math.sin(t * 4)) * Math.max(0, Math.sin(t * 0.3)), 0, 100) : 0;

  // Monza-ish oval world position
  const wx = 300 * Math.cos(p * 2 * PI) + 80 * Math.cos(p * 4 * PI);
  const wz = 250 * Math.sin(p * 2 * PI) + 40 * Math.sin(p * 4 * PI);

  return { speed, rpm, gear, throttle, brake, steer, abs, tc, wx, wz };
}

// ── Tyre model ─────────────────────────────────────────────────────────────────
function tyreTemps(speed, brake, inPit) {
  if (inPit) return [80, 80, 78, 78];
  const fb = 85 + (brake / 100) * 25;
  const rb = 83 + (speed / 310) * 18;
  return [
    clamp(fb + noise(0.3, 4),       75, 115),
    clamp(fb + noise(0.5, 4) + 2,   75, 115),
    clamp(rb + noise(0.4, 3),       72, 105),
    clamp(rb + noise(0.6, 3) + 1.5, 72, 105),
  ];
}

function tyrePressures(temps) {
  return temps.map(tmp => clamp(27.0 + (tmp - 85) * 0.04 + noise(0.1, 0.3), 25.5, 29.5));
}

function brakeTemps(speed, brake) {
  const front = clamp(200 + (brake / 100) * 500 + noise(0.5, 30), 80, 800);
  const rear  = clamp(150 + (brake / 100) * 300 + noise(0.4, 20), 60, 600);
  return [front, front * 0.97, rear, rear * 0.98];
}

// ── Gap model ─────────────────────────────────────────────────────────────────
let gapAhead  = 1800;   // ms positive
let gapBehind = -2200;  // ms negative

function updateGaps(speed) {
  // Faster speed = closing gap to car ahead slightly
  const catchRate = (speed / 310) * 0.8;
  gapAhead  = clamp(gapAhead  + noise(0.05, 3) - catchRate, 200, 8000);
  gapBehind = clamp(gapBehind + noise(0.05, 3) + 0.3,       -8000, -150);
}

// ── Main tick ─────────────────────────────────────────────────────────────────
function buildPacket() {
  t += 1 / HZ;

  const now = Date.now();
  if (!lapStartTime) lapStartTime = now;

  const lapElapsedMs = now - lapStartTime;
  const lapProgress  = clamp(lapElapsedMs / (LAP_SEC * 1000), 0, 1);

  // Seed variation for the very first lap
  if (lapCount === 0 && lapElapsedMs < 1000 / HZ + 5) newLapVariation();

  // Lap boundary
  if (lapElapsedMs >= LAP_SEC * 1000) {
    lastLapMs    = lapElapsedMs + Math.round(noise(0.01, 200));
    lapCount    += 1;
    lapStartTime = now;
    totalFuel    = Math.max(0, totalFuel - FUEL_PER_LAP + _rand(-0.15, 0.15));
    tyreWear     = tyreWear.map(w => clamp(w + _rand(0.035, 0.055), 0, 1));
    if (Math.random() < 0.3) position = clamp(position + (Math.random() < 0.5 ? -1 : 1), 1, 15);
    newLapVariation();  // roll new pace / events for next lap
    const tag = mistakeActive ? ' ⚠ MISTAKE' : trafficActive ? ' 🚦 TRAFFIC' : '';
    console.log(`Lap ${lapCount}  ${(lastLapMs / 1000).toFixed(3)}s  mult:${lapSpeedMult.toFixed(3)}  Fuel:${totalFuel.toFixed(1)}L  P${position}${tag}`);
  }

  // Pit stop
  if (PIT_LAPS.has(lapCount) && !pitDone.has(lapCount) && lapProgress > 0.5) {
    pitDone.add(lapCount);
    pitLaneTimer = HZ * 25; // 25s in pit lane
    tyreWear     = [0, 0, 0, 0];
    totalFuel    = FUEL_FULL;
    console.log(`Pit stop on lap ${lapCount} — tyres fresh, fuel full`);
  }

  const inPit = pitLaneTimer > 0;
  if (inPit) pitLaneTimer--;

  const p   = inPit ? 0 : lapProgress;
  const phy = lapPhysics(p);
  updateGaps(phy.speed);

  const temps     = tyreTemps(phy.speed, phy.brake, inPit);
  const pressures = tyrePressures(temps);
  const bTemps    = brakeTemps(phy.speed, phy.brake);

  // Lap 3 every 8 laps is marked invalid for demo purposes
  const lapValid = (lapCount % 8 !== 3) ? 1 : 0;
  const flags    = (lapValid & 1) | ((inPit ? 1 : 0) << 1);

  const delta_ms  = Math.round(lapElapsedMs - EST_LAP_MS * lapProgress + noise(0.3, 120));
  const est_lap   = EST_LAP_MS + Math.round(noise(0.02, 300));
  const stintLeft = Math.max(0, (TOTAL_LAPS - lapCount) * LAP_SEC * 1000 - lapElapsedMs);

  // Build 188-byte packet
  const buf = Buffer.alloc(188);

  // Core
  buf.writeInt32LE(2, 0);
  buf.writeFloatLE(phy.speed, 4);
  buf.writeFloatLE(phy.wx, 8);
  buf.writeFloatLE(0, 12);
  buf.writeFloatLE(phy.wz, 16);
  buf.writeFloatLE(phy.rpm, 28);
  buf.writeInt32LE(phy.gear, 32);
  buf.writeFloatLE(phy.throttle, 36);
  buf.writeFloatLE(phy.brake, 40);
  buf.writeFloatLE(phy.steer, 44);
  buf.writeFloatLE(phy.abs, 48);
  buf.writeFloatLE(phy.tc, 52);

  // Extended
  buf.writeFloatLE(totalFuel, 56);
  buf.writeFloatLE(inPit ? 0 : lapProgress, 60);
  buf.writeInt32LE(lapCount, 64);
  buf.writeInt32LE(inPit ? 0 : lapElapsedMs, 68);
  buf.writeInt32LE(lastLapMs, 72);
  buf.writeInt32LE(position, 76);
  buf.writeInt32LE(flags, 80);

  buf.writeFloatLE(temps[0], 84);
  buf.writeFloatLE(temps[1], 88);
  buf.writeFloatLE(temps[2], 92);
  buf.writeFloatLE(temps[3], 96);

  buf.writeFloatLE(pressures[0], 100);
  buf.writeFloatLE(pressures[1], 104);
  buf.writeFloatLE(pressures[2], 108);
  buf.writeFloatLE(pressures[3], 112);

  buf.writeFloatLE(bTemps[0], 116);
  buf.writeFloatLE(bTemps[1], 120);
  buf.writeFloatLE(bTemps[2], 124);
  buf.writeFloatLE(bTemps[3], 128);

  buf.writeFloatLE(tyreWear[0], 132);
  buf.writeFloatLE(tyreWear[1], 136);
  buf.writeFloatLE(tyreWear[2], 140);
  buf.writeFloatLE(tyreWear[3], 144);

  buf.writeInt32LE(Math.round(gapAhead), 148);
  buf.writeInt32LE(Math.round(gapBehind), 152);
  buf.writeFloatLE(AIR_TEMP, 156);
  buf.writeFloatLE(ROAD_TEMP, 160);
  buf.writeFloatLE(BRAKE_BIAS, 164);
  buf.writeInt32LE(delta_ms, 168);
  buf.writeInt32LE(est_lap, 172);
  buf.writeInt32LE(Math.round(stintLeft), 176);
  buf.writeInt32LE(SESSION_TYPE, 180);
  buf.writeInt32LE(TYRE_COMPOUND, 184);

  return buf;
}

// ── UDP server ────────────────────────────────────────────────────────────────
server.on('error', (err) => { console.error('Socket error:', err); server.close(); });

server.on('message', (msg, rinfo) => {
  if (msg.length < 12) return;
  const operationId = msg.readInt32LE(8);

  if (operationId === 0) {
    console.log(`Handshake from ${rinfo.address}:${rinfo.port}`);
    const resp = Buffer.alloc(4);
    resp.writeInt32LE(1, 0);
    server.send(resp, rinfo.port, rinfo.address);
  }

  if (operationId === 1) {
    console.log(`Subscribe from ${rinfo.address}:${rinfo.port}`);
    client = { address: rinfo.address, port: rinfo.port };
    if (!sending) {
      sending = true;
      setInterval(() => {
        if (!client) return;
        server.send(buildPacket(), client.port, client.address);
      }, 1000 / HZ);
    }
  }
});

server.on('listening', () => {
  const addr = server.address();
  console.log(`\nSynapse telemetry simulator  •  ${addr.address}:${addr.port}`);
  console.log('Session: RACE  |  Track: Monza  |  20 laps  |  Pit stops: L7 + L14');
  console.log('In Synapse → select "AC (UDP)"  →  127.0.0.1 : 9996\n');
});

server.bind(PORT, HOST);
