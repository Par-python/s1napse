"""Math channel engine — manages channels, history, topo sort, tick eval."""

from __future__ import annotations

import collections
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .math_parser import (
    parse_formula, extract_dependencies, FormulaError, FormulaEvaluator,
)
from .math_functions import ALL_FUNCTION_NAMES, CONSTANTS


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MathChannel:
    name: str
    formula: str
    unit: str = ""
    color: str = "#FFFFFF"
    visible: bool = True
    built_in: bool = False
    description: str = ""
    compiled_ast: Optional[object] = field(default=None, repr=False)
    dependencies: list[str] = field(default_factory=list)


class ChannelHistory:
    """Ring buffer storing the last N samples for a channel."""

    def __init__(self, max_size: int = 500):
        self.buffer: collections.deque[float] = collections.deque(maxlen=max_size)

    def push(self, value: float) -> None:
        self.buffer.append(value)

    def prev(self, n: int = 1) -> float:
        if len(self.buffer) > n:
            return self.buffer[-(n + 1)]
        return 0.0

    def rolling_avg(self, n: int) -> float:
        samples = list(self.buffer)[-n:]
        return sum(samples) / len(samples) if samples else 0.0

    def rolling_max(self, n: int) -> float:
        samples = list(self.buffer)[-n:]
        return max(samples) if samples else 0.0

    def rolling_min(self, n: int) -> float:
        samples = list(self.buffer)[-n:]
        return min(samples) if samples else 0.0


class LapBoundaryCache:
    """Updated at each lap completion."""

    def __init__(self):
        self.lap_avg_values: dict[str, float] = {}
        self.lap_max_values: dict[str, float] = {}
        self.lap_min_values: dict[str, float] = {}
        self.lap_start_values: dict[str, float] = {}
        self._accumulators: dict[str, list[float]] = {}

    def accumulate(self, name: str, value: float) -> None:
        self._accumulators.setdefault(name, []).append(value)

    def finalize_lap(self) -> None:
        """Called on lap complete — compute avg/max/min from accumulators."""
        for name, samples in self._accumulators.items():
            if samples:
                self.lap_avg_values[name] = sum(samples) / len(samples)
                self.lap_max_values[name] = max(samples)
                self.lap_min_values[name] = min(samples)
        self._accumulators.clear()

    def snapshot_start(self, values: dict[str, float]) -> None:
        """Called on lap start — record current values."""
        self.lap_start_values = dict(values)
        self._accumulators.clear()


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_TICK_BUDGET_S = 0.005  # 5ms


