"""Runtime accessor for Lovely-Sim-Racing/lovely-track-data turn metadata.

Both `tools/import_tracks.py` (build-time, against TUMFTM CSVs) and
`s1napse/track_recorder.py` (runtime, against live-recorded telemetry) import
from here so the Lovely-merge logic stays in a single place.
"""

import json
import math
from pathlib import Path

LOVELY_DIR = Path(__file__).resolve().parent / 'lovely-track-data'
LOVELY_SOURCE_TAG = 'Lovely-Sim-Racing/lovely-track-data (CC BY-NC-SA 4.0)'

# s1napse track slug (slug-of-ACC-Static.track) -> Lovely's ACC trackId (their filename).
# Slugs follow the rule in s1napse/track_recorder.py (lowercase, [^a-z0-9_] -> _).
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

CLOSE_TURN_FRAC = 0.03  # turns within 3% of lap are considered "close"
TANGENT_SHIFT   = 22.0  # renderer-units; shoves close-pair labels along the track


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
        nx, ny = ty, -tx
        if _signed_area(pts) < 0:
            nx, ny = -nx, -ny
    else:
        nx, ny = nx / R, ny / R
    return (tx, ty), (nx, ny)


def _compute_turn_offset(pts: list[tuple[float, float]],
                         frac: float,
                         magnitude: float = 12.0) -> tuple[float, float]:
    """Outward-normal label offset for a turn at `frac` along a closed polyline."""
    vecs = _tangent_and_outward_normal(pts, frac)
    if vecs is None:
        return (0.0, 0.0)
    _, (nx, ny) = vecs
    return (round(nx * magnitude, 2), round(ny * magnitude, 2))


def load_turns(s1napse_slug: str,
               pts_normalized: list[tuple[float, float]]
               ) -> list[list]:
    """Load turn metadata for a track slug. Returns the renderer's tuple shape:
    [frac, label, name, ox, oy]. Empty list if no mapping or no file."""
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
        if (len(clusters) > 1
                and ((fracs[0] - fracs[-1]) % 1.0) < CLOSE_TURN_FRAC):
            clusters[0] = clusters[-1] + clusters[0]
            clusters.pop()

    pn = len(pts_normalized)
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

        first_i, last_i = cluster[0], cluster[-1]
        fpx, fpy = pts_normalized[int(fracs[first_i] * pn) % pn]
        lpx, lpy = pts_normalized[int(fracs[last_i]  * pn) % pn]
        ax, ay = (lpx - fpx), (lpy - fpy)
        aL = math.hypot(ax, ay)
        if aL > 0:
            ax, ay = ax / aL, ay / aL
        else:
            ax, ay = 1.0, 0.0

        cx = sum(p[0] for p in pts_normalized) / pn
        cy = sum(p[1] for p in pts_normalized) / pn
        mid_px, mid_py = (fpx + lpx) / 2.0, (fpy + lpy) / 2.0
        out_seed_x, out_seed_y = (mid_px - cx), (mid_py - cy)
        perp_x, perp_y = -ay, ax
        if perp_x * out_seed_x + perp_y * out_seed_y < 0:
            perp_x, perp_y = -perp_x, -perp_y

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
