"""Small utility functions shared across the application."""

from PyQt6.QtWidgets import QFrame, QLabel
from .constants import sans
from .theme import BORDER_STRONG as BORDER2, TEXT_MUTED as TXT2


def _safe_list(obj, length: int, default: float = 0.0) -> list:
    """Return a list of `length` floats from obj, padding/truncating as needed."""
    try:
        return [float(obj[i]) for i in range(length)]
    except Exception:
        return [default] * length


def h_line() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f'color: {BORDER2}; background: {BORDER2};')
    line.setFixedHeight(1)
    return line


def _channel_header(color: str, name: str, unit: str = '') -> QLabel:
    """Small colored-square + channel name header for graph sections."""
    txt = f'■  {name}'
    if unit:
        txt += f'  ·  {unit}'
    lbl = QLabel(txt)
    lbl.setFont(sans(9))
    lbl.setStyleSheet(f'color: {color}; letter-spacing: 0.8px; padding-top: 6px;')
    return lbl


def _vsep() -> QFrame:
    """Thin vertical separator line."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setStyleSheet(f'color: {BORDER2}; background: {BORDER2};')
    sep.setFixedWidth(1)
    return sep


def _interp_time_at_dist(dists: list, times: list, target: float) -> float | None:
    """Return interpolated time_ms at target distance using binary search."""
    if not dists or target < dists[0]:
        return None
    if target >= dists[-1]:
        return float(times[-1])
    lo, hi = 0, len(dists) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if dists[mid] <= target:
            lo = mid
        else:
            hi = mid
    span = dists[hi] - dists[lo]
    if span == 0:
        return float(times[lo])
    t = (target - dists[lo]) / span
    return times[lo] + t * (times[hi] - times[lo])


def _compute_sector_times(dists: list, times: list,
                          boundaries_m: list) -> list:
    """Return list of per-sector durations (s) at each distance boundary.
    Returns None for sectors not yet reached."""
    if not dists or not times:
        return [None] * len(boundaries_m)
    result = []
    prev_ms = 0.0
    for b in boundaries_m:
        t = _interp_time_at_dist(dists, times, b)
        if t is not None:
            result.append((t - prev_ms) / 1000.0)
            prev_ms = t
        else:
            result.append(None)
    return result
