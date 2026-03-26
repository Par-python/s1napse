"""Braking zone analysis and brake-application-shape classification."""

from __future__ import annotations

import numpy as np

from .models import Corner, BrakingAnalysis, CornerBest


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
_BRAKE_ON_PCT = 5.0       # brake considered "on" above this %
_SPIKE_TIME_MS = 50       # time-to-peak below this → spike
_HESITANT_PEAK = 50.0     # peak below this % → possibly hesitant
_HESITANT_RAMP_MS = 200   # time-to-peak above this → hesitant


def analyze_braking(
    corners: list[Corner],
    lap_data: dict,
    lap_number: int,
    bests: dict[int, CornerBest],
) -> list[BrakingAnalysis]:
    """Classify braking for every corner in the lap.

    Parameters
    ----------
    corners : list[Corner]
        Detected corners for this track.
    lap_data : dict
        The ``data`` dict from a stored lap.
    lap_number : int
        Current lap number.
    bests : dict[int, CornerBest]
        Personal bests keyed by corner_id (used for delta comparison).

    Returns
    -------
    list[BrakingAnalysis]
    """
    dist = np.asarray(lap_data['dist_m'], dtype=np.float64)
    speed = np.asarray(lap_data['speed'], dtype=np.float64)
    brake = np.asarray(lap_data['brake'], dtype=np.float64)
    time_ms = np.asarray(lap_data['time_ms'], dtype=np.float64)

    results: list[BrakingAnalysis] = []

    for corner in corners:
        ba = _analyze_single(corner, dist, speed, brake, time_ms,
                             lap_number, bests.get(corner.corner_id))
        results.append(ba)

    return results


def compute_consistency(
    history: list[list[BrakingAnalysis]],
    n_laps: int = 5,
) -> float:
    """Compute braking consistency % over the last *n_laps* laps.

    Consistency is 100 % when brake_start_distance and peak_brake_pct
    are identical across laps for every corner.
    """
    recent = history[-n_laps:] if len(history) > n_laps else history
    if len(recent) < 2:
        return 100.0

    n_corners = len(recent[0]) if recent else 0
    if n_corners == 0:
        return 100.0

    scores: list[float] = []
    for cid_idx in range(n_corners):
        brake_dists = []
        peaks = []
        for lap_analyses in recent:
            if cid_idx < len(lap_analyses):
                ba = lap_analyses[cid_idx]
                brake_dists.append(ba.brake_start_distance)
                peaks.append(ba.peak_brake_pct)
        if len(brake_dists) >= 2:
            # Normalise stddev: perfect = 0 → 100 %, stddev ≥ 50m → 0 %
            dist_std = float(np.std(brake_dists))
            peak_std = float(np.std(peaks))
            dist_score = max(0.0, 1.0 - dist_std / 50.0)
            peak_score = max(0.0, 1.0 - peak_std / 30.0)
            scores.append((dist_score + peak_score) / 2.0)

    return round(float(np.mean(scores)) * 100, 1) if scores else 100.0


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _analyze_single(
    corner: Corner,
    dist: np.ndarray,
    speed: np.ndarray,
    brake: np.ndarray,
    time_ms: np.ndarray,
    lap_number: int,
    best: CornerBest | None,
) -> BrakingAnalysis:
    """Braking analysis for one corner."""

    # Find indices for the braking zone
    brake_start_idx = _nearest_idx_np(dist, corner.braking_start_distance)
    apex_idx = _nearest_idx_np(dist, corner.apex_distance)
    exit_idx = _nearest_idx_np(dist, corner.exit_distance)

    # Brake-on region: from brake_start to where brake drops back below threshold
    brake_end_idx = _find_brake_end(brake_start_idx, exit_idx, brake)

    brake_start_speed = float(speed[brake_start_idx])
    min_speed_val = float(np.min(speed[brake_start_idx:exit_idx + 1])) if brake_start_idx < exit_idx else float(speed[apex_idx])

    # Brake trace in the zone
    zone_brake = brake[brake_start_idx:brake_end_idx + 1]
    zone_time = time_ms[brake_start_idx:brake_end_idx + 1]

    peak_brake_pct = float(np.max(zone_brake)) if len(zone_brake) > 0 else 0.0
    peak_idx_local = int(np.argmax(zone_brake)) if len(zone_brake) > 0 else 0

    # Time to peak
    if len(zone_time) > 1 and peak_idx_local > 0:
        time_to_peak = int(zone_time[peak_idx_local] - zone_time[0])
    else:
        time_to_peak = 0

    # Classify shape
    shape = _classify_shape(peak_brake_pct, time_to_peak,
                            float(dist[brake_end_idx] - dist[brake_start_idx]))

    # Total brake duration in metres
    total_brake_m = float(dist[brake_end_idx] - dist[brake_start_idx])

    # Speed scrubbed
    speed_scrubbed = brake_start_speed - min_speed_val

    # Deceleration efficiency
    decel_eff = speed_scrubbed / total_brake_m if total_brake_m > 0 else 0.0

    # Delta vs best (metres: negative = later = braver)
    delta_m = 0.0
    if best is not None:
        delta_m = float(corner.braking_start_distance - best.brake_start_distance)

    return BrakingAnalysis(
        corner=corner,
        lap_number=lap_number,
        brake_start_distance=round(float(dist[brake_start_idx]), 1),
        brake_start_speed=round(brake_start_speed, 1),
        brake_start_delta_vs_best=round(delta_m, 1),
        peak_brake_pct=round(peak_brake_pct, 1),
        time_to_peak_ms=time_to_peak,
        brake_application_shape=shape,
        total_brake_duration_m=round(total_brake_m, 1),
        speed_scrubbed=round(speed_scrubbed, 1),
        deceleration_efficiency=round(decel_eff, 3),
    )


def _classify_shape(peak: float, time_to_peak_ms: int,
                    total_brake_m: float) -> str:
    """Classify brake application as progressive / spike / hesitant."""
    if peak > 70.0 and time_to_peak_ms < _SPIKE_TIME_MS:
        return "spike"
    if peak < _HESITANT_PEAK and time_to_peak_ms > _HESITANT_RAMP_MS:
        return "hesitant"
    return "progressive"


def _find_brake_end(start_idx: int, max_idx: int,
                    brake: np.ndarray) -> int:
    """Find index where brake drops back below _BRAKE_ON_PCT after start."""
    for i in range(start_idx + 1, min(max_idx + 1, len(brake))):
        if brake[i] < _BRAKE_ON_PCT:
            return i
    return min(max_idx, len(brake) - 1)


def _nearest_idx_np(arr: np.ndarray, target: float) -> int:
    return int(np.searchsorted(arr, target, side='left'))
