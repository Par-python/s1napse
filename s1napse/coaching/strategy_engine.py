"""Live race-strategy engine.

Pure-logic: produces a StrategyState dataclass on every processed sample.
Has no Qt dependency. Mirrors the LapCoach / MathEngine pattern.

See docs/superpowers/specs/2026-04-25-strategy-tab-v1-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


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
