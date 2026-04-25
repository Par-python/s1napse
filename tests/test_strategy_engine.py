"""Tests for the StrategyEngine and its dataclasses."""

from s1napse.coaching.strategy_engine import StrategyState, Headline


class TestStrategyStateDefaults:
    def test_empty_state_has_stable_headline(self):
        state = StrategyState()
        h = state.headline()
        assert h.text == 'STRATEGY: STABLE'
        assert h.severity == 'neutral'

    def test_empty_state_no_pit_window(self):
        state = StrategyState()
        assert state.pit_window_open_lap is None
        assert state.pit_window_close_lap is None

    def test_empty_state_no_degradation(self):
        state = StrategyState()
        assert state.deg_baseline_s is None
        assert state.deg_slope_s_per_lap is None
        assert state.deg_r_squared is None

    def test_empty_state_no_rival_pit_alerts(self):
        state = StrategyState()
        assert state.rival_ahead_pitted_at is None
        assert state.rival_behind_pitted_at is None


class TestStrategyEngineSkeleton:
    def test_engine_can_be_instantiated(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        assert isinstance(eng.state, StrategyState)

    def test_update_accepts_three_args(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        # update(sample, current_lap_data, session_laps)
        eng.update({'gap_ahead': 0, 'gap_behind': 0}, {}, [])
        # No assertions on state yet -- just confirms the call doesn't raise.

    def test_state_property_returns_same_object(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        s1 = eng.state
        s2 = eng.state
        assert s1 is s2  # caller can read incrementally without copy


class TestDegradationProjector:
    def _laps(self, times):
        """Build minimal session_laps with given total_time_s values."""
        return [{'lap_number': i + 1, 'total_time_s': t,
                 'data': {'speed': [100]}}
                for i, t in enumerate(times)]

    def test_no_degradation_with_fewer_than_3_laps(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        eng.update({}, {}, self._laps([90.0, 90.5]))
        assert eng.state.deg_slope_s_per_lap is None
        assert eng.state.deg_baseline_s is None

    def test_linear_fit_on_clean_series(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        # 4 laps, each 0.2 s slower than the last
        eng.update({}, {}, self._laps([90.0, 90.2, 90.4, 90.6]))
        assert eng.state.deg_slope_s_per_lap is not None
        assert abs(eng.state.deg_slope_s_per_lap - 0.2) < 0.01
        assert eng.state.deg_r_squared is not None
        assert eng.state.deg_r_squared > 0.99  # near-perfect linear data

    def test_baseline_uses_laps_2_and_3(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        # Lap 1 is an outlap (slower), 2 and 3 are baseline, then deg
        eng.update({}, {}, self._laps([95.0, 90.0, 90.2, 90.4]))
        # baseline should be average of laps 2 and 3 = 90.1
        assert abs(eng.state.deg_baseline_s - 90.1) < 0.01

    def test_uses_only_trailing_5_laps(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        # 7 laps; only the last 5 should be in the fit
        # First two are huge outliers -- if the engine used them, slope would be very negative
        eng.update({}, {}, self._laps(
            [200.0, 200.0, 90.0, 90.1, 90.2, 90.3, 90.4]))
        # Slope should be ~0.1 (from the trailing 5: 90.0 to 90.4)
        assert abs(eng.state.deg_slope_s_per_lap - 0.1) < 0.05


class TestPitWindow:
    def _laps(self, times):
        return [{'lap_number': i + 1, 'total_time_s': t,
                 'data': {'speed': [100]}}
                for i, t in enumerate(times)]

    def test_no_window_without_fuel_history(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        # No completed laps -> no fuel/lap history
        eng.update({'fuel': 30.0}, {}, [])
        assert eng.state.pit_window_open_lap is None
        assert eng.state.pit_window_close_lap is None

    def test_window_open_when_fuel_runs_out_in_n_laps(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        # Three laps logged. Synthesize fuel state via repeated updates.
        # Lap 1: fuel = 90L start, 87L end -> 3L/lap
        # Lap 2: fuel = 87L start, 84L end -> 3L/lap
        # Lap 3: fuel = 84L start, 81L end -> 3L/lap
        # Current fuel: 30L -> ~10 laps left
        eng._fuel_per_lap_history = [3.0, 3.0, 3.0]  # internal seeding
        eng.update({'fuel': 30.0}, {},
                   self._laps([90.0, 90.0, 90.0]))
        assert eng.state.fuel_laps_left is not None
        assert abs(eng.state.fuel_laps_left - 10.0) < 0.5

    def test_window_close_from_tyre_cliff(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        eng._fuel_per_lap_history = [3.0]
        # Lap times degrading by 0.3s/lap. Baseline ~90.0; cliff at +1.5s = lap_5
        eng.update({'fuel': 30.0}, {},
                   self._laps([90.0, 90.0, 90.3, 90.6, 90.9]))
        # Cliff lap = current_lap + (1.5 / slope) = 5 + (1.5 / 0.3) = 10
        assert eng.state.pit_window_close_lap is not None
        assert 8 <= eng.state.pit_window_close_lap <= 12


class TestRivalWatch:
    def test_no_alert_when_gap_stable(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        # Feed steady gaps over 10 ticks (clock advances 1s each)
        for i in range(10):
            eng.update({'gap_ahead': 5000, 'gap_behind': 4000,
                        '_clock_s': float(i)}, {}, [])
        assert eng.state.rival_ahead_pitted_at is None
        assert eng.state.rival_behind_pitted_at is None

    def test_alert_fires_when_gap_ahead_jumps(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        # 5 ticks at 5000 ms gap, then jump to 22000 ms (17 s jump)
        for i in range(5):
            eng.update({'gap_ahead': 5000, 'gap_behind': 0,
                        '_clock_s': float(i)}, {}, [])
        eng.update({'gap_ahead': 22000, 'gap_behind': 0,
                    '_clock_s': 5.0}, {}, [])
        assert eng.state.rival_ahead_pitted_at is not None
        assert abs(eng.state.rival_ahead_pitted_at - 5.0) < 0.1

    def test_small_jump_does_not_fire(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        for i in range(5):
            eng.update({'gap_ahead': 5000, 'gap_behind': 0,
                        '_clock_s': float(i)}, {}, [])
        # Jump of 8 s -- below 15 s threshold
        eng.update({'gap_ahead': 13000, 'gap_behind': 0,
                    '_clock_s': 5.0}, {}, [])
        assert eng.state.rival_ahead_pitted_at is None

    def test_alert_suppressed_for_60s_after_firing(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        for i in range(5):
            eng.update({'gap_ahead': 5000, 'gap_behind': 0,
                        '_clock_s': float(i)}, {}, [])
        # First jump
        eng.update({'gap_ahead': 22000, 'gap_behind': 0,
                    '_clock_s': 5.0}, {}, [])
        first_at = eng.state.rival_ahead_pitted_at
        # Another jump 30s later -- within suppression window
        eng.update({'gap_ahead': 40000, 'gap_behind': 0,
                    '_clock_s': 35.0}, {}, [])
        assert eng.state.rival_ahead_pitted_at == first_at  # unchanged
