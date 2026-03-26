"""Built-in function implementations for the math channel engine.

All functions are plain Python callables.  The FUNCTION_REGISTRY maps
names to (callable, min_args, max_args) tuples.
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Core math functions
# ---------------------------------------------------------------------------

def fn_abs(x: float) -> float:
    return abs(x)


def fn_min(a: float, b: float) -> float:
    return min(a, b)


def fn_max(a: float, b: float) -> float:
    return max(a, b)


def fn_sqrt(x: float) -> float:
    return math.sqrt(x) if x >= 0 else 0.0


def fn_avg(*args: float) -> float:
    return sum(args) / len(args) if args else 0.0


def fn_clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def fn_if(cond, true_val: float, false_val: float) -> float:
    return true_val if cond else false_val


# ---------------------------------------------------------------------------
# Function registry
# ---------------------------------------------------------------------------
# name → (callable, min_args, max_args or None for variadic)

FUNCTION_REGISTRY: dict[str, tuple] = {
    'abs':   (fn_abs,   1, 1),
    'min':   (fn_min,   2, 2),
    'max':   (fn_max,   2, 2),
    'sqrt':  (fn_sqrt,  1, 1),
    'avg':   (fn_avg,   2, None),   # variadic, 2+
    'clamp': (fn_clamp, 3, 3),
    'if':    (fn_if,    3, 3),
}

# Stateful functions handled specially by the evaluator (first arg is a channel name)
STATEFUL_FUNCTIONS = {
    'prev', 'delta', 'rate',
    'rolling_avg', 'rolling_max', 'rolling_min',
    'lap_avg', 'lap_max', 'lap_min', 'lap_start',
}

ALL_FUNCTION_NAMES = set(FUNCTION_REGISTRY.keys()) | STATEFUL_FUNCTIONS

# Constants available in formulas
CONSTANTS: dict[str, float] = {
    'pi': math.pi,
    'e': math.e,
}
