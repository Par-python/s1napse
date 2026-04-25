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
