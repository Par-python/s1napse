"""Import TUMFTM/racetrack-database CSVs into s1napse/tracks/*.json.

For each track:
  - tracks-db/{Name}.csv -> centerline (x_m, y_m, w_tr_right_m, w_tr_left_m)
  - racelines/{Name}.csv -> raceline (x_m, y_m)
Both CSVs share the same coordinate frame, so the raceline is normalized with
the SAME transform as the centerline so the two overlay correctly.

Curvature is computed along the raceline, smoothed, and normalized [0, 1] so
the widget can render a green->white->red gradient without extra per-frame work.
"""

import json
import math
import re
import sys
from pathlib import Path

REPO        = Path(__file__).resolve().parent.parent
TRACKS_DIR  = REPO / 's1napse' / 'tracks-db'
RACELN_DIR  = REPO / 's1napse' / 'racelines'
DST_DIR     = REPO / 's1napse' / 'tracks'
N_OUT       = 250
PAD         = 0.06
SMOOTH_SIGMA = 6.0  # gaussian kernel std-dev for curvature smoothing
SOURCE_TAG  = 'TUMFTM/racetrack-database (LGPL-3.0)'

LOVELY_DIR = REPO / 's1napse' / 'lovely-track-data'
LOVELY_SOURCE_TAG = 'Lovely-Sim-Racing/lovely-track-data (CC BY-NC-SA 4.0)'

# s1napse track slug (slug-of-ACC-Static.track) -> Lovely's ACC trackId (their filename).
# Slugs follow the rule in s1napse/track_recorder.py:313 (lowercase, [^a-z0-9_] -> _).
LOVELY_ID_MAP: dict[str, str] = {
    'barcelona':       'barcelona',
    'brands_hatch':    'brands-hatch',
    'cota':            'cota',
    'donington':       'donington',
    'hungaroring':     'hungaroring',
    'imola':           'imola',
    'indianapolis':    'indianapolis',
    'kyalami':         'kyalami',
    'laguna_seca':     'laguna-seca',
    'misano':          'misano',
    'monza':           'monza',
    'mount_panorama':  'mount-panorama',
    'nurburgring_24h': 'nurburgring-24h',
    'nurburgring':     'nurburgring',
    # TUMFTM bundles the Nürburgring GP layout as `Nuerburgring.csv`; alias to the same Lovely file.
    'nuerburgring':    'nurburgring',
    'oulton_park':     'oulton-park',
    'paul_ricard':     'paul-ricard',
    'red_bull_ring':   'red-bull-ring',
    'silverstone':     'silverstone',
    'snetterton':      'snetterton',
    'spa':             'spa',
    'suzuka':          'suzuka',
    'valencia':        'valencia',
    'watkins_glen':    'watkins-glen',
    'zandvoort':       'zandvoort',
    'zolder':          'zolder',
}


def slug(name: str) -> str:
    s = re.sub(r'[^a-z0-9_]', '_', name.lower())
    return re.sub(r'_+', '_', s).strip('_')


def load_xy(csv_path: Path) -> list[tuple[float, float]]:
    pts = []
    with open(csv_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) < 2:
                continue
            pts.append((float(parts[0]), float(parts[1])))
    return pts


def polyline_length(pts: list[tuple[float, float]]) -> float:
    total = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def resample_closed(pts: list[tuple[float, float]], n_out: int) -> list[tuple[float, float]]:
    """Resample a closed polyline to n_out evenly-spaced points by arc length."""
    if len(pts) < 2:
        return []
    cum = [0.0]
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        cum.append(cum[-1] + math.hypot(x1 - x0, y1 - y0))
    total = cum[-1]
    if total == 0:
        return []

    out = []
    j = 0
    for i in range(n_out):
        target = (i / n_out) * total
        while j < len(cum) - 1 and cum[j + 1] < target:
            j += 1
        seg = cum[j + 1] - cum[j]
        t = 0.0 if seg == 0 else (target - cum[j]) / seg
        x0, y0 = pts[j % len(pts)]
        x1, y1 = pts[(j + 1) % len(pts)]
        out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    return out


