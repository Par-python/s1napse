"""Matplotlib-based graph widgets for telemetry visualization."""

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtWidgets import QSizePolicy

from ..constants import (
    BG, BG1, TXT2, WHITE, MONZA_LENGTH_M,
    C_SPEED, C_THROTTLE, C_BRAKE, C_DELTA, C_PURPLE, C_REF,
)
from ..utils import _interp_time_at_dist


def _style_ax(ax, fig, ylabel: str = '', ylim=None):
    """Apply consistent MoTeC-inspired dark styling to an axes object."""
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG1)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#303030')
    ax.spines['bottom'].set_color('#303030')
    ax.tick_params(colors=TXT2, labelsize=7, length=3)
    ax.grid(True, color='#1c1c1c', linewidth=0.8, linestyle='-', axis='y')
    if ylabel:
        ax.set_ylabel(ylabel, color=TXT2, fontsize=8, labelpad=4)
    if ylim:
        ax.set_ylim(ylim)
    fig.subplots_adjust(left=0.09, right=0.98, top=0.95, bottom=0.22)


class ChannelGraph(FigureCanvas):
    """Single-channel live telemetry graph."""

    def __init__(self, color: str, ylabel: str, ylim=(0, 100), parent=None):
        self.fig = Figure(figsize=(8, 2.2), facecolor=BG)
        super().__init__(self.fig)
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ax = self.fig.add_subplot(111)
        _style_ax(self.ax, self.fig, ylabel=ylabel, ylim=ylim)
        self.setMinimumHeight(160)
        self.data = []
        self.line, = self.ax.plot([], [], color=color, linewidth=1.4)

    def update_data(self, value: float):
        self.data.append(value)
        x = range(len(self.data))
        self.line.set_data(x, self.data)
        self.ax.set_xlim(0, max(1, len(self.data)))
        self.draw_idle()

    def clear(self):
        self.data.clear()
        self.line.set_data([], [])
        self.ax.set_xlim(0, 1)
        self.draw_idle()


class MultiChannelGraph(FigureCanvas):
    """Two-channel live telemetry graph."""

    def __init__(self, color1: str, color2: str, ylabel: str,
                 label1: str, label2: str, ylim=(0, 100), parent=None):
        self.fig = Figure(figsize=(8, 2.2), facecolor=BG)
        super().__init__(self.fig)
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ax = self.fig.add_subplot(111)
        _style_ax(self.ax, self.fig, ylabel=ylabel, ylim=ylim)
        self.setMinimumHeight(160)
        self.data1, self.data2 = [], []
        self.line1, = self.ax.plot([], [], color=color1, linewidth=1.4, label=label1)
        self.line2, = self.ax.plot([], [], color=color2, linewidth=1.4, label=label2)
        self.ax.legend(fontsize=7, framealpha=0, loc='upper right',
                       labelcolor=TXT2)

    def update_data(self, v1: float, v2: float):
        self.data1.append(v1)
        self.data2.append(v2)
        x = range(len(self.data1))
        self.line1.set_data(x, self.data1)
        self.line2.set_data(x, self.data2)
        self.ax.set_xlim(0, max(1, len(self.data1)))
        self.draw_idle()

    def clear(self):
        self.data1.clear()
        self.data2.clear()
        self.line1.set_data([], [])
        self.line2.set_data([], [])
        self.ax.set_xlim(0, 1)
        self.draw_idle()


class AnalysisTelemetryGraph(FigureCanvas):
    """Distance-based single channel graph for lap analysis."""

    def __init__(self, ylabel: str, color: str = C_SPEED, ylim=(0, 100), parent=None):
        self.fig = Figure(figsize=(4, 1.2), facecolor=BG)
        super().__init__(self.fig)
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ax = self.fig.add_subplot(111)
        _style_ax(self.ax, self.fig, ylabel=ylabel, ylim=ylim)
        self.distances, self.values = [], []
        self.line, = self.ax.plot([], [], color=color, linewidth=1.2)
        self.vline = self.ax.axvline(0, color=WHITE, linewidth=0.8, alpha=0.5)

    def update_data(self, distance_m: float, value: float):
        self.distances.append(distance_m)
        self.values.append(value)
        self.line.set_data(self.distances, self.values)
        self.ax.set_xlim(0, max(MONZA_LENGTH_M, distance_m))
        self.vline.set_xdata([distance_m])
        self.draw_idle()

    def clear(self):
        self.distances.clear()
        self.values.clear()
        self.line.set_data([], [])
        self.vline.set_xdata([0])
        self.ax.set_xlim(0, MONZA_LENGTH_M)
        self.draw_idle()


