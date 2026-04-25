# Strategy Tab v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Strategy tab with six live race-strategy cards driven by a shared `StrategyEngine`, plus a one-line strategy headline banner on the Race tab. Move existing fuel-save, undercut/overcut, and pit-strategy cards from Race → Strategy.

**Architecture:** Pure-logic `StrategyEngine` class in `s1napse/coaching/strategy_engine.py` produces a `StrategyState` dataclass on every processed sample. Two consumers: a new `StrategyTab` widget (six cards) and a one-line headline banner inserted at the top of the Race tab. Mirrors how `LapCoach` and `MathEngine` are organized today — pure logic in `coaching/`, UI in `widgets/`.

**Tech Stack:** Python 3, PyQt6, NumPy (already a transitive dep via `coaching/lap_coach.py`), matplotlib (for the small line charts in cards #1 and #5), pytest (new — first test infrastructure in the repo).

**Spec:** [docs/superpowers/specs/2026-04-25-strategy-tab-v1-design.md](../specs/2026-04-25-strategy-tab-v1-design.md)

**Note on testing:** This adds the first pytest module in the project. Engine logic is fully testable — UI is not (PyQt6 not in CI). Final verification step is a manual smoke test in ACC.

---

## File Structure

- **Create:** `s1napse/coaching/strategy_engine.py` — `StrategyEngine`, `StrategyState`, `Headline` dataclasses; ~250 lines.
- **Create:** `s1napse/widgets/strategy_tab.py` — `StrategyTab` widget with six cards; ~400 lines.
- **Create:** `tests/__init__.py` — empty.
- **Create:** `tests/test_strategy_engine.py` — pytest tests for the engine.
- **Create:** `pytest.ini` — minimal pytest config (rootdir + testpaths).
- **Create:** `requirements-dev.txt` — pytest dev dep (kept out of runtime `requirements.txt`).
- **Modify:** `s1napse/widgets/__init__.py` — export `StrategyTab`.
- **Modify:** `s1napse/app.py` — register Strategy tab, instantiate engine, wire `update()` into `_process_sample`, move three existing cards out of Race tab, add headline banner widget at top of Race tab.

The engine and widget are independent files — engine has no Qt dependency.

---

## Task 1: pytest scaffolding + project conventions

This is the first time this repo has had pytest. We set up the bare minimum so subsequent tasks can write failing tests against `strategy_engine.py` before it exists.

**Files:**
- Create: `pytest.ini`
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`

- [ ] **Step 1.1: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 1.2: Create `requirements-dev.txt`**

```
pytest>=8.0.0
```

- [ ] **Step 1.3: Create empty `tests/__init__.py`**

Just an empty file to make `tests/` an importable package.

- [ ] **Step 1.4: Install pytest locally**

Run from the repo root:
```bash
pip3 install -r requirements-dev.txt
```
Expected: pytest 8.x installs without error. If you don't have pip3 available, use whatever pip the repo's Python uses.

- [ ] **Step 1.5: Smoke-test the framework**

Run from the repo root:
```bash
python3 -m pytest --collect-only
```
Expected: `no tests ran` (empty `tests/` directory) and exit code 5 — that's correct for "no tests collected." If you get exit code 0 with "no tests ran," that's also fine. If you get any other error (like ImportError or "config file not found"), the scaffolding isn't right — check `pytest.ini` is at the repo root.

- [ ] **Step 1.6: Commit**

```bash
git add pytest.ini requirements-dev.txt tests/__init__.py
git commit -m "test: add pytest scaffolding"
```

---

## Task 2: `StrategyState` and `Headline` dataclasses (no logic yet)

The engine and the UI both need these two dataclasses. Defining them first means subsequent tests can import them.

**Files:**
- Create: `s1napse/coaching/strategy_engine.py`
- Create: `tests/test_strategy_engine.py`

- [ ] **Step 2.1: Write the failing test for `StrategyState` defaults**

Create `tests/test_strategy_engine.py` with:

```python
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
```

- [ ] **Step 2.2: Run the test to verify it fails**

```bash
python3 -m pytest tests/test_strategy_engine.py -v
```
Expected: ImportError / ModuleNotFoundError because `s1napse.coaching.strategy_engine` doesn't exist yet.

- [ ] **Step 2.3: Create `s1napse/coaching/strategy_engine.py` with the dataclasses**

```python
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
    available (e.g. degradation needs ≥3 laps before fitting).
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
          3. Fuel critical (≤ 2 laps left)
          4. Tyres approaching cliff (projected ≥ 1.5 s/lap loss within 2 laps)
          5. Default
        """
        return Headline()  # placeholder for now — Task 8 fills this in
```

- [ ] **Step 2.4: Run the test to verify it passes**

```bash
python3 -m pytest tests/test_strategy_engine.py -v
```
Expected: 4 passed.

- [ ] **Step 2.5: Commit**

```bash
git add s1napse/coaching/strategy_engine.py tests/test_strategy_engine.py
git commit -m "feat: StrategyState and Headline dataclasses"
```

---

## Task 3: `StrategyEngine` skeleton with `update()` no-op

The engine class itself, with a no-op `update()` that takes the same arguments the real implementation will. Wires up the contract before behavior.

**Files:**
- Modify: `s1napse/coaching/strategy_engine.py`
- Modify: `tests/test_strategy_engine.py`

- [ ] **Step 3.1: Write the failing test for engine instantiation and update signature**

Append to `tests/test_strategy_engine.py`:

```python
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
        # No assertions on state yet — just confirms the call doesn't raise.

    def test_state_property_returns_same_object(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        s1 = eng.state
        s2 = eng.state
        assert s1 is s2  # caller can read incrementally without copy
```

- [ ] **Step 3.2: Run the test to verify it fails**

```bash
python3 -m pytest tests/test_strategy_engine.py::TestStrategyEngineSkeleton -v
```
Expected: ImportError on `StrategyEngine`.

- [ ] **Step 3.3: Add the `StrategyEngine` class**

Append to `s1napse/coaching/strategy_engine.py`:

```python
class StrategyEngine:
    """Live race-strategy engine.

    Instantiate once per session. Call :meth:`update` for every processed
    raw telemetry sample. Read the latest snapshot via :attr:`state`.

    The engine never raises — missing inputs simply leave the relevant
    StrategyState fields as None.
    """

    def __init__(self):
        self._state = StrategyState()

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
        # No-op for now — subsequent tasks fill this in.
        return
```

- [ ] **Step 3.4: Run the test to verify it passes**

```bash
python3 -m pytest tests/test_strategy_engine.py -v
```
Expected: 7 passed (4 from Task 2 + 3 here).

- [ ] **Step 3.5: Commit**

```bash
git add s1napse/coaching/strategy_engine.py tests/test_strategy_engine.py
git commit -m "feat: StrategyEngine skeleton with no-op update"
```

---

## Task 4: Tyre-degradation projector logic

Linear regression over the trailing 3-5 lap times of the current stint. Reset on tyre stint reset (pit exit).

**Files:**
- Modify: `s1napse/coaching/strategy_engine.py`
- Modify: `tests/test_strategy_engine.py`

- [ ] **Step 4.1: Write the failing tests**

Append to `tests/test_strategy_engine.py`:

```python
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
        # First two are huge outliers — if the engine used them, slope would be very negative
        eng.update({}, {}, self._laps(
            [200.0, 200.0, 90.0, 90.1, 90.2, 90.3, 90.4]))
        # Slope should be ~0.1 (from the trailing 5: 90.0 to 90.4)
        assert abs(eng.state.deg_slope_s_per_lap - 0.1) < 0.05
```

- [ ] **Step 4.2: Run the tests to verify they fail**

```bash
python3 -m pytest tests/test_strategy_engine.py::TestDegradationProjector -v
```
Expected: 4 failed (state fields are still None).

- [ ] **Step 4.3: Add `numpy` import and fill in `_recompute_degradation`**

In `s1napse/coaching/strategy_engine.py`, change the imports to:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
```

Add a private method to `StrategyEngine` (paste right after `update`):

```python
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

        # R² for fit confidence
        y_pred = slope * x + intercept
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        s.deg_r_squared = (1.0 - ss_res / ss_tot) if ss_tot > 0 else 1.0

        # Projected end-of-stint pace: assume 5 more laps remaining (UI overrides this)
        s.deg_projected_end_pace_s = round(
            float(intercept + slope * (len(window) - 1 + 5)), 3)
```

Now wire it into `update()`. Replace the `return` in the `update()` body with:

```python
        self._recompute_degradation(session_laps)
```

- [ ] **Step 4.4: Run the tests to verify they pass**

```bash
python3 -m pytest tests/test_strategy_engine.py -v
```
Expected: 11 passed (7 prior + 4 new).

- [ ] **Step 4.5: Commit**

```bash
git add s1napse/coaching/strategy_engine.py tests/test_strategy_engine.py
git commit -m "feat: tyre-degradation linear regression in StrategyEngine"
```

---

## Task 5: Pit-window estimator logic

Open edge from fuel; close edge from projected tyre cliff (lap-time loss ≥ 1.5 s/lap above baseline).

**Files:**
- Modify: `s1napse/coaching/strategy_engine.py`
- Modify: `tests/test_strategy_engine.py`

- [ ] **Step 5.1: Write the failing tests**

Append to `tests/test_strategy_engine.py`:

```python
class TestPitWindow:
    def _laps(self, times):
        return [{'lap_number': i + 1, 'total_time_s': t,
                 'data': {'speed': [100]}}
                for i, t in enumerate(times)]

    def test_no_window_without_fuel_history(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        # No completed laps → no fuel/lap history
        eng.update({'fuel': 30.0}, {}, [])
        assert eng.state.pit_window_open_lap is None
        assert eng.state.pit_window_close_lap is None

    def test_window_open_when_fuel_runs_out_in_n_laps(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        # Three laps logged. Synthesize fuel state via repeated updates.
        # Lap 1: fuel = 90L start, 87L end → 3L/lap
        # Lap 2: fuel = 87L start, 84L end → 3L/lap
        # Lap 3: fuel = 84L start, 81L end → 3L/lap
        # Current fuel: 30L → ~10 laps left
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
```

- [ ] **Step 5.2: Run the tests to verify they fail**

```bash
python3 -m pytest tests/test_strategy_engine.py::TestPitWindow -v
```
Expected: 3 failed (window fields are still None).

- [ ] **Step 5.3: Add fuel-tracking attribute and pit-window logic**

In `StrategyEngine.__init__`, add the fuel-history attribute:

```python
    def __init__(self):
        self._state = StrategyState()
        self._fuel_per_lap_history: list[float] = []
        self._tyre_cliff_threshold_s = 1.5
```

Add the `_recompute_pit_window` method right after `_recompute_degradation`:

```python
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
```

Wire into `update()`:

```python
    def update(self, sample, current_lap_data, session_laps):
        # Track current lap count for window math
        self._state.current_lap_count = max(
            (lap.get('lap_number', 0) for lap in session_laps), default=0)
        self._recompute_degradation(session_laps)
        self._recompute_pit_window(sample)
```

- [ ] **Step 5.4: Run the tests to verify they pass**

```bash
python3 -m pytest tests/test_strategy_engine.py -v
```
Expected: 14 passed (11 prior + 3 new).

- [ ] **Step 5.5: Commit**

```bash
git add s1napse/coaching/strategy_engine.py tests/test_strategy_engine.py
git commit -m "feat: pit-window estimator (fuel-open + tyre-close)"
```

---

## Task 6: Rival-watch gap-jump detection

Detect when a rival pits via a sudden gap-ahead/gap-behind jump (≥ pit_loss × 0.7 = 15 s default) within one lap. 60 s suppression after firing.

**Files:**
- Modify: `s1napse/coaching/strategy_engine.py`
- Modify: `tests/test_strategy_engine.py`

- [ ] **Step 6.1: Write the failing tests**

Append to `tests/test_strategy_engine.py`:

```python
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
        # Jump of 8 s — below 15 s threshold
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
        # Another jump 30s later — within suppression window
        eng.update({'gap_ahead': 40000, 'gap_behind': 0,
                    '_clock_s': 35.0}, {}, [])
        assert eng.state.rival_ahead_pitted_at == first_at  # unchanged
```

- [ ] **Step 6.2: Run the tests to verify they fail**

```bash
python3 -m pytest tests/test_strategy_engine.py::TestRivalWatch -v
```
Expected: 3 failed (the second test passes vacuously since None == None — wait, actually all 4 fail because the alert never fires).

Run to confirm:
```bash
python3 -m pytest tests/test_strategy_engine.py::TestRivalWatch -v
```
Expected: at least the "alert fires" tests fail.

- [ ] **Step 6.3: Add gap-buffer attribute and rival-watch logic**

In `StrategyEngine.__init__`, add:

```python
        self._gap_ahead_buffer: list[tuple[float, int]] = []   # (clock_s, gap_ms)
        self._gap_behind_buffer: list[tuple[float, int]] = []
        self._pit_loss_s = 22.0       # default ACC pit loss
        self._jump_threshold_s = self._pit_loss_s * 0.7   # 15.4 s
        self._suppression_s = 60.0
```

Add the `_recompute_rival_watch` method:

```python
    def _recompute_rival_watch(self, sample: dict) -> None:
        """Detect rival pit by sudden gap jump (≥ pit_loss × 0.7 within 1 s)."""
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
```

Wire into `update()`:

```python
    def update(self, sample, current_lap_data, session_laps):
        self._state.current_lap_count = max(
            (lap.get('lap_number', 0) for lap in session_laps), default=0)
        self._recompute_degradation(session_laps)
        self._recompute_pit_window(sample)
        self._recompute_rival_watch(sample)
```

- [ ] **Step 6.4: Run the tests to verify they pass**

```bash
python3 -m pytest tests/test_strategy_engine.py -v
```
Expected: 18 passed (14 prior + 4 new).

- [ ] **Step 6.5: Commit**

```bash
git add s1napse/coaching/strategy_engine.py tests/test_strategy_engine.py
git commit -m "feat: rival-watch gap-jump detection with 60s suppression"
```

---

## Task 7: Weather/track-temp watch

Track `road_temp` and `air_temp`; record stint-start road temp on first call after a tyre stint reset.

**Files:**
- Modify: `s1napse/coaching/strategy_engine.py`
- Modify: `tests/test_strategy_engine.py`

- [ ] **Step 7.1: Write the failing tests**

Append to `tests/test_strategy_engine.py`:

```python
class TestTempWatch:
    def test_temp_recorded_on_first_sample(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        eng.update({'road_temp': 28.0, 'air_temp': 22.0}, {}, [])
        assert eng.state.track_temp_c == 28.0
        assert eng.state.air_temp_c == 22.0
        assert eng.state.track_temp_at_stint_start_c == 28.0

    def test_stint_start_temp_persists_across_updates(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        eng.update({'road_temp': 28.0, 'air_temp': 22.0}, {}, [])
        eng.update({'road_temp': 32.0, 'air_temp': 23.0}, {}, [])
        assert eng.state.track_temp_c == 32.0
        assert eng.state.track_temp_at_stint_start_c == 28.0

    def test_stint_start_temp_resets_on_pit_exit(self):
        from s1napse.coaching.strategy_engine import StrategyEngine
        eng = StrategyEngine()
        eng.update({'road_temp': 28.0, 'air_temp': 22.0}, {}, [])
        eng.update({'road_temp': 32.0, 'air_temp': 23.0}, {}, [])
        # Caller signals pit-exit by passing _pit_exit=True
        eng.update({'road_temp': 33.0, 'air_temp': 23.5,
                    '_pit_exit': True}, {}, [])
        assert eng.state.track_temp_at_stint_start_c == 33.0
```

- [ ] **Step 7.2: Run the tests to verify they fail**

```bash
python3 -m pytest tests/test_strategy_engine.py::TestTempWatch -v
```
Expected: 3 failed (temp fields are still None).

- [ ] **Step 7.3: Add temp-watch logic**

Add the `_recompute_temp_watch` method:

```python
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
```

Wire into `update()`:

```python
    def update(self, sample, current_lap_data, session_laps):
        self._state.current_lap_count = max(
            (lap.get('lap_number', 0) for lap in session_laps), default=0)
        self._recompute_degradation(session_laps)
        self._recompute_pit_window(sample)
        self._recompute_rival_watch(sample)
        self._recompute_temp_watch(sample)
```

- [ ] **Step 7.4: Run the tests to verify they pass**

```bash
python3 -m pytest tests/test_strategy_engine.py -v
```
Expected: 21 passed (18 prior + 3 new).

- [ ] **Step 7.5: Commit**

```bash
git add s1napse/coaching/strategy_engine.py tests/test_strategy_engine.py
git commit -m "feat: weather/track-temp watch with stint-start anchor"
```

---

## Task 8: Headline-priority logic

The `state.headline()` method that picks the highest-priority active state.

**Files:**
- Modify: `s1napse/coaching/strategy_engine.py`
- Modify: `tests/test_strategy_engine.py`

- [ ] **Step 8.1: Write the failing tests**

Append to `tests/test_strategy_engine.py`:

```python
class TestHeadlinePriority:
    def test_default_is_stable_neutral(self):
        from s1napse.coaching.strategy_engine import StrategyState
        h = StrategyState().headline()
        assert h.text == 'STRATEGY: STABLE'
        assert h.severity == 'neutral'

    def test_rival_pit_is_priority_1(self):
        from s1napse.coaching.strategy_engine import StrategyState
        s = StrategyState()
        s.rival_ahead_pitted_at = 100.0
        s.fuel_laps_left = 1.0   # would otherwise fire P3
        h = s.headline()
        assert 'UNDERCUT' in h.text or 'PITTED' in h.text
        assert h.severity == 'red'

    def test_pit_window_is_priority_2_when_no_rival(self):
        from s1napse.coaching.strategy_engine import StrategyState
        s = StrategyState()
        s.current_lap_count = 5
        s.pit_window_open_lap = 5    # window currently open
        s.pit_window_close_lap = 8
        h = s.headline()
        assert 'PIT WINDOW' in h.text
        assert h.severity == 'red'

    def test_fuel_critical_is_priority_3(self):
        from s1napse.coaching.strategy_engine import StrategyState
        s = StrategyState()
        s.fuel_laps_left = 1.5
        h = s.headline()
        assert 'FUEL' in h.text
        assert h.severity == 'red'

    def test_tyre_cliff_is_priority_4(self):
        from s1napse.coaching.strategy_engine import StrategyState
        s = StrategyState()
        s.deg_slope_s_per_lap = 0.8   # +0.8 s/lap → hits 1.5 in <2 laps
        h = s.headline()
        assert 'TYRE' in h.text or 'TYRES' in h.text
        assert h.severity == 'amber'
```

- [ ] **Step 8.2: Run the tests to verify they fail**

```bash
python3 -m pytest tests/test_strategy_engine.py::TestHeadlinePriority -v
```
Expected: 4 failed (the placeholder `headline()` always returns the default).

- [ ] **Step 8.3: Implement the priority logic**

Replace the placeholder `headline()` method on `StrategyState` with:

```python
    def headline(self) -> Headline:
        """Return the highest-priority active headline."""
        # P1: rival-pit alert (within last 30 s of detection — caller's clock)
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

        # P3: fuel critical (≤ 2 laps left)
        if self.fuel_laps_left is not None and self.fuel_laps_left <= 2.0:
            return Headline(
                f'FUEL: {self.fuel_laps_left:.1f} LAPS LEFT — SAVE NOW', 'red')

        # P4: tyre cliff approaching (projected ≥ 1.5 s/lap loss within 2 laps)
        if (self.deg_slope_s_per_lap is not None
                and self.deg_slope_s_per_lap > 0
                and (1.5 / self.deg_slope_s_per_lap) <= 2.0):
            laps_to_cliff = round(1.5 / self.deg_slope_s_per_lap, 1)
            return Headline(
                f'TYRES: {laps_to_cliff} LAPS TO 1.5s/LAP DROP', 'amber')

        # Default
        return Headline('STRATEGY: STABLE', 'neutral')
```

- [ ] **Step 8.4: Run the tests to verify they pass**

```bash
python3 -m pytest tests/test_strategy_engine.py -v
```
Expected: 26 passed (21 prior + 5 new).

- [ ] **Step 8.5: Commit**

```bash
git add s1napse/coaching/strategy_engine.py tests/test_strategy_engine.py
git commit -m "feat: headline-priority logic for Race-tab banner"
```

---

## Task 9: Wire `StrategyEngine` into `_process_sample` and surface `_clock_s` / `_pit_exit`

Engine logic is done. Now wire it into `TelemetryApp` so it actually receives samples, and surface the rival-watch and temp-watch synthetic fields.

**Files:**
- Modify: `s1napse/app.py`

- [ ] **Step 9.1: Add the import**

At the top of `s1napse/app.py`, in the existing coaching-imports block (around line 53-54), add:

```python
from .coaching.strategy_engine import StrategyEngine
```

- [ ] **Step 9.2: Instantiate the engine in `__init__`**

In `TelemetryApp.__init__`, find the line that creates the `LapCoach` (currently around line 162-163: `# Coaching engine` / `self._lap_coach = LapCoach()`). Right after that, add:

```python
        # Strategy engine (live race-strategy state)
        self._strategy_engine = StrategyEngine()
```

- [ ] **Step 9.3: Sync `_fuel_per_lap_history` into the engine on lap completion**

In `_process_sample`, find the existing block where fuel-per-lap is appended (around line 4347-4350: `self._fuel_per_lap_history.append(...)`). Right after that block (still inside `if lap_changed:`), add:

```python
            self._strategy_engine._fuel_per_lap_history = list(self._fuel_per_lap_history)
```

(This is a deliberate underscore-prefix poke — `_fuel_per_lap_history` is the engine's internal state but the engine doesn't track lap completion itself, so the host pushes its history in.)

- [ ] **Step 9.4: Call `engine.update()` at the end of `_process_sample`**

At the very end of `_process_sample` (after `self._last_data = data`, currently line ~4475), add:

```python
        # Strategy engine — last call so it sees the freshest state
        import time as _time
        sample_with_synth = dict(data)
        sample_with_synth['_clock_s'] = _time.monotonic()
        sample_with_synth['_pit_exit'] = (
            self._prev_is_in_pit_lane and not data.get('is_in_pit_lane', False))
        self._strategy_engine.update(
            sample_with_synth, self.current_lap_data, self.session_laps)
```

(Note: `_prev_is_in_pit_lane` was already updated earlier in this method, so by the time we read it the value reflects the *previous* state — which is what we want for pit-exit detection.)

Wait — re-reading the code: `_prev_is_in_pit_lane` IS updated earlier in `_process_sample` (line ~4340: `self._prev_is_in_pit_lane = cur_in_pit_lane`). So by the time the engine call runs, it's already been updated to the current value. We need to capture pit-exit before that update.

Replace the `_pit_exit` line with:

```python
        sample_with_synth['_pit_exit'] = False  # detected via separate path
```

And add proper pit-exit detection at the top of `_process_sample`. Find this existing block (around line 4337):

```python
        cur_in_pit_lane = data.get('is_in_pit_lane', False)
        if self._prev_is_in_pit_lane and not cur_in_pit_lane:
            self._current_lap_had_pit_exit = True
            self._tyre_stint_laps = 0
        self._prev_is_in_pit_lane = cur_in_pit_lane
```

Change it to:

```python
        cur_in_pit_lane = data.get('is_in_pit_lane', False)
        _pit_exit_this_tick = self._prev_is_in_pit_lane and not cur_in_pit_lane
        if _pit_exit_this_tick:
            self._current_lap_had_pit_exit = True
            self._tyre_stint_laps = 0
        self._prev_is_in_pit_lane = cur_in_pit_lane
```

Then at the bottom (where you added the engine call), use the captured local:

```python
        # Strategy engine — last call so it sees the freshest state
        import time as _time
        sample_with_synth = dict(data)
        sample_with_synth['_clock_s'] = _time.monotonic()
        sample_with_synth['_pit_exit'] = _pit_exit_this_tick
        self._strategy_engine.update(
            sample_with_synth, self.current_lap_data, self.session_laps)
```

- [ ] **Step 9.5: Verify the file still parses and the engine tests still pass**

```bash
python3 -c "import ast; ast.parse(open('s1napse/app.py').read()); print('OK')"
python3 -m pytest tests/test_strategy_engine.py -v
```
Expected: `OK` and 26 passed.

- [ ] **Step 9.6: Commit**

```bash
git add s1napse/app.py
git commit -m "feat: wire StrategyEngine into _process_sample"
```

---

## Task 10: `StrategyTab` widget skeleton with all six cards (placeholder content)

Build the new tab widget with six empty card frames so it can be registered and shown. Cards will get their content in subsequent tasks. UI styling matches the existing Race tab's card pattern.

**Files:**
- Create: `s1napse/widgets/strategy_tab.py`

- [ ] **Step 10.1: Create the file**

Create `s1napse/widgets/strategy_tab.py`:

```python
"""Strategy tab — six live cards driven by StrategyEngine.

See docs/superpowers/specs/2026-04-25-strategy-tab-v1-design.md.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
)