def curvature(pts: list[tuple[float, float]]) -> list[float]:
    """Absolute turn angle at each point (closed polyline)."""
    n = len(pts)
    c = [0.0] * n
    for i in range(n):
        x0, y0 = pts[(i - 1) % n]
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        dx1, dy1 = x1 - x0, y1 - y0
        dx2, dy2 = x2 - x1, y2 - y1
        cross = dx1 * dy2 - dy1 * dx2
        dot   = dx1 * dx2 + dy1 * dy2
        c[i]  = abs(math.atan2(cross, dot))
    return c


def gaussian_smooth_closed(values: list[float], sigma: float) -> list[float]:
    """Gaussian smoothing on a closed list (wraps around)."""
    n = len(values)
    r = max(1, int(math.ceil(3 * sigma)))
    kernel = [math.exp(-(k * k) / (2 * sigma * sigma)) for k in range(-r, r + 1)]
    ksum = sum(kernel)
    kernel = [k / ksum for k in kernel]
    out = [0.0] * n
    for i in range(n):
        s = 0.0
        for k in range(-r, r + 1):
            s += kernel[k + r] * values[(i + k) % n]
        out[i] = s
    return out


def normalize_with_frame(pts: list[tuple[float, float]],
                         min_x: float, max_x: float,
                         min_y: float, max_y: float) -> list[list[float]]:
    span = max(max_x - min_x, max_y - min_y)
    if span == 0:
        return []
    scale    = (1.0 - 2 * PAD) / span
    offset_x = (1.0 - (max_x - min_x) * scale) / 2.0
    offset_y = (1.0 - (max_y - min_y) * scale) / 2.0
    out = []
    for x, y in pts:
        nx = (x - min_x) * scale + offset_x + PAD
        ny = (y - min_y) * scale + offset_y + PAD
        out.append([round(nx, 4), round(ny, 4)])
    return out


def bounds(pts: list[tuple[float, float]]):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


def percentile_normalize(values: list[float], lo_p: float = 0.05, hi_p: float = 0.95) -> list[float]:
    """Map values to [0,1] using percentile bounds so outliers don't dominate."""
    s = sorted(values)
    n = len(s)
    if n == 0:
        return []
    lo = s[max(0, int(lo_p * n))]
    hi = s[min(n - 1, int(hi_p * n))]
    if hi - lo < 1e-9:
        return [0.5] * len(values)
    return [max(0.0, min(1.0, (v - lo) / (hi - lo))) for v in values]


def _signed_area(pts: list[tuple[float, float]]) -> float:
    """Signed area (shoelace). Positive = CCW, negative = CW."""
    n = len(pts)
    s = 0.0
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return 0.5 * s


