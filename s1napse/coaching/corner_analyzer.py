"""Per-corner performance scoring and personal-best comparison."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .models import Corner, CornerPerformance, CornerBest
from ..track_recorder import _get_tracks_dir
from ..utils import _interp_time_at_dist


# ---------------------------------------------------------------------------
# Grade thresholds (seconds slower than personal best)
# ---------------------------------------------------------------------------
_GREEN_THRESHOLD = 0.15
_YELLOW_THRESHOLD = 0.50


def analyze_corners(
    corners: list[Corner],
    lap_data: dict,
    lap_number: int,
    bests: dict[int, CornerBest],
) -> list[CornerPerformance]:
    """Score each corner for the given lap against personal bests.

    Parameters
    ----------
    corners : list[Corner]
        Detected corners for this track.
    lap_data : dict
        The ``data`` dict from a stored lap.
    lap_number : int
        Lap number for this analysis.
    bests : dict[int, CornerBest]
        Personal bests keyed by corner_id.  Updated in-place when a corner
        improves.

    Returns
    -------
    list[CornerPerformance]
    """
    dist = lap_data['dist_m']
    speed = lap_data['speed']
    time_ms = lap_data['time_ms']
    brake = lap_data['brake']
    throttle = lap_data['throttle']

    results: list[CornerPerformance] = []

    for corner in corners:
        perf = _score_corner(corner, dist, speed, time_ms, brake, throttle,
                             lap_number, bests.get(corner.corner_id))

        # Update personal best if this is faster
        _maybe_update_best(corner, perf, bests)

        results.append(perf)

    return results


# ---------------------------------------------------------------------------
# Internal scoring
# ---------------------------------------------------------------------------

def _score_corner(
    corner: Corner,
    dist: list,
    speed: list,
    time_ms: list,
    brake: list,
    throttle: list,
    lap_number: int,
    best: CornerBest | None,
) -> CornerPerformance:
    """Compute CornerPerformance for one corner."""

    # Find array indices for the corner zone
    entry_idx = _nearest_idx(dist, corner.entry_distance)
    turnin_idx = _nearest_idx(dist, corner.turn_in_distance)
    apex_idx = _nearest_idx(dist, corner.apex_distance)
    exit_idx = _nearest_idx(dist, corner.exit_distance)

    entry_speed = speed[turnin_idx]
    min_speed = min(speed[entry_idx:exit_idx + 1]) if entry_idx < exit_idx else speed[apex_idx]
    exit_speed = speed[exit_idx]

    braking_dist = corner.apex_distance - corner.braking_start_distance

    # Time in corner (entry to exit)
    t_entry = _interp_time_at_dist(dist, time_ms, corner.entry_distance)
    t_exit = _interp_time_at_dist(dist, time_ms, corner.exit_distance)
    time_in_corner = ((t_exit - t_entry) / 1000.0) if (t_entry is not None and t_exit is not None) else 0.0

    # Throttle application distance from apex
    throttle_app_dist = _find_throttle_application(
        apex_idx, exit_idx, dist, throttle)

    # Delta vs best
    delta = 0.0
    if best is not None:
        delta = time_in_corner - best.best_time_in_corner

    # Grade
    if best is None:
        grade = "green"  # first lap baseline
    elif delta <= _GREEN_THRESHOLD:
        grade = "green"
    elif delta <= _YELLOW_THRESHOLD:
        grade = "yellow"
    else:
        grade = "red"

    # Primary issue detection
    primary_issue, tip = _detect_primary_issue(
        corner, entry_speed, min_speed, exit_speed,
        throttle_app_dist, delta, best)

    return CornerPerformance(
        corner=corner,
        lap_number=lap_number,
        entry_speed=round(entry_speed, 1),
        min_speed=round(min_speed, 1),
        exit_speed=round(exit_speed, 1),
        braking_distance=round(braking_dist, 1),
        time_in_corner=round(time_in_corner, 3),
        delta_vs_best=round(delta, 3),
        throttle_application_distance=round(throttle_app_dist, 1),
        grade=grade,
        primary_issue=primary_issue,
        tip=tip,
    )


def _find_throttle_application(apex_idx: int, exit_idx: int,
                                dist: list, throttle: list) -> float:
    """Distance from apex where throttle first exceeds 20 %."""
    apex_dist = dist[apex_idx]
    for i in range(apex_idx, min(exit_idx + 1, len(dist))):
        if throttle[i] > 20.0:
            return dist[i] - apex_dist
    return dist[min(exit_idx, len(dist) - 1)] - apex_dist


def _detect_primary_issue(
    corner: Corner,
    entry_speed: float,
    min_speed: float,
    exit_speed: float,
    throttle_app_dist: float,
    delta: float,
    best: CornerBest | None,
) -> tuple[str, str]:
    """Pick the single biggest issue and an actionable tip.

    Returns (issue_key, tip_string).
    """
    if best is None:
        return "baseline", "Building your baseline — keep pushing!"

    if delta <= 0.1:
        return "great", "You nailed this corner!"

    # Rank issues by estimated time impact
    issues: list[tuple[float, str, str]] = []

    # Braked too early
    brake_delta_m = corner.braking_start_distance - best.brake_start_distance
    if brake_delta_m > 10:
        issues.append((
            brake_delta_m * 0.03,
            "braked_early",
            f"Try braking ~{int(brake_delta_m)}m later — you have room.",
        ))

    # Braked too late (entry speed much higher but min speed much lower)
    if entry_speed > best.entry_speed + 5 and min_speed < best.min_speed - 5:
        issues.append((
            abs(delta),
            "braked_late",
            "You carried too much speed in — brake a touch earlier to keep a higher minimum speed.",
        ))

    # Too slow at apex
    apex_deficit = best.min_speed - min_speed
    if apex_deficit > 3:
        issues.append((
            apex_deficit * 0.02,
            "slow_apex",
            f"Apex speed is {apex_deficit:.0f} km/h below your best — carry a bit more speed through the turn.",
        ))

    # Slow exit
    exit_deficit = best.exit_speed - exit_speed
    if exit_deficit > 3:
        issues.append((
            exit_deficit * 0.025,
            "slow_exit",
            f"Exit speed is {exit_deficit:.0f} km/h below your best — get on the throttle earlier.",
        ))

    # Late throttle
    throttle_delta = throttle_app_dist - best.throttle_application_distance
    if throttle_delta > 5:
        issues.append((
            throttle_delta * 0.02,
            "late_throttle",
            f"You're picking up the throttle {throttle_delta:.0f}m later than your best — start at 30 % right at the apex.",
        ))

    # Hesitant braking
    if best.peak_brake_pct > 0:
        brake_deficit = best.peak_brake_pct - 0  # filled in by braking analyzer
        # placeholder — will be supplemented by braking analysis

    if not issues:
        return "minor", f"Small time loss (+{delta:.2f}s) — keep building consistency."

    # Pick highest-impact issue
    issues.sort(key=lambda t: t[0], reverse=True)
    return issues[0][1], issues[0][2]


# ---------------------------------------------------------------------------
# Personal bests
# ---------------------------------------------------------------------------

def _maybe_update_best(corner: Corner, perf: CornerPerformance,
                       bests: dict[int, CornerBest]) -> None:
    """Update personal best for this corner if the current lap is faster."""
    cid = corner.corner_id
    current_time = perf.time_in_corner
    if current_time <= 0:
        return
    if cid not in bests or current_time < bests[cid].best_time_in_corner:
        bests[cid] = CornerBest(
            corner_id=cid,
            best_time_in_corner=current_time,
            entry_speed=perf.entry_speed,
            min_speed=perf.min_speed,
            exit_speed=perf.exit_speed,
            braking_distance=perf.braking_distance,
            brake_start_distance=corner.braking_start_distance,
            peak_brake_pct=0.0,  # filled by braking analyzer
            throttle_application_distance=perf.throttle_application_distance,
        )


def _nearest_idx(dist: list, target: float) -> int:
    """Binary search for the nearest index to target distance."""
    lo, hi = 0, len(dist) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if dist[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _bests_path(track_key: str) -> Path:
    return _get_tracks_dir() / f'{track_key}_personal_bests.json'


def save_bests(track_key: str, bests: dict[int, CornerBest]) -> None:
    path = _bests_path(track_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {str(k): v.to_dict() for k, v in bests.items()}
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def load_bests(track_key: str) -> dict[int, CornerBest]:
    path = _bests_path(track_key)
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return {int(k): CornerBest.from_dict(v) for k, v in data.items()}
    except Exception:
        return {}
