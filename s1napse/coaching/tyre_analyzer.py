"""Tyre management analysis (single core-temp per tyre).

Full inner/middle/outer analysis is deferred until readers are extended.
This module works with the available single core temperature per corner.
"""

from __future__ import annotations

import numpy as np

from .models import TyreLapSummary


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
_BALANCE_DELTA_C = 4.0        # front-rear difference above this → biased
_PRESSURE_DRIFT_PSI = 1.5     # flag if pressure rises by more than this


def analyze_tyres(
    lap_data: dict,
    lap_number: int,
    history: list[TyreLapSummary],
    lap_times: list[float],
) -> TyreLapSummary:
    """Produce a tyre summary for the completed lap.

    Parameters
    ----------
    lap_data : dict
        Completed lap data arrays (keys include tyre_temp_fl, etc.).
    lap_number : int
        Current lap number.
    history : list[TyreLapSummary]
        Previous lap summaries (used for degradation/pressure drift).
    lap_times : list[float]
        All lap times so far (including this lap), for degradation checks.

    Returns
    -------
    TyreLapSummary
    """
    # Take average of the last quarter of the lap for a stable end-of-lap reading
    n = len(lap_data.get('tyre_temp_fl', []))
    if n == 0:
        return _empty(lap_number)

    quarter = max(1, n // 4)
    sl = slice(-quarter, None)

    fl = _avg(lap_data.get('tyre_temp_fl', []), sl)
    fr = _avg(lap_data.get('tyre_temp_fr', []), sl)
    rl = _avg(lap_data.get('tyre_temp_rl', []), sl)
    rr = _avg(lap_data.get('tyre_temp_rr', []), sl)

    pfl = _avg(lap_data.get('tyre_pressure_fl', []), sl)
    pfr = _avg(lap_data.get('tyre_pressure_fr', []), sl)
    prl = _avg(lap_data.get('tyre_pressure_rl', []), sl)
    prr = _avg(lap_data.get('tyre_pressure_rr', []), sl)

    front_avg = (fl + fr) / 2.0
    rear_avg = (rl + rr) / 2.0
    left_avg = (fl + rl) / 2.0
    right_avg = (fr + rr) / 2.0

    # Balance classification
    fr_delta = front_avg - rear_avg
    if abs(fr_delta) < _BALANCE_DELTA_C:
        balance = "balanced"
    elif fr_delta > 0:
        balance = "front-biased"
    else:
        balance = "rear-biased"

    # Build insight message
    msg = _build_message(balance, fr_delta, front_avg, rear_avg,
                         pfl, pfr, prl, prr, history, lap_times)

    return TyreLapSummary(
        lap_number=lap_number,
        temp_fl=round(fl, 1), temp_fr=round(fr, 1),
        temp_rl=round(rl, 1), temp_rr=round(rr, 1),
        pressure_fl=round(pfl, 2), pressure_fr=round(pfr, 2),
        pressure_rl=round(prl, 2), pressure_rr=round(prr, 2),
        front_avg=round(front_avg, 1), rear_avg=round(rear_avg, 1),
        left_avg=round(left_avg, 1), right_avg=round(right_avg, 1),
        balance=balance,
        message=msg,
    )


# ---------------------------------------------------------------------------
# Message generation
# ---------------------------------------------------------------------------

def _build_message(
    balance: str,
    fr_delta: float,
    front_avg: float,
    rear_avg: float,
    pfl: float, pfr: float, prl: float, prr: float,
    history: list[TyreLapSummary],
    lap_times: list[float],
) -> str:
    """Pick the most relevant tyre insight."""

    # 1. Pressure drift
    if history:
        first = history[0]
        drift = max(
            abs(pfl - first.pressure_fl),
            abs(pfr - first.pressure_fr),
            abs(prl - first.pressure_rl),
            abs(prr - first.pressure_rr),
        )
        if drift > _PRESSURE_DRIFT_PSI:
            return (
                f"Tyre pressures have climbed by {drift:.1f} PSI since the "
                f"start. Consider starting with lower pressures next session "
                f"so they land in the optimal window after a few laps."
            )

    # 2. Degradation check (temps dropping + lap times rising)
    if len(history) >= 3 and len(lap_times) >= 3:
        recent_temps = [
            (h.front_avg + h.rear_avg) / 2.0 for h in history[-3:]
        ]
        recent_times = lap_times[-3:]
        temps_falling = all(
            recent_temps[i] > recent_temps[i + 1] for i in range(len(recent_temps) - 1)
        )
        times_rising = all(
            recent_times[i] < recent_times[i + 1] for i in range(len(recent_times) - 1)
        )
        if temps_falling and times_rising:
            peak_lap = max(range(len(history)),
                           key=lambda i: (history[i].front_avg + history[i].rear_avg) / 2.0)
            return (
                f"Your tyres peaked around lap {history[peak_lap].lap_number} "
                f"and temps are now dropping while lap times increase. "
                f"This is normal tyre degradation — consider pitting soon "
                f"or driving at 95% to manage the remaining life."
            )

    # 3. Balance message
    if balance == "front-biased":
        return (
            f"Your front tyres are {abs(fr_delta):.0f} C hotter than the rears. "
            f"This usually means heavy braking or aggressive turn-in. "
            f"Lighter trail braking and earlier throttle would shift load to the rear."
        )
    if balance == "rear-biased":
        return (
            f"Your rear tyres are {abs(fr_delta):.0f} C hotter than the fronts. "
            f"This can mean aggressive throttle out of corners or a rear-biased setup."
        )

    return (
        f"Tyre temps are well balanced — "
        f"fronts {front_avg:.0f} C, rears {rear_avg:.0f} C."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _avg(arr: list, sl: slice) -> float:
    subset = arr[sl] if arr else []
    if not subset:
        return 0.0
    return float(np.mean(subset))


def _empty(lap_number: int) -> TyreLapSummary:
    return TyreLapSummary(
        lap_number=lap_number,
        temp_fl=0, temp_fr=0, temp_rl=0, temp_rr=0,
        pressure_fl=0, pressure_fr=0, pressure_rl=0, pressure_rr=0,
        front_avg=0, rear_avg=0, left_avg=0, right_avg=0,
        balance="unknown", message="No tyre data available.",
    )
