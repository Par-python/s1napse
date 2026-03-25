"""Track recorder and saved-track loader."""

import json
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
            key = td['track_key']
            TRACKS[key] = {
                'name': td['name'],
                'pts': [tuple(p) for p in td['pts']],
                'turns': [tuple(t) for t in td.get('turns', [])],
                'length_m': td['length_m'],
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

        data = {
            'name': track_name,
            'track_key': track_key,
            'length_m': length_m,
            'pts': pts,
            'turns': [],
        }

        out_dir = _get_tracks_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f'{track_key}.json'
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return str(path)
