"""Live race-strategy engine.

Pure-logic: produces a StrategyState dataclass on every processed sample.
Has no Qt dependency. Mirrors the LapCoach / MathEngine pattern.

See docs/superpowers/specs/2026-04-25-strategy-tab-v1-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np


Severity = Literal['neutral', 'amber', 'red']


@dataclass
class Headline:
    """One-line strategy callout for the Race-tab banner."""
    text: str = 'STRATEGY: STABLE'
    severity: Severity = 'neutral'


@dataclass
class StrategyState:
    """Snapshot of all strategy-tab state. Recomputed on every sample.

    All fields are Optional / None when the underlying signal isn't yet
    available (e.g. degradation needs >=3 laps before fitting).
    """

    # --- Card 1: tyre-degradation projector ---
    deg_baseline_s: float | None = None          # average of laps 2-3
    deg_slope_s_per_lap: float | None = None     # linear-fit slope
    deg_r_squared: float | None = None           # fit confidence (0..1)
    deg_projected_end_pace_s: float | None = None
    deg_lap_times_s: list[float] = field(default_factory=list)

    # --- Card 2: pit-window estimator ---
    pit_window_open_lap: int | None = None       # earliest pit lap (fuel-driven)
    pit_window_close_lap: int | None = None      # latest pit lap (tyres-driven)
    current_lap_in_window: int | None = None

    # --- Card 3: fuel-save cost (rule of thumb) ---
    fuel_save_cost_s_per_lap_per_l: float = 0.7  # constant for v1

    # --- Card 4: rival-watch (gap-jump heuristic) ---
    rival_ahead_pitted_at: float | None = None   # monotonic timestamp (s)
    rival_behind_pitted_at: float | None = None
    last_gap_ahead_ms: int = 0
    last_gap_behind_ms: int = 0

    # --- Card 5: weather/track-temp watch ---
    track_temp_c: float | None = None
    track_temp_at_stint_start_c: float | None = None
    air_temp_c: float | None = None

    # --- Card 6: pit-strategy summary ---
    fuel_laps_left: float | None = None

    # --- Bookkeeping ---
    current_lap_count: int = 0

    def headline(self) -> Headline:
        """Return the highest-priority active headline.

        Fixed priority order (first active wins):
          1. Rival-pit alert
          2. Pit window open
          3. Fuel critical (<= 2 laps left)
          4. Tyres approaching cliff (projected >= 1.5 s/lap loss within 2 laps)
          5. Default
        """
        return Headline()  # placeholder for now -- Task 8 fills this in


class StrategyEngine:
    """Live race-strategy engine.

    Instantiate once per session. Call :meth:`update` for every processed
    raw telemetry sample. Read the latest snapshot via :attr:`state`.

    The engine never raises -- missing inputs simply leave the relevant
    StrategyState fields as None.
    """

    def __init__(self):
        self._state = StrategyState()
        self._fuel_per_lap_history: list[float] = []
        self._tyre_cliff_threshold_s = 1.5

    @property
    def state(self) -> StrategyState:
        return self._state

    def update(
        self,
        sample: dict,
        current_lap_data: dict,
        session_laps: list,
    ) -> None:
        """Recompute strategy state from the latest sample.

        Parameters
        ----------
        sample : dict
            One raw telemetry sample dict (matches the reader output schema).
        current_lap_data : dict
            The in-progress lap's per-channel arrays (TelemetryApp.current_lap_data).
        session_laps : list
            The list of completed laps (TelemetryApp.session_laps).
        """
        # Track current lap count for window math
        self._state.current_lap_count = max(
            (lap.get('lap_number', 0) for lap in session_laps), default=0)
        self._recompute_degradation(session_laps)
        self._recompute_pit_window(sample)

    def _recompute_degradation(self, session_laps: list) -> None:
        """Linear regression over trailing 3-5 lap times.

        Fills deg_baseline_s, deg_slope_s_per_lap, deg_r_squared,
        deg_projected_end_pace_s, deg_lap_times_s on self._state.
        Leaves them as None if fewer than 3 laps available.
        """
        s = self._state
        times = [lap.get('total_time_s', 0.0) for lap in session_laps
                 if lap.get('total_time_s', 0.0) > 0]
        s.deg_lap_times_s = list(times)

        if len(times) < 3:
            s.deg_baseline_s = None
            s.deg_slope_s_per_lap = None
            s.deg_r_squared = None
            s.deg_projected_end_pace_s = None
            return

        # Baseline: average of laps 2 and 3 (the first two settled laps)
        s.deg_baseline_s = round((times[1] + times[2]) / 2, 3)

        # Fit on the trailing 5 laps (or fewer if we don't have 5)
        window = times[-5:]
        x = np.arange(len(window))
        y = np.array(window)
        slope, intercept = np.polyfit(x, y, 1)
        s.deg_slope_s_per_lap = round(float(slope), 4)

        # R-squared for fit confidence
        y_pred = slope * x + intercept
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        s.deg_r_squared = (1.0 - ss_res / ss_tot) if ss_tot > 0 else 1.0

        # Projected end-of-stint pace: assume 5 more laps remaining (UI overrides this)
        s.deg_projected_end_pace_s = round(
            float(intercept + slope * (len(window) - 1 + 5)), 3)

    def _recompute_pit_window(self, sample: dict) -> None:
        """Compute pit window open (fuel) and close (tyre cliff) lap numbers."""
        s = self._state
        fuel_now = sample.get('fuel', 0.0)

        # Open edge: fuel-driven
        if self._fuel_per_lap_history and fuel_now > 0:
            avg_fuel = sum(self._fuel_per_lap_history[-3:]) / len(
                self._fuel_per_lap_history[-3:])
            if avg_fuel > 0:
                laps_left = fuel_now / avg_fuel
                s.fuel_laps_left = round(laps_left, 1)
                s.pit_window_open_lap = s.current_lap_count + int(laps_left)
            else:
                s.fuel_laps_left = None
                s.pit_window_open_lap = None
        else:
            s.fuel_laps_left = None
            s.pit_window_open_lap = None

        # Close edge: tyre cliff
        if s.deg_slope_s_per_lap and s.deg_slope_s_per_lap > 0:
            cliff_laps_ahead = self._tyre_cliff_threshold_s / s.deg_slope_s_per_lap
            s.pit_window_close_lap = s.current_lap_count + int(cliff_laps_ahead)
        else:
            s.pit_window_close_lap = None
