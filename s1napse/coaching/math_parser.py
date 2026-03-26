"""Safe AST-based formula parser and evaluator.

Uses Python's ``ast`` module to parse formulas into an AST, validates
every node against a strict whitelist, and walks the tree to evaluate.
**No eval/exec/compile is used.**
"""

from __future__ import annotations

import ast
import math
from typing import Any

from .math_functions import (
    FUNCTION_REGISTRY, STATEFUL_FUNCTIONS, ALL_FUNCTION_NAMES, CONSTANTS,
)

# ---------------------------------------------------------------------------
# Allowed AST node types
# ---------------------------------------------------------------------------
ALLOWED_NODES = {
    ast.Expression,
    ast.BinOp, ast.UnaryOp, ast.Compare, ast.BoolOp, ast.IfExp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv,
    ast.USub, ast.UAdd, ast.Not,
    ast.Gt, ast.Lt, ast.GtE, ast.LtE, ast.Eq, ast.NotEq,
    ast.And, ast.Or,
    ast.Call, ast.Name, ast.Constant,
    ast.Load,
}


class FormulaError(Exception):
    """Raised when a formula cannot be parsed or validated."""


# ---------------------------------------------------------------------------
# Parse & validate
# ---------------------------------------------------------------------------

def parse_formula(formula: str) -> ast.Expression:
    """Parse *formula* into a safe ``ast.Expression`` tree.

    Raises :class:`FormulaError` on syntax errors or disallowed nodes.
    """
    formula = formula.strip()
    if not formula:
        raise FormulaError("Formula cannot be empty")

    # Strip newlines for multi-line support
    formula = ' '.join(formula.splitlines())

    try:
        tree = ast.parse(formula, mode='eval')
    except SyntaxError as e:
        raise FormulaError(f"Syntax error: {e.msg}") from None

    _validate_nodes(tree)
    return tree


def _validate_nodes(node: ast.AST) -> None:
    """Walk the AST and reject any node not in the whitelist."""
    if type(node) not in ALLOWED_NODES:
        raise FormulaError(
            f"Disallowed syntax: {type(node).__name__}. "
            f"Only arithmetic, comparisons, function calls, and conditionals are allowed."
        )
    for child in ast.iter_child_nodes(node):
        _validate_nodes(child)


def extract_dependencies(
    tree: ast.Expression,
    known_channels: set[str],
) -> list[str]:
    """Return channel names referenced in the formula.

    Names that match constants or function names are excluded.
    Raises :class:`FormulaError` for unrecognised names.
    """
    deps: list[str] = []
    _walk_deps(tree, known_channels, deps)
    return list(dict.fromkeys(deps))  # unique, preserve order


def _walk_deps(node: ast.AST, known: set[str], deps: list[str]) -> None:
    if isinstance(node, ast.Name):
        name = node.id
        if name in CONSTANTS or name == 'dt':
            return
        if name in ALL_FUNCTION_NAMES:
            return
        if name not in known:
            _raise_unknown(name, known)
        if name not in deps:
            deps.append(name)
        return

    # For stateful function calls, the first arg is a channel name (ast.Name)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn_name = node.func.id
        if fn_name in STATEFUL_FUNCTIONS and node.args:
            first = node.args[0]
            if isinstance(first, ast.Name):
                name = first.id
                if name not in known:
                    _raise_unknown(name, known)
                if name not in deps:
                    deps.append(name)
            # Process remaining args (skip first since we handled it)
            for arg in node.args[1:]:
                _walk_deps(arg, known, deps)
            return

    for child in ast.iter_child_nodes(node):
        _walk_deps(child, known, deps)


def _raise_unknown(name: str, known: set[str]) -> None:
    suggestion = _closest_match(name, known)
    msg = f"Unknown channel: '{name}'."
    if suggestion:
        msg += f" Did you mean '{suggestion}'?"
    else:
        msg += f" Available: {', '.join(sorted(known)[:20])}"
    raise FormulaError(msg)


def _closest_match(name: str, candidates: set[str]) -> str | None:
    """Return the closest match within Levenshtein distance 2."""
    best, best_d = None, 3
    for c in candidates:
        d = _levenshtein(name, c)
        if d < best_d:
            best, best_d = c, d
    return best


def _levenshtein(s: str, t: str) -> int:
    if len(s) < len(t):
        return _levenshtein(t, s)
    if not t:
        return len(s)
    prev = list(range(len(t) + 1))
    for i, sc in enumerate(s):
        curr = [i + 1]
        for j, tc in enumerate(t):
            curr.append(min(
                prev[j + 1] + 1,
                curr[j] + 1,
                prev[j] + (0 if sc == tc else 1),
            ))
        prev = curr
    return prev[-1]


# ---------------------------------------------------------------------------
# Safe evaluator
# ---------------------------------------------------------------------------