def _tangent_and_outward_normal(pts: list[tuple[float, float]],
                                frac: float
                                ) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Return ((tx, ty), (nx, ny)) — unit tangent and unit outward direction — at `frac`.

    The outward direction is computed as the vector from the track centroid to the
    point, not from the local tangent's normal. Local tangents wiggle through
    chicanes and can point the "outward" direction back across the track itself;
    the centroid-relative direction is globally consistent.
    """
    n = len(pts)
    if n < 2:
        return None
    i = int(frac * n) % n
    x0, y0 = pts[(i - 1) % n]
    x1, y1 = pts[(i + 1) % n]
    px, py = pts[i]
    tx, ty = (x1 - x0), (y1 - y0)
    L = math.hypot(tx, ty)
    if L == 0:
        return None
    tx, ty = tx / L, ty / L
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    nx, ny = (px - cx), (py - cy)
    R = math.hypot(nx, ny)
    if R == 0:
        # Fallback to local normal if the point sits exactly on the centroid.
        nx, ny = ty, -tx
        if _signed_area(pts) < 0:
            nx, ny = -nx, -ny
    else:
        nx, ny = nx / R, ny / R
    return (tx, ty), (nx, ny)


def _compute_turn_offset(pts: list[tuple[float, float]],
                         frac: float,
                         magnitude: float = 12.0) -> tuple[float, float]:
    """Outward-normal label offset for a turn at `frac` along a closed polyline.

    `pts` is the centerline in the normalized [0,1] frame. `frac` is 0..1 along the
    polyline by index (lovely's marker; close enough since pts is arc-length-resampled
    by import_tracks). Returns (ox, oy) in the renderer's offset units: the widget
    multiplies by `CR / 8.0` (CR is the turn-circle radius in pixels), so a magnitude
    of ~12 yields an offset of ~1.5 * CR pixels — clearly clear of the track.
    """
    vecs = _tangent_and_outward_normal(pts, frac)
    if vecs is None:
        return (0.0, 0.0)
    _, (nx, ny) = vecs
    return (round(nx * magnitude, 2), round(ny * magnitude, 2))


CLOSE_TURN_FRAC = 0.03  # turns within 3% of lap are considered "close"
TANGENT_SHIFT   = 22.0  # renderer-units; shoves close-pair labels along the track


def _load_lovely_turns(s1napse_slug: str,
                       pts_normalized: list[tuple[float, float]]
                       ) -> list[list]:
    """Load turn metadata for a track slug. Returns the renderer's tuple shape:
    [frac, label, name, ox, oy]. Empty list if no mapping or no file.

    For consecutive turns within CLOSE_TURN_FRAC of each other (chicanes, paired
    corners), the labels are shifted along the tangent so they don't stack on top
    of one another: earlier member shifts backward, later member shifts forward.
    """
    lovely_id = LOVELY_ID_MAP.get(s1napse_slug)
    if lovely_id is None:
        return []
    src = LOVELY_DIR / f'{lovely_id}.json'
    if not src.exists():
        return []
    with open(src) as f:
        data = json.load(f)
    raw = data.get('turn', []) or []
    keyed = [t for t in raw if isinstance(t.get('marker'), (int, float))]
    keyed.sort(key=lambda t: t['marker'])

    fracs = [float(t['marker']) for t in keyed]
    names = [str(t.get('name') or '') for t in keyed]
    m = len(fracs)

    # Group consecutive close turns into clusters. A cluster is a list of indices
    # (0-based into `fracs`) where each pair of neighbors is within CLOSE_TURN_FRAC.
    clusters: list[list[int]] = []
    if m > 0:
        cur = [0]
        for i in range(1, m):
            if (fracs[i] - fracs[i - 1]) < CLOSE_TURN_FRAC:
                cur.append(i)
            else:
                clusters.append(cur)
                cur = [i]
        clusters.append(cur)
        # Wrap: if first and last cluster are close across the lap boundary, merge.
        if (len(clusters) > 1
                and ((fracs[0] - fracs[-1]) % 1.0) < CLOSE_TURN_FRAC):
            clusters[0] = clusters[-1] + clusters[0]
            clusters.pop()

    pn = len(pts_normalized)

    # Per-turn offset, indexed 0..m-1.
    offsets: list[tuple[float, float]] = [(0.0, 0.0)] * m

    for cluster in clusters:
        if len(cluster) == 1:
            i = cluster[0]
            vecs = _tangent_and_outward_normal(pts_normalized, fracs[i])
            if vecs is None:
                continue
            _, (nx, ny) = vecs
            offsets[i] = (nx * 17.0, ny * 17.0)
            continue

        # Multi-turn cluster: lay out all members along a single shared axis from
        # first to last, evenly spaced. This is symmetric and handles 2, 3, or
        # more members the same way.
        first_i, last_i = cluster[0], cluster[-1]
        fpx, fpy = pts_normalized[int(fracs[first_i] * pn) % pn]
        lpx, lpy = pts_normalized[int(fracs[last_i]  * pn) % pn]
        ax, ay = (lpx - fpx), (lpy - fpy)
        aL = math.hypot(ax, ay)
        if aL > 0:
            ax, ay = ax / aL, ay / aL
        else:
            ax, ay = 1.0, 0.0  # degenerate fallback

        # Outward direction: perpendicular to the cluster axis, pointing away from
        # the track centroid (consistent for all members of the cluster).
        cx = sum(p[0] for p in pts_normalized) / pn
        cy = sum(p[1] for p in pts_normalized) / pn
        mid_px, mid_py = (fpx + lpx) / 2.0, (fpy + lpy) / 2.0
        out_seed_x, out_seed_y = (mid_px - cx), (mid_py - cy)
        # Project out perpendicular to axis.
        perp_x, perp_y = -ay, ax
        if perp_x * out_seed_x + perp_y * out_seed_y < 0:
            perp_x, perp_y = -perp_x, -perp_y

        # Spread evenly along the axis: -SPAN/2 .. +SPAN/2 around cluster midpoint.
        SPAN = TANGENT_SHIFT * 2.0
        OUTWARD = 14.0
        k = len(cluster)
        for j, i in enumerate(cluster):
            if k == 1:
                t = 0.0
            else:
                t = (j / (k - 1) - 0.5) * SPAN
            ox = ax * t + perp_x * OUTWARD
            oy = ay * t + perp_y * OUTWARD
            offsets[i] = (ox, oy)

    # Suppress duplicate names within a cluster: a chicane named "Variante Ascari"
    # 3 times reads as visual clutter; keep the name on the first member only.
    display_names = list(names)
    for cluster in clusters:
        first = cluster[0]
        for i in cluster[1:]:
            if names[i] == names[first]:
                display_names[i] = ''

    out: list[list] = []
    for idx in range(1, m + 1):
        i = idx - 1
        ox, oy = offsets[i]
        out.append([round(fracs[i], 4), str(idx), display_names[i], round(ox, 2), round(oy, 2)])
    return out


def convert(name: str, force: bool) -> str:
    key = slug(name)
    dst = DST_DIR / f'{key}.json'
    if dst.exists() and not force:
        return f'SKIP  {name:24s} -> {dst.name} (exists)'

    track_csv = TRACKS_DIR / f'{name}.csv'
    raceln_csv = RACELN_DIR / f'{name}.csv'
    if not track_csv.exists():
        return f'FAIL  {name:24s} (no track csv)'

    track_raw = load_xy(track_csv)
    if len(track_raw) < 10:
        return f'FAIL  {name:24s} (only {len(track_raw)} track pts)'

    length = int(round(polyline_length(track_raw)))

    # Resample centerline to N_OUT evenly-spaced pts (arc-length).
    track_rs = resample_closed(track_raw, N_OUT)
    # Shared bounds derived from the centerline so both curves fit in the same frame.
    min_x, max_x, min_y, max_y = bounds(track_rs)

    pts = normalize_with_frame(track_rs, min_x, max_x, min_y, max_y)
    pts_tuples = [(p[0], p[1]) for p in pts]
    turns = _load_lovely_turns(key, pts_tuples)
    data = {
        'name':      name,
        'track_key': key,
        'length_m':  length,
        'pts':       pts,
        'turns':     turns,
        'source':    SOURCE_TAG,
    }
    if turns:
        data['turn_source'] = LOVELY_SOURCE_TAG

    # Raceline: normalize with track's frame, resample, compute + smooth + normalize curvature.
    note = ''
    if raceln_csv.exists():
        raceln_raw = load_xy(raceln_csv)
        if len(raceln_raw) >= 10:
            raceln_rs = resample_closed(raceln_raw, N_OUT)
            raceln_norm = normalize_with_frame(raceln_rs, min_x, max_x, min_y, max_y)
            curv_raw    = curvature(raceln_rs)
            curv_smooth = gaussian_smooth_closed(curv_raw, SMOOTH_SIGMA)
            curv_norm   = percentile_normalize(curv_smooth, 0.05, 0.95)
            data['raceline']      = raceln_norm
            data['raceline_curv'] = [round(c, 4) for c in curv_norm]
            note = f', raceline ({len(raceln_norm)} pts)'
        else:
            note = ', no raceline (too few pts)'
    else:
        note = ', no raceline csv'

    DST_DIR.mkdir(parents=True, exist_ok=True)
    with open(dst, 'w') as f:
        json.dump(data, f, indent=2)
    turn_note = f', {len(turns)} turns' if turns else ''
    return f'OK    {name:24s} -> {dst.name}  ({length} m, {len(pts)} pts{note}{turn_note})'


def main():
    force = '--force' in sys.argv
    if not TRACKS_DIR.exists():
        print(f'Source dir not found: {TRACKS_DIR}')
        sys.exit(1)
    csvs = sorted(TRACKS_DIR.glob('*.csv'))
    if not csvs:
        print(f'No CSVs in {TRACKS_DIR}')
        sys.exit(1)
    for csv_path in csvs:
        print(convert(csv_path.stem, force))


if __name__ == '__main__':
    main()