class AnalysisMultiLineGraph(FigureCanvas):
    """Distance-based two-channel graph for lap analysis."""

    def __init__(self, ylabel: str, label1: str, label2: str,
                 color1: str = C_THROTTLE, color2: str = C_BRAKE,
                 ylim=(0, 100), parent=None):
        self.fig = Figure(figsize=(4, 1.2), facecolor=BG)
        super().__init__(self.fig)
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ax = self.fig.add_subplot(111)
        _style_ax(self.ax, self.fig, ylabel=ylabel, ylim=ylim)
        self.distances, self.v1, self.v2 = [], [], []
        self.line1, = self.ax.plot([], [], color=color1, linewidth=1.2, label=label1)
        self.line2, = self.ax.plot([], [], color=color2, linewidth=1.2, label=label2)
        self.ax.legend(fontsize=6, framealpha=0, loc='upper right', labelcolor=TXT2)
        self.vline = self.ax.axvline(0, color=WHITE, linewidth=0.8, alpha=0.5)

    def update_data(self, distance_m: float, val1: float, val2: float):
        self.distances.append(distance_m)
        self.v1.append(val1)
        self.v2.append(val2)
        self.line1.set_data(self.distances, self.v1)
        self.line2.set_data(self.distances, self.v2)
        self.ax.set_xlim(0, max(MONZA_LENGTH_M, distance_m))
        self.vline.set_xdata([distance_m])
        self.draw_idle()

    def clear(self):
        self.distances.clear()
        self.v1.clear()
        self.v2.clear()
        self.line1.set_data([], [])
        self.line2.set_data([], [])
        self.vline.set_xdata([0])
        self.ax.set_xlim(0, MONZA_LENGTH_M)
        self.draw_idle()


class TimeDeltaGraph(FigureCanvas):
    """Time delta vs distance with fill bands."""

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(10, 1.8), facecolor=BG)
        super().__init__(self.fig)
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ax = self.fig.add_subplot(111)
        _style_ax(self.ax, self.fig, ylabel='Delta (s)')
        self.ax.axhline(0, color=C_REF, linewidth=1, alpha=0.8)
        self.distances, self.deltas = [], []
        self.current_dist = 0
        self.line, = self.ax.plot([], [], color=C_DELTA, linewidth=1.4)
        self.vline = self.ax.axvline(0, color=WHITE, linewidth=0.8, alpha=0.5)
        self._fill_pos = None
        self._fill_neg = None

    def update_data(self, distances, deltas, current_distance_m: float):
        self.distances = list(distances) if distances else []
        self.deltas = list(deltas) if deltas else []
        self.current_dist = current_distance_m

        if self._fill_pos:
            self._fill_pos.remove()
            self._fill_pos = None
        if self._fill_neg:
            self._fill_neg.remove()
            self._fill_neg = None

        if self.distances and self.deltas:
            self.line.set_data(self.distances, self.deltas)
            self.ax.set_xlim(0, max(MONZA_LENGTH_M, max(self.distances)))
            mn = min(-0.2, min(self.deltas) - 0.02)
            mx = max(0.2, max(self.deltas) + 0.02)
            self.ax.set_ylim(mn, mx)
            try:
                import numpy as np
                d = np.array(self.distances)
                v = np.array(self.deltas)
                self._fill_pos = self.ax.fill_between(d, 0, v, where=(v > 0),
                                                       color=C_REF, alpha=0.12)
                self._fill_neg = self.ax.fill_between(d, 0, v, where=(v <= 0),
                                                       color=C_DELTA, alpha=0.12)
            except ImportError:
                pass

        self.vline.set_xdata([current_distance_m])
        self.draw_idle()

    def clear(self):
        if self._fill_pos:
            self._fill_pos.remove()
            self._fill_pos = None
        if self._fill_neg:
            self._fill_neg.remove()
            self._fill_neg = None
        self.distances.clear()
        self.deltas.clear()
        self.line.set_data([], [])
        self.vline.set_xdata([0])
        self.ax.set_xlim(0, MONZA_LENGTH_M)
        self.ax.set_ylim(-0.2, 0.2)
        self.draw_idle()


