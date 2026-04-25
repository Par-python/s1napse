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