class FormulaEvaluator:
    """Walks a pre-validated AST and computes a float result.

    Parameters
    ----------
    context : dict[str, float]
        Channel name → current value mapping (raw + math channels).
    dt : float
        Time delta since previous tick (seconds).
    history : dict
        Channel name → ChannelHistory instance.
    lap_cache : object
        LapBoundaryCache with lap_avg_values etc.
    """

    def __init__(self, context: dict[str, float], dt: float,
                 history: dict, lap_cache):
        self.ctx = context
        self.dt = dt
        self.history = history
        self.lap_cache = lap_cache

    def evaluate(self, tree: ast.Expression) -> float:
        try:
            result = self._eval(tree.body)
            return self._sanitise(result)
        except Exception:
            return 0.0

    def _eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return float(node.value)

        if isinstance(node, ast.Name):
            name = node.id
            if name in CONSTANTS:
                return CONSTANTS[name]
            if name == 'dt':
                return self.dt
            return self.ctx.get(name, 0.0)

        if isinstance(node, ast.UnaryOp):
            operand = self._eval(node.operand)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.Not):
                return float(not operand)

        if isinstance(node, ast.BinOp):
            left = self._eval(node.left)
            right = self._eval(node.right)
            return self._binop(node.op, left, right)

        if isinstance(node, ast.Compare):
            left = self._eval(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = self._eval(comp)
                if not self._cmpop(op, left, right):
                    return 0.0
                left = right
            return 1.0

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for v in node.values:
                    if not self._eval(v):
                        return 0.0
                return 1.0
            else:  # Or
                for v in node.values:
                    if self._eval(v):
                        return 1.0
                return 0.0

        if isinstance(node, ast.IfExp):
            cond = self._eval(node.test)
            return self._eval(node.body) if cond else self._eval(node.orelse)

        if isinstance(node, ast.Call):
            return self._eval_call(node)

        return 0.0

    def _eval_call(self, node: ast.Call) -> float:
        if not isinstance(node.func, ast.Name):
            return 0.0
        fn_name = node.func.id

        # ── Stateful functions (first arg is channel name) ───────────
        if fn_name in STATEFUL_FUNCTIONS:
            return self._eval_stateful(fn_name, node.args)

        # ── Regular functions ────────────────────────────────────────
        entry = FUNCTION_REGISTRY.get(fn_name)
        if entry is None:
            return 0.0
        func, min_a, max_a = entry
        args = [self._eval(a) for a in node.args]

        if len(args) < min_a:
            return 0.0
        if max_a is not None and len(args) > max_a:
            args = args[:max_a]

        try:
            return float(func(*args))
        except Exception:
            return 0.0

    def _eval_stateful(self, fn_name: str, args: list) -> float:
        if not args or not isinstance(args[0], ast.Name):
            return 0.0
        ch_name = args[0].id
        hist = self.history.get(ch_name)

        if fn_name == 'prev':
            n = int(self._eval(args[1])) if len(args) > 1 else 1
            return hist.prev(n) if hist else 0.0

        if fn_name == 'delta':
            cur = self.ctx.get(ch_name, 0.0)
            prev_val = hist.prev(1) if hist else 0.0
            return cur - prev_val

        if fn_name == 'rate':
            cur = self.ctx.get(ch_name, 0.0)
            prev_val = hist.prev(1) if hist else 0.0
            return (cur - prev_val) / self.dt if self.dt > 0 else 0.0

        if fn_name == 'rolling_avg':
            n = int(self._eval(args[1])) if len(args) > 1 else 20
            return hist.rolling_avg(n) if hist else 0.0

        if fn_name == 'rolling_max':
            n = int(self._eval(args[1])) if len(args) > 1 else 20
            return hist.rolling_max(n) if hist else 0.0

        if fn_name == 'rolling_min':
            n = int(self._eval(args[1])) if len(args) > 1 else 20
            return hist.rolling_min(n) if hist else 0.0

        # Lap-boundary functions
        lc = self.lap_cache
        if fn_name == 'lap_avg':
            return lc.lap_avg_values.get(ch_name, 0.0) if lc else 0.0
        if fn_name == 'lap_max':
            return lc.lap_max_values.get(ch_name, 0.0) if lc else 0.0
        if fn_name == 'lap_min':
            return lc.lap_min_values.get(ch_name, 0.0) if lc else 0.0
        if fn_name == 'lap_start':
            return lc.lap_start_values.get(ch_name, 0.0) if lc else 0.0

        return 0.0

    # ── Binary operators ──────────────────────────────────────────────

    @staticmethod
    def _binop(op, left, right):
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            return left / right if right != 0 else 0.0
        if isinstance(op, ast.Pow):
            try:
                return left ** right
            except Exception:
                return 0.0
        if isinstance(op, ast.Mod):
            return left % right if right != 0 else 0.0
        if isinstance(op, ast.FloorDiv):
            return left // right if right != 0 else 0.0
        return 0.0

    @staticmethod
    def _cmpop(op, left, right):
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.GtE):
            return left >= right
        if isinstance(op, ast.LtE):
            return left <= right
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        return False

    @staticmethod
    def _sanitise(val) -> float:
        try:
            val = float(val)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(val):
            return 0.0
        if math.isinf(val):
            return 1e9 if val > 0 else -1e9
        return val
