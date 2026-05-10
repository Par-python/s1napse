"""Track recorder and saved-track loader."""

import json
import math
import re
import sys
from pathlib import Path


def _get_tracks_dir() -> Path:
    """Return the writable tracks directory.

    When frozen as a PyInstaller EXE, write next to the .exe so the user's
    recorded tracks persist between sessions.  When running from source, use
    the repo's tracks/ folder as before.
    """
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parent
    return base / 'tracks'


def _bundle_base() -> Path:
    """Directory containing bundled assets (tracks-db/, racelines/).
    Both live inside the package folder alongside tracks/."""
    return Path(__file__).resolve().parent


def _read_xy_csv(path: Path, want_cols: int) -> list[tuple[float, ...]]:
    """Parse a comma-separated CSV, skipping '#'-prefixed lines. Each row is
    coerced to `want_cols` floats; shorter rows are skipped."""
    out: list[tuple[float, ...]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) < want_cols:
                continue
            try:
                out.append(tuple(float(parts[i]) for i in range(want_cols)))
            except ValueError:
                continue
    return out


def _build_edges(center_xy: list[tuple[float, float]],
                 wr: list[float], wl: list[float]
                 ) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Offset the centerline along its per-point normal to produce left/right edges.

    Right-hand normal is (dy, -dx); left-hand normal is (-dy, dx).
    Widths are in the same units as the centerline (meters for TUMFTM data).
    """
    n = len(center_xy)
    left: list[tuple[float, float]] = []
    right: list[tuple[float, float]] = []
    for i in range(n):
        x, y = center_xy[i]
        # Tangent via neighbor difference (periodic loop).
        px, py = center_xy[(i - 1) % n]
        nx, ny = center_xy[(i + 1) % n]
        tx, ty = nx - px, ny - py
        ln = math.hypot(tx, ty) or 1.0
        tx, ty = tx / ln, ty / ln
        # Unit right / left normals.
        rx, ry = ty, -tx
        lx, ly = -ty,  tx
        right.append((x + rx * wr[i], y + ry * wr[i]))
        left.append((x + lx * wl[i], y + ly * wl[i]))
    return left, right


def _load_tumftm(track_key: str) -> dict | None:
    """If TUMFTM CSVs exist for this track, return a dict with normalized
    centerline + edges + raceline (all in [0..1], Y-flipped for screen).
    Matches filenames case-insensitively."""
    base = _bundle_base()
    tdb = base / 'tracks-db'
    rll = base / 'racelines'
    if not tdb.exists():
        return None

    def _find(dirp: Path) -> Path | None:
        if not dirp.exists():
            return None
        for p in dirp.glob('*.csv'):
            if p.stem.lower() == track_key.lower():
                return p
        return None

    tfile = _find(tdb)
    if tfile is None:
        return None

    rows = _read_xy_csv(tfile, 4)        # x, y, w_right, w_left
    if len(rows) < 10:
        return None

    cx = [r[0] for r in rows]
    cy = [r[1] for r in rows]
    wr = [r[2] for r in rows]
    wl = [r[3] for r in rows]

    # Read raceline in the SAME meter frame (optional).
    rfile = _find(rll)
    rline_m: list[tuple[float, float]] = []
    if rfile is not None:
        rr = _read_xy_csv(rfile, 2)
        rline_m = [(r[0], r[1]) for r in rr]

    # Build edges in meters, then normalize everything with a shared transform.
    center_m = list(zip(cx, cy))
    left_m, right_m = _build_edges(center_m, wr, wl)

    all_x = cx + [p[0] for p in left_m] + [p[0] for p in right_m]
    all_y = cy + [p[1] for p in left_m] + [p[1] for p in right_m]
    if rline_m:
        all_x += [p[0] for p in rline_m]
        all_y += [p[1] for p in rline_m]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    span_x = max_x - min_x
    span_y = max_y - min_y
    span   = max(span_x, span_y)
    if span <= 0:
        return None

    PAD = 0.06
    scale = (1.0 - 2 * PAD) / span
    off_x = (1.0 - span_x * scale) / 2.0
    off_y = (1.0 - span_y * scale) / 2.0

    def nrm(xs: list[float], ys: list[float]) -> list[tuple[float, float]]:
        # Y-flip so screen-Y-down renders the track upright.
        return [(round((x - min_x) * scale + off_x, 5),
                 round(1.0 - ((y - min_y) * scale + off_y), 5))
                for x, y in zip(xs, ys)]

    center_n = nrm(cx, cy)
    left_n   = nrm([p[0] for p in left_m],  [p[1] for p in left_m])
    right_n  = nrm([p[0] for p in right_m], [p[1] for p in right_m])
    raceline_n = nrm([p[0] for p in rline_m], [p[1] for p in rline_m]) if rline_m else []

    # Curvature profile for the raceline, used by the raceline color gradient.
    rcurv: list[float] = []
    if raceline_n:
        m = len(raceline_n)
        raw = [0.0] * m
        for i in range(m):
            ax, ay = raceline_n[(i - 1) % m]
            bx, by = raceline_n[i]
            cxp, cyp = raceline_n[(i + 1) % m]
            v1x, v1y = bx - ax, by - ay
            v2x, v2y = cxp - bx, cyp - by
            cross = v1x * v2y - v1y * v2x
            raw[i] = cross
        # Smooth + map into [0..1] centered at 0.5 (for green→white→red grad).
        R = 5
        denom = (R * 2 + 1)
        sm = [sum(raw[(i + k) % m] for k in range(-R, R + 1)) / denom for i in range(m)]
        if sm:
            mx = max(abs(v) for v in sm) or 1.0
            rcurv = [max(0.0, min(1.0, 0.5 + 0.5 * (v / mx))) for v in sm]

    return {
        'pts':           center_n,
        'left_edge':     left_n,
        'right_edge':    right_n,
        'raceline':      raceline_n,
        'raceline_curv': rcurv,
    }


# ---------------------------------------------------------------------------
# TRACK DATA  -  normalized waypoints + turn metadata
# Track registry: starts empty, populated by load_saved_tracks() from tracks/*.json
TRACKS: dict = {}

# Substring -> track key map: populated by load_saved_tracks() alongside TRACKS
TRACK_NAME_MAP: dict[str, str] = {}


def load_saved_tracks():
    """Load any JSON files from the tracks/ directory into TRACKS and TRACK_NAME_MAP."""
    tracks_dir = _get_tracks_dir()
    if not tracks_dir.exists():
        return
    for json_file in sorted(tracks_dir.glob('*.json')):
        try:
            with open(json_file) as f:
                td = json.load(f)
            if not isinstance(td, dict) or 'track_key' not in td or 'pts' not in td:
                continue
            key = td['track_key']
            # ACC world-Z increases northward, but Qt screen-Y increases downward,
            # so saved-normalized y must be flipped on load to render right-side up.
            pts = [(float(p[0]), 1.0 - float(p[1])) for p in td['pts']]
            raceline = [(float(p[0]), 1.0 - float(p[1])) for p in td.get('raceline', [])]
            turns = []
            for t in td.get('turns', []):
                t = list(t)
                if len(t) >= 5:
                    t[4] = -t[4]  # flip label Y-offset to match flipped track
                turns.append(tuple(t))

            left_edge: list[tuple[float, float]] = []
            right_edge: list[tuple[float, float]] = []

            # Prefer TUMFTM data (real track limits + curvature-optimal raceline)
            # when the matching CSVs are bundled; it's strictly higher quality
            # than our session-recorded centerline.
            tumf = _load_tumftm(key)
            if tumf is not None:
                pts = tumf['pts']
                left_edge = tumf['left_edge']
                right_edge = tumf['right_edge']
                if tumf['raceline']:
                    raceline = tumf['raceline']
                    # Only override the curvature profile if we actually
                    # replaced the raceline, so they stay in sync.
                    td_curv = tumf['raceline_curv']
                else:
                    td_curv = list(td.get('raceline_curv', []))
            else:
                td_curv = list(td.get('raceline_curv', []))

            TRACKS[key] = {
                'name': td['name'],
                'pts': pts,
                'turns': turns,
                'length_m': td['length_m'],
                'raceline': raceline,
                'raceline_curv': td_curv,
                'left_edge': left_edge,
                'right_edge': right_edge,
            }
            TRACK_NAME_MAP[key] = key
        except Exception as e:
            print(f'Failed to load saved track {json_file.name}: {e}')


# Load any previously recorded tracks on import
load_saved_tracks()


class TrackRecorder:
    """Samples world position during a lap and saves a normalized track JSON."""

    N_OUT = 250          # waypoints to write to the JSON file
    MIN_SAMPLES = 50     # minimum samples before a save is accepted

    def __init__(self):
        self.recording = False
        self._samples: list[tuple[float, float, float]] = []   # (pct, x, z)
        self._last_pct = -1.0

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def start(self):
        self.recording = True
        self._samples = []
        self._last_pct = -1.0

    def stop(self):
        self.recording = False

    def feed(self, lap_dist_pct: float, world_x: float, world_z: float):
        if not self.recording:
            return
        if world_x == 0.0 and world_z == 0.0:
            return
        # Skip backward jumps larger than 0.5 (lap boundary crossing)
        if self._last_pct >= 0 and (lap_dist_pct - self._last_pct) < -0.5:
            return
        # Deduplicate: only record if we've moved at least 0.001 along the lap
        if abs(lap_dist_pct - self._last_pct) < 0.001:
            return
        self._samples.append((lap_dist_pct, world_x, world_z))
        self._last_pct = lap_dist_pct

    def save(self, track_name: str, length_m: int) -> str | None:
        """Normalize and save to tracks/{key}.json. Returns the path on success."""
        if len(self._samples) < self.MIN_SAMPLES:
            return None

        # Sort by lap fraction
        s = sorted(self._samples, key=lambda t: t[0])
        xs = [p[1] for p in s]
        zs = [p[2] for p in s]

        min_x, max_x = min(xs), max(xs)
        min_z, max_z = min(zs), max(zs)
        span = max(max_x - min_x, max_z - min_z)
        if span == 0:
            return None

        PAD = 0.06
        scale = (1.0 - 2 * PAD) / span
        nx = [(x - min_x) * scale + PAD for x in xs]
        nz = [(z - min_z) * scale + PAD for z in zs]

        # Downsample to N_OUT evenly-spaced points
        n = len(nx)
        indices = [int(round(i * (n - 1) / (self.N_OUT - 1))) for i in range(self.N_OUT)]
        pts = [[round(nx[i], 4), round(nz[i], 4)] for i in indices]

        # Derive a filesystem-safe key from the track name
        track_key = re.sub(r'[^a-z0-9_]', '_', track_name.lower()).strip('_')
        track_key = re.sub(r'_+', '_', track_key)

        from s1napse.lovely_turns import load_turns, LOVELY_SOURCE_TAG
        pts_tuples = [(p[0], p[1]) for p in pts]
        turns = load_turns(track_key, pts_tuples)

        data = {
            'name': track_name,
            'track_key': track_key,
            'length_m': length_m,
            'pts': pts,
            'turns': turns,
        }
        if turns:
            data['turn_source'] = LOVELY_SOURCE_TAG

        out_dir = _get_tracks_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f'{track_key}.json'
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return str(path)