class MathEngine:
    """Core engine.  Parses, validates, and evaluates math channel formulas."""

    def __init__(self):
        self.channels: dict[str, MathChannel] = {}
        self.evaluation_order: list[str] = []
        self.history: dict[str, ChannelHistory] = {}
        self.lap_cache = LapBoundaryCache()
        self._last_dt: float = 0.05
        self._last_tick_time: float = 0.0
        self._raw_channel_names: set[str] = set()
        self._last_eval_ms: float = 0.0
        self._last_values: dict[str, float] = {}

    @property
    def last_eval_ms(self) -> float:
        return self._last_eval_ms

    # ------------------------------------------------------------------
    # Channel management
    # ------------------------------------------------------------------

    def set_raw_channels(self, names: set[str]) -> None:
        """Register the set of raw telemetry channel names."""
        self._raw_channel_names = set(names)

    def add_channel(self, name: str, formula: str, unit: str = "",
                    color: str = "#FFFFFF", built_in: bool = False,
                    description: str = "", visible: bool = True,
                    ) -> tuple[bool, str]:
        """Parse, validate, and register a new math channel."""
        err = self._validate_name(name)
        if err:
            return False, err

        ok, msg, deps, tree = self._parse_and_validate(formula, exclude=name)
        if not ok:
            return False, msg

        ch = MathChannel(
            name=name, formula=formula, unit=unit, color=color,
            visible=visible, built_in=built_in, description=description,
            compiled_ast=tree, dependencies=deps,
        )
        self.channels[name] = ch
        self.history.setdefault(name, ChannelHistory())
        self._rebuild_order()
        return True, ""

    def edit_channel(self, name: str, new_formula: str | None = None,
                     new_unit: str | None = None, new_color: str | None = None,
                     new_visible: bool | None = None) -> tuple[bool, str]:
        ch = self.channels.get(name)
        if ch is None:
            return False, f"Channel '{name}' does not exist"
        if ch.built_in and new_formula is not None:
            return False, "Cannot edit built-in channel formula"

        if new_formula is not None:
            ok, msg, deps, tree = self._parse_and_validate(new_formula, exclude=name)
            if not ok:
                return False, msg
            ch.formula = new_formula
            ch.compiled_ast = tree
            ch.dependencies = deps
            self._rebuild_order()
        if new_unit is not None:
            ch.unit = new_unit
        if new_color is not None:
            ch.color = new_color
        if new_visible is not None:
            ch.visible = new_visible
        return True, ""

    def remove_channel(self, name: str) -> tuple[bool, str]:
        ch = self.channels.get(name)
        if ch is None:
            return False, f"Channel '{name}' does not exist"
        if ch.built_in:
            return False, "Cannot delete built-in channel"
        # Check dependents
        dependents = [c.name for c in self.channels.values()
                      if name in c.dependencies and c.name != name]
        if dependents:
            return False, (
                f"Cannot delete '{name}' — used by: {', '.join(dependents)}")
        del self.channels[name]
        self.history.pop(name, None)
        self._rebuild_order()
        return True, ""

    def validate_formula(self, formula: str,
                         exclude_name: str | None = None,
                         ) -> tuple[bool, str, list[str]]:
        ok, msg, deps, _ = self._parse_and_validate(formula, exclude=exclude_name)
        return ok, msg, deps

    # ------------------------------------------------------------------
    # Evaluation (called every telemetry tick)
    # ------------------------------------------------------------------

    def evaluate(self, raw_channels: dict[str, float],
                 timestamp: float) -> dict[str, float]:
        """Evaluate all math channels given current raw telemetry values."""
        t0 = time.perf_counter()

        # dt
        if self._last_tick_time > 0:
            self._last_dt = max(0.001, timestamp - self._last_tick_time)
        self._last_tick_time = timestamp

        # Push raw values into history + accumulator
        for name, val in raw_channels.items():
            self.history.setdefault(name, ChannelHistory()).push(val)
            self.lap_cache.accumulate(name, val)

        # Update known raw channel names
        self._raw_channel_names.update(raw_channels.keys())

        # Build context: raw + previously computed math channels
        ctx: dict[str, float] = dict(raw_channels)
        results: dict[str, float] = {}

        evaluator = FormulaEvaluator(
            ctx, self._last_dt, self.history, self.lap_cache)

        for ch_name in self.evaluation_order:
            ch = self.channels.get(ch_name)
            if ch is None or ch.compiled_ast is None:
                continue

            # Time budget check
            elapsed = time.perf_counter() - t0
            if elapsed > _TICK_BUDGET_S:
                break

            val = evaluator.evaluate(ch.compiled_ast)
            ctx[ch_name] = val
            results[ch_name] = val
            self.history.setdefault(ch_name, ChannelHistory()).push(val)
            self.lap_cache.accumulate(ch_name, val)

        self._last_eval_ms = (time.perf_counter() - t0) * 1000.0
        self._last_values = results
        return results

    # ------------------------------------------------------------------
    # Lap boundary events
    # ------------------------------------------------------------------

    def on_lap_complete(self) -> None:
        self.lap_cache.finalize_lap()

    def on_lap_start(self, raw_channels: dict[str, float]) -> None:
        all_vals = dict(raw_channels)
        all_vals.update(self._last_values)
        self.lap_cache.snapshot_start(all_vals)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_to_json(self, filepath: str) -> None:
        user_channels = [
            {
                'name': ch.name, 'formula': ch.formula, 'unit': ch.unit,
                'color': ch.color, 'visible': ch.visible,
                'description': ch.description,
            }
            for ch in self.channels.values() if not ch.built_in
        ]
        data = {'version': 1, 'channels': user_channels}
        # Atomic write: tmp then rename
        tmp = filepath + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
        Path(tmp).replace(filepath)

    def load_from_json(self, filepath: str) -> None:
        try:
            with open(filepath) as f:
                data = json.load(f)
        except Exception:
            return
        for entry in data.get('channels', []):
            self.add_channel(
                name=entry['name'],
                formula=entry['formula'],
                unit=entry.get('unit', ''),
                color=entry.get('color', '#FFFFFF'),
                visible=entry.get('visible', True),
                description=entry.get('description', ''),
            )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_all_channels(self) -> list[MathChannel]:
        ordered = []
        for name in self.evaluation_order:
            if name in self.channels:
                ordered.append(self.channels[name])
        # Append any not in order (shouldn't happen)
        for ch in self.channels.values():
            if ch not in ordered:
                ordered.append(ch)
        return ordered

    def get_available_names(self) -> list[str]:
        names = set(self._raw_channel_names)
        names.update(self.channels.keys())
        names.update(CONSTANTS.keys())
        names.add('dt')
        return sorted(names)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate_name(self, name: str) -> str:
        """Return error message or empty string if valid."""
        if not name:
            return "Name cannot be empty"
        if not all(c.isalnum() or c == '_' for c in name):
            return "Name must be snake_case (lowercase, digits, underscores)"
        if name != name.lower():
            return "Name must be lowercase"
        if len(name) > 40:
            return "Name must be 40 characters or fewer"
        if name in self._raw_channel_names:
            return f"'{name}' conflicts with a raw telemetry channel"
        if name in ALL_FUNCTION_NAMES:
            return f"'{name}' conflicts with a built-in function"
        if name in CONSTANTS or name == 'dt':
            return f"'{name}' conflicts with a constant"
        if name in self.channels:
            return f"'{name}' already exists"
        return ""

    def _known_channels(self, exclude: str | None = None) -> set[str]:
        names = set(self._raw_channel_names)
        names.update(self.channels.keys())
        if exclude and exclude in names:
            names.discard(exclude)
        return names

    def _parse_and_validate(
        self, formula: str, exclude: str | None = None,
    ) -> tuple[bool, str, list[str], object | None]:
        """Returns (ok, error, deps, compiled_ast)."""
        try:
            tree = parse_formula(formula)
        except FormulaError as e:
            return False, str(e), [], None

        known = self._known_channels(exclude)
        try:
            deps = extract_dependencies(tree, known)
        except FormulaError as e:
            return False, str(e), [], None

        # Circular dependency check
        if exclude:
            # Temporarily add the channel being edited
            temp_deps = {exclude: deps}
            for name, ch in self.channels.items():
                if name != exclude:
                    temp_deps[name] = ch.dependencies
            cycle = _find_cycle(temp_deps, exclude)
            if cycle:
                return False, f"Circular dependency: {' -> '.join(cycle)}", [], None

        return True, "", deps, tree

    def _rebuild_order(self) -> None:
        """Recompute topological evaluation order."""
        graph: dict[str, list[str]] = {}
        for name, ch in self.channels.items():
            # Only depend on other math channels (not raw)
            graph[name] = [
                d for d in ch.dependencies if d in self.channels
            ]
        self.evaluation_order = _topological_sort(graph)