class ComparisonGraph(FigureCanvas):
    """Overlaid two-lap distance-based graph."""

    def __init__(self, ylabel: str, color_a: str, color_b: str,
                 ylim=(0, 100), parent=None):
        self.fig = Figure(figsize=(8, 1.8), facecolor=BG)
        super().__init__(self.fig)
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ax = self.fig.add_subplot(111)
        _style_ax(self.ax, self.fig, ylabel=ylabel, ylim=ylim)
        self.setMinimumHeight(140)
        self.line_a, = self.ax.plot([], [], color=color_a, linewidth=1.4,
                                    linestyle='-', alpha=0.9)
        self.line_b, = self.ax.plot([], [], color=color_b, linewidth=1.4,
                                    linestyle='--', alpha=0.75)

    def set_data(self, dists_a: list, vals_a: list,
                 dists_b: list, vals_b: list):
        max_d = max((dists_a[-1] if dists_a else 0),
                    (dists_b[-1] if dists_b else 0),
                    MONZA_LENGTH_M)
        if dists_a and vals_a:
            self.line_a.set_data(dists_a, vals_a)
        if dists_b and vals_b:
            self.line_b.set_data(dists_b, vals_b)
        self.ax.set_xlim(0, max_d)
        self.draw_idle()

    def clear(self):
        self.line_a.set_data([], [])
        self.line_b.set_data([], [])
        self.ax.set_xlim(0, MONZA_LENGTH_M)
        self.draw_idle()


class ComparisonDeltaGraph(FigureCanvas):
    """Time delta between two saved laps."""

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(8, 1.8), facecolor=BG)
        super().__init__(self.fig)
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ax = self.fig.add_subplot(111)
        _style_ax(self.ax, self.fig, ylabel='Delta (s)')
        self.ax.axhline(0, color=TXT2, linewidth=0.8, alpha=0.6)
        self.setMinimumHeight(140)
        self.line, = self.ax.plot([], [], color=C_DELTA, linewidth=1.4)
        self._fill_pos = None
        self._fill_neg = None

    def set_data(self, dists_a: list, times_a: list,
                 dists_b: list, times_b: list):
        if self._fill_pos:
            self._fill_pos.remove()
            self._fill_pos = None
        if self._fill_neg:
            self._fill_neg.remove()
            self._fill_neg = None

        if not dists_a or not dists_b:
            self.line.set_data([], [])
            self.draw_idle()
            return

        step = max(dists_a[-1], dists_b[-1]) / 500
        sample_dists = [i * step for i in range(501)]
        deltas = []
        for d in sample_dists:
            ta = _interp_time_at_dist(dists_a, times_a, d)
            tb = _interp_time_at_dist(dists_b, times_b, d)
            if ta is not None and tb is not None:
                deltas.append((ta - tb) / 1000.0)
            else:
                deltas.append(None)

        valid = [(d, v) for d, v in zip(sample_dists, deltas) if v is not None]
        if not valid:
            self.draw_idle()
            return
        xd, yd = zip(*valid)
        self.line.set_data(xd, yd)
        self.ax.set_xlim(0, max(xd))
        mn = min(min(yd) - 0.05, -0.2)
        mx = max(max(yd) + 0.05,  0.2)
        self.ax.set_ylim(mn, mx)
        try:
            import numpy as np
            xa, ya = np.array(xd), np.array(yd)
            self._fill_pos = self.ax.fill_between(
                xa, 0, ya, where=(ya > 0), color=C_REF, alpha=0.15)
            self._fill_neg = self.ax.fill_between(
                xa, 0, ya, where=(ya <= 0), color=C_DELTA, alpha=0.15)
        except ImportError:
            pass
        self.draw_idle()

    def clear(self):
        if self._fill_pos:
            self._fill_pos.remove()
            self._fill_pos = None
        if self._fill_neg:
            self._fill_neg.remove()
            self._fill_neg = None
        self.line.set_data([], [])
        self.ax.set_xlim(0, MONZA_LENGTH_M)
        self.ax.set_ylim(-0.2, 0.2)
        self.draw_idle()


