"""Automatic corner detection from a completed lap's telemetry."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

try:
    from scipy.signal import savgol_filter
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

from .models import Corner
from ..track_recorder import _get_tracks_dir


# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
_STEER_THRESHOLD_FRAC = 0.12   # 12 % of max observed |steering|
_MIN_CORNER_DIST_M = 50.0      # minimum sustained distance to count as a corner
_MERGE_GAP_M = 30.0            # merge corners closer than this
_BRAKE_THRESHOLD_PCT = 5.0     # brake % threshold for braking-start detection
_SAVGOL_WINDOW = 21            # Savitzky-Golay window (must be odd)
_SAVGOL_ORDER = 3              # polynomial order


def detect_corners(lap_data: dict) -> list[Corner]:
    """Detect corners from a completed lap's data arrays.

    Parameters
    ----------
    lap_data : dict
        The ``data`` dict from a stored lap (keys: ``dist_m``, ``steer_deg``,
        ``speed``, ``brake``, ``throttle``).

    Returns
    -------
    list[Corner]
        Detected corners sorted by entry distance.
    """
    dist = np.asarray(lap_data['dist_m'], dtype=np.float64)
    steer = np.asarray(lap_data['steer_deg'], dtype=np.float64)
    speed = np.asarray(lap_data['speed'], dtype=np.float64)
    brake = np.asarray(lap_data['brake'], dtype=np.float64)
    throttle = np.asarray(lap_data['throttle'], dtype=np.float64)

    if len(dist) < _SAVGOL_WINDOW + 2:
        return []

    # ── 1. Smooth the steering signal ────────────────────────────────────
    window = min(_SAVGOL_WINDOW, len(steer) - 1)
    if window % 2 == 0:
        window -= 1
    if window < 5:
        return []
    if _HAS_SCIPY:
        smooth_steer = savgol_filter(steer, window, _SAVGOL_ORDER)
    else:
        # Fallback: simple moving average
        kernel = np.ones(window) / window
        smooth_steer = np.convolve(steer, kernel, mode='same')

    # ── 2. Threshold: fraction of max observed |steering| ────────────────
    max_abs_steer = np.max(np.abs(smooth_steer))
    if max_abs_steer < 1.0:
        return []  # essentially no steering — oval or straight
    threshold = max_abs_steer * _STEER_THRESHOLD_FRAC

    # ── 3. Find sustained regions above threshold ────────────────────────
    in_corner = np.abs(smooth_steer) > threshold
    raw_segments = _contiguous_regions(in_corner)

    # Filter by minimum distance span
    segments = []
    for start_idx, end_idx in raw_segments:
        span = dist[end_idx] - dist[start_idx]
        if span >= _MIN_CORNER_DIST_M:
            segments.append((start_idx, end_idx))

    # ── 4. Merge segments that are close together ────────────────────────
    segments = _merge_segments(segments, dist, _MERGE_GAP_M)

    # ── 5. Build Corner objects ──────────────────────────────────────────
    corners: list[Corner] = []
    for cid, (seg_start, seg_end) in enumerate(segments, start=1):
        turn_in_dist = dist[seg_start]
        exit_dist = dist[seg_end]

        # Direction: sign of mean steering in the segment
        mean_steer = np.mean(smooth_steer[seg_start:seg_end + 1])
        direction = "LEFT" if mean_steer < 0 else "RIGHT"

        # Apex: point of minimum speed in the segment
        seg_speed = speed[seg_start:seg_end + 1]
        apex_local = int(np.argmin(seg_speed))
        apex_idx = seg_start + apex_local
        apex_dist = dist[apex_idx]

        # Braking start: search backward from turn-in for brake > threshold
        braking_start = _find_braking_start(seg_start, dist, brake)

        # Entry distance is the braking start (or turn-in if no braking found)
        entry_dist = braking_start if braking_start < turn_in_dist else turn_in_dist

        # Refine exit: where steering drops AND throttle > 80%
        exit_dist = _refine_exit(seg_end, dist, smooth_steer, throttle,
                                 threshold, exit_dist)

        corners.append(Corner(
            corner_id=cid,
            direction=direction,
            entry_distance=round(entry_dist, 1),
            turn_in_distance=round(turn_in_dist, 1),
            apex_distance=round(apex_dist, 1),
            exit_distance=round(exit_dist, 1),
            braking_start_distance=round(braking_start, 1),
        ))

    return corners


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _contiguous_regions(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return (start, end) index pairs for contiguous True regions."""
    diff = np.diff(mask.astype(int))
    starts = np.where(diff == 1)[0] + 1
    ends = np.where(diff == -1)[0]

    # Handle edge cases: region starts at index 0 or ends at last index
    if mask[0]:
        starts = np.concatenate(([0], starts))
    if mask[-1]:
        ends = np.concatenate((ends, [len(mask) - 1]))

    return list(zip(starts.tolist(), ends.tolist()))


def _merge_segments(segments: list[tuple[int, int]], dist: np.ndarray,
                    gap_m: float) -> list[tuple[int, int]]:
    """Merge segment pairs whose gap is less than *gap_m* metres."""
    if not segments:
        return segments
    merged = [segments[0]]
    for start, end in segments[1:]:
        prev_start, prev_end = merged[-1]
        if dist[start] - dist[prev_end] < gap_m:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def _find_braking_start(turn_in_idx: int, dist: np.ndarray,
                        brake: np.ndarray) -> float:
    """Search backward from turn-in to find where braking began."""
    # Look up to 500m before turn-in
    min_dist = dist[turn_in_idx] - 500.0
    for i in range(turn_in_idx - 1, -1, -1):
        if dist[i] < min_dist:
            break
        if brake[i] < _BRAKE_THRESHOLD_PCT:
            # Found the point where brake drops below threshold going backward;
            # the braking start is the next sample forward.
            return dist[min(i + 1, turn_in_idx)]
    return dist[turn_in_idx]  # fallback: no braking detected


def _refine_exit(seg_end: int, dist: np.ndarray, smooth_steer: np.ndarray,
                 throttle: np.ndarray, threshold: float,
                 default_exit: float) -> float:
    """Extend exit to where steering is low AND throttle is high."""
    search_limit = min(seg_end + 200, len(dist) - 1)
    for i in range(seg_end, search_limit + 1):
        if abs(smooth_steer[i]) < threshold and throttle[i] > 80.0:
            return dist[i]
    return default_exit


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _corners_path(track_key: str) -> Path:
    return _get_tracks_dir() / f'{track_key}_corners.json'


def save_corners(track_key: str, corners: list[Corner]) -> None:
    """Save detected corners to tracks/{track_key}_corners.json."""
    path = _corners_path(track_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump([c.to_dict() for c in corners], f, indent=2)


def load_corners(track_key: str) -> list[Corner] | None:
    """Load cached corners. Returns None if no cache exists."""
    path = _corners_path(track_key)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        return [Corner.from_dict(d) for d in data]
    except Exception:
        return None