# ---------------------------------------------------------------------------
# Graph algorithms
# ---------------------------------------------------------------------------

def _topological_sort(graph: dict[str, list[str]]) -> list[str]:
    """Kahn's algorithm. Returns nodes in dependency order."""
    in_degree: dict[str, int] = {n: 0 for n in graph}
    for deps in graph.values():
        for d in deps:
            if d in in_degree:
                in_degree[d] += 1

    queue = collections.deque(n for n, d in in_degree.items() if d == 0)
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for dep in graph.get(node, []):
            if dep in in_degree:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

    # If not all nodes visited, there's a cycle — return what we have
    remaining = [n for n in graph if n not in order]
    order.extend(remaining)
    return order


def _find_cycle(deps: dict[str, list[str]], start: str) -> list[str] | None:
    """DFS cycle detection starting from *start*."""
    visited: set[str] = set()
    path: list[str] = []

    def dfs(node: str) -> list[str] | None:
        if node in visited:
            if node in path:
                idx = path.index(node)
                return path[idx:] + [node]
            return None
        visited.add(node)
        path.append(node)
        for dep in deps.get(node, []):
            if dep in deps:  # only check math channels
                cycle = dfs(dep)
                if cycle:
                    return cycle
        path.pop()
        return None

    return dfs(start)
