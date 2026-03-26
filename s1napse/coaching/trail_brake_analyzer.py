"""Trail braking detection and coaching state machine."""

from __future__ import annotations

import numpy as np

from .models import Corner, TrailBrakeAnalysis


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
_BRAKE_NOISE_FLOOR = 3.0     # brake % above this counts as "on the brake"
_STEER_FRAC = 0.10            # 10 % of max |steering| = "actively turning"
_ABRUPT_DROP_DIST_M = 10.0   # brake drops from >20 % to 0 in less than this → abrupt


def analyze_trail_braking(
    corners: list[Corner],
    lap_data: dict,
    lap_number: int,
    stage_history: dict[int, int],
) -> list[TrailBrakeAnalysis]:
    """Detect trail braking for every corner.

    Parameters
    ----------
    corners : list[Corner]
        Detected corners.
    lap_data : dict
        Completed lap data arrays.
    lap_number : int
        Current lap.
    stage_history : dict[int, int]
        Per-corner coaching stage (0/1/2), updated in-place as the driver
        progresses.

    Returns
    -------
    list[TrailBrakeAnalysis]
    """
    dist = np.asarray(lap_data['dist_m'], dtype=np.float64)
    brake = np.asarray(lap_data['brake'], dtype=np.float64)
    steer = np.asarray(lap_data['steer_deg'], dtype=np.float64)

    max_abs_steer = np.max(np.abs(steer))
    steer_threshold = max_abs_steer * _STEER_FRAC if max_abs_steer > 1.0 else 5.0

    results: list[TrailBrakeAnalysis] = []

    for corner in corners:
        tb = _analyze_single(corner, dist, brake, steer,
                             steer_threshold, lap_number)

        # Advance coaching stage
        cid = corner.corner_id
        prev_stage = stage_history.get(cid, 0)
        if tb.release_quality == "smooth":
            new_stage = 2
        elif tb.detected:
            new_stage = max(prev_stage, 1)
        else:
            new_stage = prev_stage  # don't regress
        stage_history[cid] = new_stage
        tb.stage = new_stage

        results.append(tb)

    return results


# ---------------------------------------------------------------------------
# Single-corner analysis
# ---------------------------------------------------------------------------

def _analyze_single(
    corner: Corner,
    dist: np.ndarray,
    brake: np.ndarray,
    steer: np.ndarray,
    steer_threshold: float,
    lap_number: int,
) -> TrailBrakeAnalysis:
    """Trail braking analysis for one corner."""

    turn_in_idx = _nearest(dist, corner.turn_in_distance)
    apex_idx = _nearest(dist, corner.apex_distance)
    exit_idx = _nearest(dist, corner.exit_distance)

    # Zone from turn-in to exit
    lo = turn_in_idx
    hi = min(exit_idx + 1, len(dist))
    if hi <= lo:
        return _empty(corner, lap_number)

    zone_dist = dist[lo:hi]
    zone_brake = brake[lo:hi]
    zone_steer = steer[lo:hi]

    # Overlap mask: brake on AND steering on
    overlap = (zone_brake > _BRAKE_NOISE_FLOOR) & (np.abs(zone_steer) > steer_threshold)

    if not np.any(overlap):
        return TrailBrakeAnalysis(
            corner=corner, lap_number=lap_number,
            detected=False, overlap_distance=0.0,
            overlap_entry_brake_pct=0.0, brake_release_gradient=0.0,
            brake_at_apex=0.0, release_quality="none", stage=0,
        )

    # Overlap distance
    overlap_indices = np.where(overlap)[0]
    first, last = overlap_indices[0], overlap_indices[-1]
    overlap_dist = float(zone_dist[last] - zone_dist[first])

    # Brake % at start of overlap (when steering begins)
    entry_brake = float(zone_brake[first])

    # Brake % at apex
    apex_local = max(0, min(apex_idx - lo, len(zone_brake) - 1))
    brake_at_apex = float(zone_brake[apex_local])

    # Brake release gradient (brake_pct per metre through overlap)
    if overlap_dist > 0:
        gradient = (entry_brake - float(zone_brake[last])) / overlap_dist
    else:
        gradient = 0.0

    # Classify release quality
    quality = _classify_release(zone_brake, zone_dist, first, last)

    return TrailBrakeAnalysis(
        corner=corner,
        lap_number=lap_number,
        detected=True,
        overlap_distance=round(overlap_dist, 1),
        overlap_entry_brake_pct=round(entry_brake, 1),
        brake_release_gradient=round(gradient, 3),
        brake_at_apex=round(brake_at_apex, 1),
        release_quality=quality,
        stage=0,  # updated by caller
    )


def _classify_release(
    zone_brake: np.ndarray,
    zone_dist: np.ndarray,
    first: int,
    last: int,
) -> str:
    """Classify trail brake release as smooth, abrupt, or none."""
    if last <= first:
        return "none"

    overlap_brake = zone_brake[first:last + 1]
    overlap_dist = zone_dist[first:last + 1]

    # Check for abrupt drop: brake goes from >20 % to <3 % in < 10 m
    for i in range(len(overlap_brake) - 1):
        if overlap_brake[i] > 20.0 and overlap_brake[i + 1] < _BRAKE_NOISE_FLOOR:
            drop_dist = overlap_dist[i + 1] - overlap_dist[i]
            if drop_dist < _ABRUPT_DROP_DIST_M:
                return "abrupt"

    # Check smoothness: low variance in the per-metre gradient
    if len(overlap_brake) < 3:
        return "smooth"

    diffs = np.diff(overlap_brake)
    dist_diffs = np.diff(overlap_dist)
    valid = dist_diffs > 0.1
    if not np.any(valid):
        return "smooth"

    gradients = diffs[valid] / dist_diffs[valid]
    grad_std = float(np.std(gradients))

    # Low variance = smooth release; high variance = jerky
    if grad_std < 1.5:
        return "smooth"
    return "abrupt"


def _empty(corner: Corner, lap_number: int) -> TrailBrakeAnalysis:
    return TrailBrakeAnalysis(
        corner=corner, lap_number=lap_number,
        detected=False, overlap_distance=0.0,
        overlap_entry_brake_pct=0.0, brake_release_gradient=0.0,
        brake_at_apex=0.0, release_quality="none", stage=0,
    )


def _nearest(arr: np.ndarray, target: float) -> int:
    return int(np.searchsorted(arr, target, side='left'))