class RacePaceChart(FigureCanvas):
    """Session lap times scatter/line chart for race pace trend."""

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(8, 2.0), facecolor=BG)
        super().__init__(self.fig)
        self.setMinimumWidth(100)
        self.setMinimumHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ax = self.fig.add_subplot(111)
        _style_ax(self.ax, self.fig, ylabel='Lap (s)')
        self.ax.set_xlabel('Lap', color=TXT2, fontsize=7)

    def refresh(self, session_laps: list):
        self.ax.cla()
        _style_ax(self.ax, self.fig, ylabel='Lap (s)')
        if not session_laps:
            self.draw_idle()
            return

        times = [l['total_time_s'] for l in session_laps if l.get('total_time_s', 0) > 20]
        laps  = [l['lap_number'] for l in session_laps if l.get('total_time_s', 0) > 20]
        if not times:
            self.draw_idle()
            return

        best_t = min(times)
        from ..constants import BORDER2 as _B2
        colors = [C_PURPLE if abs(t - best_t) < 0.001 else C_SPEED for t in times]

        self.ax.plot(laps, times, color=_B2, linewidth=1.0, zorder=1)
        self.ax.scatter(laps, times, c=colors, s=20, zorder=2)
        self.ax.set_xlim(min(laps) - 0.5, max(laps) + 0.5)
        padding = max(1.0, (max(times) - min(times)) * 0.2)
        self.ax.set_ylim(min(times) - padding, max(times) + padding)
        self.draw_idle()


class ReplayGraph(FigureCanvas):
    """Full-lap single-channel graph with a movable playhead line."""

    def __init__(self, ylabel: str, color: str, ylim=(0, 100), parent=None):
        self.fig = Figure(figsize=(8, 1.5), facecolor=BG)
        super().__init__(self.fig)
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ax = self.fig.add_subplot(111)
        _style_ax(self.ax, self.fig, ylabel=ylabel, ylim=ylim)
        self.setMinimumHeight(110)
        self.line, = self.ax.plot([], [], color=color, linewidth=1.2)
        self.vline = self.ax.axvline(0, color=WHITE, linewidth=1.0, alpha=0.7)

    def set_lap_data(self, times_ms: list, values: list):
        if not times_ms:
            self.line.set_data([], [])
            self.ax.set_xlim(0, 1)
            self.draw_idle()
            return
        times_s = [t / 1000.0 for t in times_ms]
        self.line.set_data(times_s, values)
        self.ax.set_xlim(0, max(times_s[-1], 0.001))
        self.draw_idle()

    def set_playhead(self, time_ms: float):
        self.vline.set_xdata([time_ms / 1000.0])
        self.draw_idle()

    def clear(self):
        self.line.set_data([], [])
        self.vline.set_xdata([0])
        self.ax.set_xlim(0, 1)
        self.draw_idle()


class ReplayMultiGraph(FigureCanvas):
    """Full-lap dual-channel graph with a movable playhead line."""

    def __init__(self, ylabel: str, color1: str, color2: str,
                 label1: str, label2: str, ylim=(0, 100), parent=None):
        self.fig = Figure(figsize=(8, 1.5), facecolor=BG)
        super().__init__(self.fig)
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ax = self.fig.add_subplot(111)
        _style_ax(self.ax, self.fig, ylabel=ylabel, ylim=ylim)
        self.setMinimumHeight(110)
        self.line1, = self.ax.plot([], [], color=color1, linewidth=1.2, label=label1)
        self.line2, = self.ax.plot([], [], color=color2, linewidth=1.2, label=label2)
        self.ax.legend(fontsize=7, framealpha=0, loc='upper right', labelcolor=TXT2)
        self.vline = self.ax.axvline(0, color=WHITE, linewidth=1.0, alpha=0.7)

    def set_lap_data(self, times_ms: list, vals1: list, vals2: list):
        if not times_ms:
            self.line1.set_data([], [])
            self.line2.set_data([], [])
            self.ax.set_xlim(0, 1)
            self.draw_idle()
            return
        times_s = [t / 1000.0 for t in times_ms]
        self.line1.set_data(times_s, vals1)
        self.line2.set_data(times_s, vals2)
        self.ax.set_xlim(0, max(times_s[-1], 0.001))
        self.draw_idle()

    def set_playhead(self, time_ms: float):
        self.vline.set_xdata([time_ms / 1000.0])
        self.draw_idle()

    def clear(self):
        self.line1.set_data([], [])
        self.line2.set_data([], [])
        self.vline.set_xdata([0])
        self.ax.set_xlim(0, 1)
        self.draw_idle()