from ..constants import BG, BG2, BG3, BORDER, BORDER2, TXT, TXT2, mono, sans


def _card() -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f'background: {BG2}; border: 1px solid {BORDER}; border-radius: 6px;')
    return f


def _chip_lbl(text: str, font_size: int = 8, bold: bool = True,
              color: str = TXT2, letter_spacing: str = '1px') -> QLabel:
    l = QLabel(text)
    l.setFont(sans(font_size, bold=bold))
    l.setStyleSheet(f'color: {color}; letter-spacing: {letter_spacing};')
    return l


class StrategyTab(QWidget):
    """Strategy tab widget. Re-renders cards from a StrategyState snapshot.

    The tab is render-driven: call :meth:`refresh` from the host's render
    timer with the current StrategyState. The widget guards against
    redrawing when invisible (see :meth:`isVisible`).
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')

        inner = QWidget()
        inner.setStyleSheet(f'background: {BG};')
        body = QVBoxLayout(inner)
        body.setContentsMargins(14, 14, 14, 14)
        body.setSpacing(10)

        body.addWidget(self._build_degradation_card())
        body.addWidget(self._build_pit_window_card())
        body.addWidget(self._build_fuel_save_cost_card())
        body.addWidget(self._build_rival_watch_card())
        body.addWidget(self._build_temp_watch_card())
        body.addWidget(self._build_pit_summary_card())
        body.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    # --- Card builders (placeholders for now; filled in Tasks 11-13) ---

    def _build_degradation_card(self) -> QFrame:
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('TYRE DEGRADATION'))
        self._deg_status = QLabel('Need 3 laps to project.')
        self._deg_status.setFont(mono(10))
        self._deg_status.setStyleSheet(f'color: {TXT2};')
        v.addWidget(self._deg_status)
        return c

    def _build_pit_window_card(self) -> QFrame:
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('PIT WINDOW'))
        self._pw_status = QLabel('Complete a lap to estimate.')
        self._pw_status.setFont(mono(10))
        self._pw_status.setStyleSheet(f'color: {TXT2};')
        v.addWidget(self._pw_status)
        return c

    def _build_fuel_save_cost_card(self) -> QFrame:
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('FUEL-SAVE COST'))
        self._fsc_status = QLabel('—')
        self._fsc_status.setFont(mono(10))
        self._fsc_status.setStyleSheet(f'color: {TXT2};')
        v.addWidget(self._fsc_status)
        return c

    def _build_rival_watch_card(self) -> QFrame:
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('RIVAL WATCH (inferred)'))
        self._rw_ahead = QLabel('Ahead: stable')
        self._rw_behind = QLabel('Behind: stable')
        for lbl in (self._rw_ahead, self._rw_behind):
            lbl.setFont(mono(10))
            lbl.setStyleSheet(f'color: {TXT};')
            v.addWidget(lbl)
        sub = QLabel('Inferred from gap delta. May fire on rival crash/spin.')
        sub.setFont(sans(8))
        sub.setStyleSheet(f'color: {TXT2};')
        sub.setWordWrap(True)
        v.addWidget(sub)
        return c

    def _build_temp_watch_card(self) -> QFrame:
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('WEATHER / TRACK TEMP'))
        self._tw_status = QLabel('—')
        self._tw_status.setFont(mono(10))
        self._tw_status.setStyleSheet(f'color: {TXT2};')
        v.addWidget(self._tw_status)
        return c

    def _build_pit_summary_card(self) -> QFrame:
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('PIT STRATEGY (relocated)'))
        self._ps_status = QLabel('Pit-strategy summary will move here in Task 14.')
        self._ps_status.setFont(mono(10))
        self._ps_status.setStyleSheet(f'color: {TXT2};')
        v.addWidget(self._ps_status)
        return c

    # --- Public API ---

    def refresh(self, state) -> None:
        """Re-render all six cards from a StrategyState. Cheap if invisible."""
        if not self.isVisible():
            return
        # Card content is filled in Tasks 11-13. For now this is a no-op.
        return
```

- [ ] **Step 10.2: Verify the file parses**

```bash
python3 -c "import ast; ast.parse(open('s1napse/widgets/strategy_tab.py').read()); print('OK')"
```
Expected: `OK`.

- [ ] **Step 10.3: Commit**

```bash
git add s1napse/widgets/strategy_tab.py
git commit -m "feat: StrategyTab widget skeleton with six placeholder cards"
```

---

## Task 11: Fill in degradation, pit-window, and fuel-save cost cards

Connect the first three cards to their `StrategyState` fields.

**Files:**
- Modify: `s1napse/widgets/strategy_tab.py`

- [ ] **Step 11.1: Replace the `refresh()` body**

In `s1napse/widgets/strategy_tab.py`, replace the `refresh()` method with:

```python
    def refresh(self, state) -> None:
        """Re-render all six cards from a StrategyState. Cheap if invisible."""
        if not self.isVisible():
            return

        # Card 1 — degradation
        if state.deg_slope_s_per_lap is None:
            self._deg_status.setText('Need 3 laps to project.')
        else:
            r2 = state.deg_r_squared or 0.0
            pips = '●●●' if r2 >= 0.9 else ('●●○' if r2 >= 0.7 else '●○○')
            self._deg_status.setText(
                f'Baseline {state.deg_baseline_s:.3f}s   '
                f'Deg {state.deg_slope_s_per_lap:+.3f}s/lap   '
                f'EOS {state.deg_projected_end_pace_s:.3f}s   '
                f'Fit {pips}'
            )

        # Card 2 — pit window
        if (state.pit_window_open_lap is None
                and state.pit_window_close_lap is None):
            self._pw_status.setText('Complete a lap to estimate.')
        else:
            open_str = (str(state.pit_window_open_lap)
                        if state.pit_window_open_lap is not None else '—')
            close_str = (str(state.pit_window_close_lap)
                         if state.pit_window_close_lap is not None else '—')
            self._pw_status.setText(
                f'Window opens lap {open_str}   closes lap {close_str}   '
                f'(currently lap {state.current_lap_count})'
            )

        # Card 3 — fuel-save cost (estimate per L/lap saved)
        cost = state.fuel_save_cost_s_per_lap_per_l
        self._fsc_status.setText(
            f'Estimated cost: ~{cost:.2f}s/lap per 1 L/lap saved   '
            f'(industry rule of thumb; varies by car/track)'
        )
```

- [ ] **Step 11.2: Verify the file parses**

```bash
python3 -c "import ast; ast.parse(open('s1napse/widgets/strategy_tab.py').read()); print('OK')"
```
Expected: `OK`.

- [ ] **Step 11.3: Commit**

```bash
git add s1napse/widgets/strategy_tab.py
git commit -m "feat: wire degradation, pit-window, fuel-save cost cards"
```

---

## Task 12: Fill in rival-watch card

**Files:**
- Modify: `s1napse/widgets/strategy_tab.py`

- [ ] **Step 12.1: Append to `refresh()`**

In `s1napse/widgets/strategy_tab.py`, inside the `refresh()` method, after the Card 3 block, add:

```python
        # Card 4 — rival watch
        import time as _time
        now = _time.monotonic()

        def _rival_str(prefix: str, gap_ms: int, pitted_at: float | None) -> str:
            gap_s = abs(gap_ms) / 1000.0
            if pitted_at is not None and (now - pitted_at) <= 30.0:
                age = int(now - pitted_at)
                return f'{prefix}: PITTED LIKELY ({age}s ago, gap {gap_s:.1f}s)'
            return f'{prefix}: stable (gap {gap_s:.1f}s)'

        self._rw_ahead.setText(_rival_str(
            'Ahead', state.last_gap_ahead_ms, state.rival_ahead_pitted_at))
        self._rw_behind.setText(_rival_str(
            'Behind', state.last_gap_behind_ms, state.rival_behind_pitted_at))

        # Color the labels amber when pit alert is active
        for lbl, pitted_at in (
            (self._rw_ahead, state.rival_ahead_pitted_at),
            (self._rw_behind, state.rival_behind_pitted_at),
        ):
            if pitted_at is not None and (now - pitted_at) <= 30.0:
                lbl.setStyleSheet('color: #f5a623;')
            else:
                lbl.setStyleSheet(f'color: {TXT};')
```

- [ ] **Step 12.2: Verify the file parses**

```bash
python3 -c "import ast; ast.parse(open('s1napse/widgets/strategy_tab.py').read()); print('OK')"
```
Expected: `OK`.

- [ ] **Step 12.3: Commit**

```bash
git add s1napse/widgets/strategy_tab.py
git commit -m "feat: rival-watch card display with amber alert styling"
```

---

## Task 13: Fill in weather/track-temp watch card

**Files:**
- Modify: `s1napse/widgets/strategy_tab.py`

- [ ] **Step 13.1: Append to `refresh()`**

In `s1napse/widgets/strategy_tab.py`, inside `refresh()`, after the Card 4 block, add:

```python
        # Card 5 — weather/track-temp watch
        if state.track_temp_c is None:
            self._tw_status.setText('No track-temp data.')
        else:
            air_str = (f' (air {state.air_temp_c:.1f}°C)'
                       if state.air_temp_c is not None else '')
            if state.track_temp_at_stint_start_c is None:
                self._tw_status.setText(
                    f'Track {state.track_temp_c:.1f}°C{air_str}')
            else:
                delta = state.track_temp_c - state.track_temp_at_stint_start_c
                if abs(delta) <= 5.0:
                    note = 'stable'
                elif delta < 0:
                    note = f'cooling {abs(delta):.0f}°C — expect more tyre life'
                else:
                    note = f'heating {delta:.0f}°C — expect more degradation'
                self._tw_status.setText(
                    f'Track {state.track_temp_c:.1f}°C{air_str} · {note}'
                )
```

- [ ] **Step 13.2: Verify the file parses**

```bash
python3 -c "import ast; ast.parse(open('s1napse/widgets/strategy_tab.py').read()); print('OK')"
```
Expected: `OK`.

- [ ] **Step 13.3: Commit**

```bash
git add s1napse/widgets/strategy_tab.py
git commit -m "feat: weather/track-temp watch card display"
```

---

## Task 14: Move the existing Pit Strategy card from Race → Strategy tab (visual reuse)

The existing pit-strategy card (built inline in `_build_race_tab` at line ~3722) is a strategy concern. Move its rendered state into the StrategyTab widget. We re-use the existing `_pit_*` labels by relocating them into the new tab — Task 16 then deletes the cards from the Race tab.

**Files:**
- Modify: `s1napse/widgets/strategy_tab.py`
- Modify: `s1napse/app.py`

- [ ] **Step 14.1: Replace the `_build_pit_summary_card` placeholder**

In `s1napse/widgets/strategy_tab.py`, replace the `_build_pit_summary_card` method with:

```python
    def _build_pit_summary_card(self) -> QFrame:
        c = _card()
        vbox = QVBoxLayout(c)
        vbox.setContentsMargins(18, 12, 18, 12)
        vbox.setSpacing(8)

        hdr_row = QHBoxLayout()
        hdr_row.addWidget(_chip_lbl('PIT STRATEGY'))
        hdr_row.addStretch()
        self._pit_no_data_lbl = _chip_lbl('Complete a lap to calculate',
                                           color=TXT2, bold=False)
        hdr_row.addWidget(self._pit_no_data_lbl)
        vbox.addLayout(hdr_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(0)

        def _pit_stat(title: str, attr: str) -> QVBoxLayout:
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(_chip_lbl(title, font_size=7))
            v = QLabel('—')
            v.setFont(mono(11, bold=True))
            v.setStyleSheet(f'color: {TXT};')
            col.addWidget(v)
            setattr(self, attr, v)
            return col

        stats_row.addLayout(_pit_stat('FUEL LAPS LEFT', '_pit_fuel_laps_lbl'))
        stats_row.addSpacing(28)
        stats_row.addLayout(_pit_stat('TYRE STINT', '_pit_tyre_stint_lbl'))
        stats_row.addSpacing(28)
        stats_row.addLayout(_pit_stat('TYRE CONDITION', '_pit_tyre_cond_lbl'))
        stats_row.addStretch()
        vbox.addLayout(stats_row)

        # Recommendation text
        from ..widgets.graphs import _style_ax  # noqa: F401  — keeps style import side effect parity
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f'color: {BORDER2}; background: {BORDER2};')
        sep.setFixedHeight(1)
        vbox.addWidget(sep)

        self._pit_rec_lbl = QLabel('—')
        self._pit_rec_lbl.setFont(sans(11, bold=True))
        self._pit_rec_lbl.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        self._pit_rec_lbl.setWordWrap(True)
        vbox.addWidget(self._pit_rec_lbl)

        return c
```

- [ ] **Step 14.2: In `app.py`, update references from `self._pit_*` to `self.strategy_tab._pit_*`**

In `s1napse/app.py`, find every reference to:
- `self._pit_fuel_laps_lbl`
- `self._pit_tyre_stint_lbl`
- `self._pit_tyre_cond_lbl`
- `self._pit_no_data_lbl`
- `self._pit_rec_lbl`

Use grep to find them all:
```bash
grep -n "self._pit_fuel_laps_lbl\|self._pit_tyre_stint_lbl\|self._pit_tyre_cond_lbl\|self._pit_no_data_lbl\|self._pit_rec_lbl" s1napse/app.py
```

Some references are in `_build_race_tab` (these get deleted in Task 16 — leave them for now). Others are in `_update_race_tab` or similar update methods. Replace each non-`_build_race_tab` usage:
- `self._pit_fuel_laps_lbl` → `self.strategy_tab._pit_fuel_laps_lbl`
- ... and so on for each label.

(Reading the labels' values via the same names — the only difference is they now live on the `strategy_tab` attribute, which gets created in Task 15.)

- [ ] **Step 14.3: Verify the file parses**

```bash
python3 -c "import ast; ast.parse(open('s1napse/app.py').read()); print('OK')"
python3 -c "import ast; ast.parse(open('s1napse/widgets/strategy_tab.py').read()); print('OK')"
```
Expected: `OK` for both.

- [ ] **Step 14.4: Commit**

```bash
git add s1napse/app.py s1napse/widgets/strategy_tab.py
git commit -m "feat: move pit-strategy summary card to StrategyTab widget"
```

---

## Task 15: Register the StrategyTab in the main app

Add the tab to the QTabWidget, instantiate the widget, hook the render-tick refresh, export from widgets/__init__.

**Files:**
- Modify: `s1napse/widgets/__init__.py`
- Modify: `s1napse/app.py`

- [ ] **Step 15.1: Export from `widgets/__init__.py`**

In `s1napse/widgets/__init__.py`, add to the import block:

```python
from .strategy_tab import StrategyTab
```

And add `'StrategyTab'` to the `__all__` list.

- [ ] **Step 15.2: Import and instantiate in `app.py`**

In `s1napse/app.py`, in the existing widgets import (around line 40-49), add `StrategyTab` to the imported names:

```python
from .widgets import (
    RevBar, PedalBar, ValueDisplay, SteeringWidget, SteeringBar,
    TyreCard, _lerp_color, _TYRE_TEMP_KP, TrackMapWidget,
    ChannelGraph, MultiChannelGraph,
    AnalysisTelemetryGraph, AnalysisMultiLineGraph,
    TimeDeltaGraph, ComparisonGraph, ComparisonDeltaGraph,
    RacePaceChart, ReplayGraph, ReplayMultiGraph,
    SectorTimesPanel, SectorScrubWidget, LapHistoryPanel,
    AidBadge, StrategyTab,
)
```

- [ ] **Step 15.3: Register the tab and instantiate before tab construction**

In `_init_ui`, find the tab-registration block (line ~244-251). Right BEFORE the `self.tabs.addTab(self._build_dashboard_tab(), 'DASHBOARD')` line, add:

```python
        self.strategy_tab = StrategyTab()
```

(Instantiating it before tab construction means `self.strategy_tab._pit_*` labels exist by the time `_build_race_tab` references them — important after Task 16 removes the in-Race-tab construction. For now they coexist; Task 16 deletes the Race-tab versions.)

Then add a new `addTab` line right after the existing RACE addTab line:

```python
        self.tabs.addTab(self._build_race_tab(), 'RACE')
        self.tabs.addTab(self.strategy_tab, 'STRATEGY')
        self.tabs.addTab(self._build_tyres_tab(), 'TYRES')
```

- [ ] **Step 15.4: Refresh the tab from `_render_telemetry`**

In `_render_telemetry` (line ~4477), after the existing render-loop work but before the function returns, add:

```python
        # Strategy tab — re-render from latest engine snapshot
        try:
            self.strategy_tab.refresh(self._strategy_engine.state)
        except Exception:
            pass
```

(The bare `except` is intentional defensive code matching the existing `_render_telemetry` style — see how the math engine and other re-render hooks behave.)

- [ ] **Step 15.5: Verify the file parses**

```bash
python3 -c "import ast; ast.parse(open('s1napse/app.py').read()); print('OK')"
python3 -c "import ast; ast.parse(open('s1napse/widgets/__init__.py').read()); print('OK')"
```
Expected: `OK` for both.

- [ ] **Step 15.6: Commit**

```bash
git add s1napse/app.py s1napse/widgets/__init__.py
git commit -m "feat: register StrategyTab in main window and refresh per render tick"
```

---

## Task 16: Move existing fuel-save and undercut/overcut cards from Race tab → Strategy tab

The remaining two strategy cards relocate. The Race tab gets simpler.

**Files:**
- Modify: `s1napse/widgets/strategy_tab.py`
- Modify: `s1napse/app.py`

- [ ] **Step 16.1: Add fuel-save and undercut cards to the StrategyTab widget**

In `s1napse/widgets/strategy_tab.py`, add two new card-builder methods before the `# --- Public API ---` comment:

```python
    def _build_fuel_save_calculator_card(self) -> QFrame:
        from PyQt6.QtWidgets import QSpinBox
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.setSpacing(8)
        v.addWidget(_chip_lbl('FUEL SAVE CALCULATOR'))

        row = QHBoxLayout()
        row.addWidget(_chip_lbl('LAPS TO GO', font_size=8, bold=False, color=TXT))
        self._fs_laps_spin = QSpinBox()
        self._fs_laps_spin.setRange(1, 99)
        self._fs_laps_spin.setValue(10)
        self._fs_laps_spin.setStyleSheet(
            f'background: {BG3}; color: {TXT}; border: 1px solid {BORDER2};'
            f' border-radius: 4px; padding: 4px 8px;')
        row.addWidget(self._fs_laps_spin)
        row.addStretch()
        v.addLayout(row)

        self._fs_result_lbl = QLabel('—')
        self._fs_result_lbl.setFont(mono(10, bold=True))
        self._fs_result_lbl.setStyleSheet(f'color: {TXT2};')
        self._fs_result_lbl.setWordWrap(True)
        v.addWidget(self._fs_result_lbl)
        return c

    def _build_undercut_overcut_card(self) -> QFrame:
        from PyQt6.QtWidgets import QDoubleSpinBox
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.setSpacing(8)
        v.addWidget(_chip_lbl('UNDERCUT / OVERCUT'))

        inputs_row = QHBoxLayout()
        inputs_row.setSpacing(20)

        def _spin_col(label: str, attr: str, default: float, min_val: float,
                      max_val: float, step: float, decimals: int) -> QVBoxLayout:
            col = QVBoxLayout()
            col.addWidget(_chip_lbl(label, font_size=7))
            spin = QDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(default)
            spin.setSingleStep(step)
            spin.setDecimals(decimals)
            spin.setStyleSheet(
                f'background: {BG3}; color: {TXT}; border: 1px solid {BORDER2};'
                f' border-radius: 4px; padding: 4px 8px;')
            spin.setFixedWidth(90)
            col.addWidget(spin)
            setattr(self, attr, spin)
            return col

        inputs_row.addLayout(
            _spin_col('PIT LOSS (s)', '_uco_pit_loss_spin', 22.0, 10.0, 60.0, 0.5, 1))
        inputs_row.addLayout(
            _spin_col('PACE DELTA (s/lap)', '_uco_pace_delta_spin', 0.8, 0.0, 5.0, 0.1, 1))
        inputs_row.addStretch()
        v.addLayout(inputs_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f'color: {BORDER2}; background: {BORDER2};')
        sep.setFixedHeight(1)
        v.addWidget(sep)

        self._uco_undercut_lbl = QLabel('UNDERCUT: —')
        self._uco_undercut_lbl.setFont(mono(9, bold=True))
        self._uco_undercut_lbl.setStyleSheet(f'color: {TXT2};')
        self._uco_overcut_lbl = QLabel('OVERCUT: —')
        self._uco_overcut_lbl.setFont(mono(9, bold=True))
        self._uco_overcut_lbl.setStyleSheet(f'color: {TXT2};')
        v.addWidget(self._uco_undercut_lbl)
        v.addWidget(self._uco_overcut_lbl)
        return c
```

Then add these two cards into the `_build_ui` body section, between the pit-summary card and the stretch. Replace this block:

```python
        body.addWidget(self._build_pit_summary_card())
        body.addStretch()
```

with:

```python
        body.addWidget(self._build_pit_summary_card())
        body.addWidget(self._build_fuel_save_calculator_card())
        body.addWidget(self._build_undercut_overcut_card())
        body.addStretch()
```

- [ ] **Step 16.2: Delete the original cards from `_build_race_tab` in `app.py`**

In `s1napse/app.py`, find `_build_race_tab` (line ~3567). Delete these blocks:

1. **Pit Strategy card** (currently around line ~3722-3766): the block starting with `# ── Pit Strategy card ────` and ending with the `outer.addWidget(pit_card)` line.
2. **Fuel save card** (currently around line ~3786-3811): the block starting with `# ── Fuel save card ────` and ending with `outer.addWidget(fuel_save_card)`.
3. **Undercut / overcut card** (currently around line ~3813-3856): the block starting with `# ── Undercut / overcut card ────` and ending with `outer.addWidget(uco_card)`.

Use grep to locate the exact line ranges:
```bash
grep -n "Pit Strategy card\|Fuel save card\|Undercut / overcut card\|outer.addWidget(pit_card)\|outer.addWidget(fuel_save_card)\|outer.addWidget(uco_card)" s1napse/app.py
```

- [ ] **Step 16.3: Update references from `self._fs_*` and `self._uco_*` to `self.strategy_tab._fs_*` and `self.strategy_tab._uco_*`**

Find all references:
```bash
grep -n "self._fs_laps_spin\|self._fs_result_lbl\|self._uco_pit_loss_spin\|self._uco_pace_delta_spin\|self._uco_undercut_lbl\|self._uco_overcut_lbl" s1napse/app.py
```

Update each one to use the `strategy_tab.` prefix. Functions like `_update_fuel_save` and `_update_undercut` (currently at line ~3864 and ~3887) read these labels — update those to use `self.strategy_tab.<attr>`.

Also update the `valueChanged.connect()` wiring. The original code wired `self._fs_laps_spin.valueChanged.connect(self._update_fuel_save)` inside `_build_race_tab`. After moving, you need to re-wire from inside `_init_ui` (after `self.strategy_tab = StrategyTab()` from Task 15):

```python
        self.strategy_tab._fs_laps_spin.valueChanged.connect(self._update_fuel_save)
        self.strategy_tab._uco_pit_loss_spin.valueChanged.connect(self._update_undercut)
        self.strategy_tab._uco_pace_delta_spin.valueChanged.connect(self._update_undercut)
```

- [ ] **Step 16.4: Verify the file parses**

```bash
python3 -c "import ast; ast.parse(open('s1napse/app.py').read()); print('OK')"
python3 -c "import ast; ast.parse(open('s1napse/widgets/strategy_tab.py').read()); print('OK')"
```
Expected: `OK` for both.

- [ ] **Step 16.5: Commit**

```bash
git add s1napse/app.py s1napse/widgets/strategy_tab.py
git commit -m "feat: relocate fuel-save and undercut cards to StrategyTab"
```

---

## Task 17: Add the headline banner to the Race tab

A 40-px-tall label at the top of the Race tab that reads `StrategyState.headline()`. Color matches severity. Click switches to the Strategy tab.

**Files:**
- Modify: `s1napse/app.py`

- [ ] **Step 17.1: Add the banner widget to `_build_race_tab`**

In `s1napse/app.py`, in `_build_race_tab` (line ~3567), find the very first thing added to `outer` (currently the `outer.addWidget(banner_card)` for `_race_session_banner`). RIGHT BEFORE that line, add:

```python
        # Headline strategy banner — driven by StrategyState.headline()
        self._race_strategy_banner = QLabel('STRATEGY: STABLE')
        self._race_strategy_banner.setFont(sans(11, bold=True))
        self._race_strategy_banner.setStyleSheet(
            f'background: {BG2}; color: {TXT2}; '
            f'border: 1px solid {BORDER}; border-radius: 6px; '
            f'padding: 10px 18px; letter-spacing: 1px;')
        self._race_strategy_banner.setFixedHeight(40)
        self._race_strategy_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Click to jump to Strategy tab
        self._race_strategy_banner.mousePressEvent = (
            lambda e: self.tabs.setCurrentWidget(self.strategy_tab))
        outer.addWidget(self._race_strategy_banner)
```

- [ ] **Step 17.2: Update banner from the render tick**

In `_render_telemetry` (line ~4477), find the `try:` block you added in Task 15 step 15.4 (which calls `self.strategy_tab.refresh(...)`). Right after that block, add:

```python
        # Race-tab headline banner
        try:
            h = self._strategy_engine.state.headline()
            self._race_strategy_banner.setText(h.text)
            color_map = {
                'red':     '#d04444',
                'amber':   '#f5a623',
                'neutral': TXT2,
            }
            border_map = {
                'red':     '#a03030',
                'amber':   '#a07020',
                'neutral': BORDER,
            }
            col = color_map.get(h.severity, TXT2)
            border = border_map.get(h.severity, BORDER)
            self._race_strategy_banner.setStyleSheet(
                f'background: {BG2}; color: {col}; '
                f'border: 1px solid {border}; border-radius: 6px; '
                f'padding: 10px 18px; letter-spacing: 1px;')
        except Exception:
            pass
```

- [ ] **Step 17.3: Verify the file parses**

```bash
python3 -c "import ast; ast.parse(open('s1napse/app.py').read()); print('OK')"
```
Expected: `OK`.

- [ ] **Step 17.4: Commit**

```bash
git add s1napse/app.py
git commit -m "feat: Race-tab headline strategy banner"
```

---

## Task 18: Final structural verification + manual smoke test prep

Run the full test suite, syntax-check both new files, and make sure no orphan references remain.

**Files:** none modified — verification only.

- [ ] **Step 18.1: Run the full pytest suite**

```bash
python3 -m pytest tests/ -v
```
Expected: 26 passed, 0 failed.

- [ ] **Step 18.2: AST-check both new files and modified app.py**

```bash
python3 -c "import ast; ast.parse(open('s1napse/coaching/strategy_engine.py').read()); print('engine OK')"
python3 -c "import ast; ast.parse(open('s1napse/widgets/strategy_tab.py').read()); print('tab OK')"
python3 -c "import ast; ast.parse(open('s1napse/app.py').read()); print('app OK')"
```
Expected: three `OK` lines.

- [ ] **Step 18.3: Check no leftover references to the old Race-tab card attribute names that should now be `strategy_tab.*`**

```bash
grep -nE "self\._fs_(laps_spin|result_lbl)\b" s1napse/app.py | grep -v "strategy_tab\." || echo "fs OK"
grep -nE "self\._uco_(pit_loss_spin|pace_delta_spin|undercut_lbl|overcut_lbl)\b" s1napse/app.py | grep -v "strategy_tab\." || echo "uco OK"
grep -nE "self\._pit_(fuel_laps_lbl|tyre_stint_lbl|tyre_cond_lbl|no_data_lbl|rec_lbl)\b" s1napse/app.py | grep -v "strategy_tab\." || echo "pit OK"
```
Expected: each prints either nothing matching followed by the OK message, OR shows lines that are inside the deleted card-construction blocks (those have been deleted by Task 16). If any non-construction reference is missing the `strategy_tab.` prefix, fix it.

- [ ] **Step 18.4: Manual smoke test in ACC (user-driven)**

This step is **manual** and must be run by the user with ACC live. The agent cannot perform it.

1. Launch the app: `python -m s1napse`.
2. Confirm a new STRATEGY tab appears between RACE and TYRES.
3. Start ACC, get on track, complete a single lap, then confirm:
   - Strategy tab opens; six cards render without errors.
   - "TYRE DEGRADATION" card shows "Need 3 laps to project."
   - "PIT WINDOW" card shows the open-edge after lap 1 (fuel-driven).
   - "FUEL-SAVE COST" card shows the constant cost line.
   - "RIVAL WATCH (inferred)" card shows current gaps; both rows say "stable" before any rival pit event.
   - "WEATHER / TRACK TEMP" card shows current track temp.
   - "PIT STRATEGY" card shows the same numbers as before the move.
   - Race tab now has a headline banner at the top reading "STRATEGY: STABLE" (or the relevant active call).
   - Clicking the headline banner switches to the Strategy tab.
4. Run a 5+ lap stint and confirm the degradation card populates with baseline / slope / EOS / fit indicator.
5. If a rival pits during the session (or you pit and observe from a replay), confirm the "PITTED LIKELY" alert fires on the appropriate row (ahead/behind).

If anything fails, open the corresponding task and fix it.
