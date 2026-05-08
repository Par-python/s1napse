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
        """Return the highest-priority active headline."""
        # P1: rival-pit alert (within last 30 s of detection -- caller's clock)
        # The caller sets *_pitted_at; treat any non-None as "recent enough"
        # for the headline. UI may further age it out for the card display.
        if self.rival_ahead_pitted_at is not None:
            return Headline('UNDERCUT NOW · CAR AHEAD PITTED', 'red')
        if self.rival_behind_pitted_at is not None:
            return Headline('OVERCUT NOW · CAR BEHIND PITTED', 'red')

        # P2: pit window currently open
        if (self.pit_window_open_lap is not None
                and self.pit_window_close_lap is not None
                and self.pit_window_open_lap <= self.current_lap_count
                <= self.pit_window_close_lap):
            return Headline(
                f'PIT WINDOW OPEN · CLOSES LAP {self.pit_window_close_lap}',
                'red')

        # P3: fuel critical (<= 2 laps left)
        if self.fuel_laps_left is not None and self.fuel_laps_left <= 2.0:
            return Headline(
                f'FUEL: {self.fuel_laps_left:.1f} LAPS LEFT — SAVE NOW', 'red')

        # P4: tyre cliff approaching (projected >= 1.5 s/lap loss within 2 laps)
        if (self.deg_slope_s_per_lap is not None
                and self.deg_slope_s_per_lap > 0
                and (1.5 / self.deg_slope_s_per_lap) <= 2.0):
            laps_to_cliff = round(1.5 / self.deg_slope_s_per_lap, 1)
            return Headline(
                f'TYRES: {laps_to_cliff} LAPS TO 1.5s/LAP DROP', 'amber')

        # Default
        return Headline('STRATEGY: STABLE', 'neutral')


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
        self._gap_ahead_buffer: list[tuple[float, int]] = []   # (clock_s, gap_ms)
        self._gap_behind_buffer: list[tuple[float, int]] = []
        self._pit_loss_s = 22.0       # default ACC pit loss
        self._jump_threshold_s = self._pit_loss_s * 0.7   # 15.4 s
        self._suppression_s = 60.0

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
        self._recompute_rival_watch(sample)
        self._recompute_temp_watch(sample)

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

        # The pit window has two edges:
        #   open  = earliest lap you can pit and still safely finish
        #           (assume tyres are ready ~3 laps in — heat them up first)
        #   close = latest lap you must pit by (fuel-driven hard limit, OR
        #           tyre-cliff projection, whichever comes first)
        if self._fuel_per_lap_history and fuel_now > 0:
            avg_fuel = sum(self._fuel_per_lap_history[-3:]) / len(
                self._fuel_per_lap_history[-3:])
            if avg_fuel > 0:
                laps_left = fuel_now / avg_fuel
                s.fuel_laps_left = round(laps_left, 1)
                # Fuel hard limit: must pit by this lap (or run out)
                fuel_hard_limit_lap = s.current_lap_count + int(laps_left)
            else:
                s.fuel_laps_left = None
                fuel_hard_limit_lap = None
        else:
            s.fuel_laps_left = None
            fuel_hard_limit_lap = None

        # Open edge: 3 laps from now (warmup heuristic) OR now if past mid-stint
        if fuel_hard_limit_lap is not None:
            mid_stint = s.current_lap_count + max(
                1, (fuel_hard_limit_lap - s.current_lap_count) // 2
            )
            s.pit_window_open_lap = mid_stint
        else:
            s.pit_window_open_lap = None

        # Close edge: tyre cliff OR fuel hard limit, whichever comes first
        tyre_close_lap = None
        if s.deg_slope_s_per_lap and s.deg_slope_s_per_lap > 0:
            cliff_laps_ahead = self._tyre_cliff_threshold_s / s.deg_slope_s_per_lap
            tyre_close_lap = s.current_lap_count + int(cliff_laps_ahead)

        candidates = [c for c in (fuel_hard_limit_lap, tyre_close_lap) if c is not None]
        s.pit_window_close_lap = min(candidates) if candidates else None

    def _recompute_rival_watch(self, sample: dict) -> None:
        """Detect rival pit by sudden gap jump (>= pit_loss * 0.7 within ~5 s)."""
        import time as _time
        s = self._state
        clock = sample.get('_clock_s', _time.monotonic())
        gap_a = sample.get('gap_ahead', 0)
        gap_b = sample.get('gap_behind', 0)
        s.last_gap_ahead_ms = gap_a
        s.last_gap_behind_ms = gap_b

        # Maintain a 30-second rolling buffer of (clock, gap) pairs
        self._gap_ahead_buffer.append((clock, gap_a))
        self._gap_behind_buffer.append((clock, gap_b))
        cutoff = clock - 30.0
        self._gap_ahead_buffer = [(t, g) for t, g in self._gap_ahead_buffer
                                   if t >= cutoff]
        self._gap_behind_buffer = [(t, g) for t, g in self._gap_behind_buffer
                                    if t >= cutoff]

        for buf, attr in (
            (self._gap_ahead_buffer, 'rival_ahead_pitted_at'),
            (self._gap_behind_buffer, 'rival_behind_pitted_at'),
        ):
            if len(buf) < 2:
                continue
            current_t, current_g = buf[-1]
            # Compare against a sample ~5s ago (or oldest if buffer is short)
            past_t, past_g = next(
                ((t, g) for t, g in buf if current_t - t >= 5.0),
                buf[0])
            jump_s = (current_g - past_g) / 1000.0
            if abs(jump_s) >= self._jump_threshold_s:
                last_fired = getattr(s, attr)
                if last_fired is None or (current_t - last_fired) > self._suppression_s:
                    setattr(s, attr, current_t)

    def _recompute_temp_watch(self, sample: dict) -> None:
        s = self._state
        road = sample.get('road_temp', None)
        air = sample.get('air_temp', None)
        pit_exit = sample.get('_pit_exit', False)

        if road is not None:
            s.track_temp_c = float(road)
            if s.track_temp_at_stint_start_c is None or pit_exit:
                s.track_temp_at_stint_start_c = float(road)
        if air is not None:
            s.air_temp_c = float(air)
