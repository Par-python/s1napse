"""Coach tab: the quick win for the last lap, then every corner graded."""

from __future__ import annotations

import html
import re

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QStackedLayout,
    QVBoxLayout, QWidget,
)

from ... import theme
from ...coaching.insight_messages import (
    braking_message, corner_message, session_progress_text, trail_brake_message,
    tyre_summary_text,
)
from ...coaching.models import CornerPerformance, LapReport
from ..primitives import Card
from ..graphs import _style_ax

_GRADE_COLOURS = {'green': theme.GOOD, 'yellow': theme.WARN, 'red': theme.BAD}


def _label(text: str, *, size: int = theme.FONT_BODY, color: str = theme.TEXT_SECONDARY,
           wrap: bool = True, weight=None) -> QLabel:
    lbl = QLabel(text)
    f = theme.ui_font(size)
    if weight is not None:
        f.setWeight(weight)
    lbl.setFont(f)
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(f'color:{color}; background:transparent; border:none;')
    return lbl


def _fmt_lap(seconds: float) -> str:
    m = int(seconds // 60)
    return f'{m}:{seconds - 60 * m:06.3f}'


class _CornerRow(QFrame):
    """One corner: grade dot, name, delta, and the coaching message."""

    def __init__(self, perf: CornerPerformance, extra: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName('CornerRow')
        self.setStyleSheet(
            f'#CornerRow {{ background:{theme.SURFACE}; border:none;'
            f' border-radius:{theme.RADIUS["lg"]}px; }}'
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(10)
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(
            f'background:{_GRADE_COLOURS.get(perf.grade, theme.TEXT_FAINT)}; border-radius:5px;'
        )
        head.addWidget(dot)
        c = perf.corner
        head.addWidget(_label(f'Turn {c.corner_id} · {c.direction.lower()}',
                              size=theme.FONT_BODY + 1, color=theme.TEXT_PRIMARY, wrap=False,
                              weight=theme.QFont.Weight.DemiBold))
        head.addStretch(1)
        d = perf.delta_vs_best
        delta = QLabel(f'{d:+.2f}s')
        delta.setFont(theme.mono_font(theme.FONT_BODY + 1, bold=True))
        tone = theme.BAD_FG if d > 0.05 else theme.GOOD_FG if d < -0.01 else theme.TEXT_MUTED
        delta.setStyleSheet(f'color:{tone}; background:transparent; border:none;')
        head.addWidget(delta)
        outer.addLayout(head)

        # corner_message() starts with "Turn N (dir): " — the row header already says that.
        body = corner_message(perf).split(': ', 1)[-1]
        outer.addWidget(_label(body))
        for line in extra:
            outer.addWidget(_label(line.split(': ', 1)[-1], color=theme.TEXT_MUTED,
                                   size=theme.FONT_BODY - 1))


class CoachTab(QWidget):
    """Left: quick win, lap picker, lap-time trend, session + tyres. Right: corners."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._report: LapReport | None = None
        self._history: list[LapReport] = []
        self._corner_rows: list[_CornerRow] = []

        self._stack = QStackedLayout(self)

        # --- empty state ------------------------------------------------
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.addStretch(1)
        msg = _label('Drive a full lap and S1napse will show where you can find time.',
                     size=theme.FONT_VALUE - 4, color=theme.TEXT_MUTED)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(msg)
        el.addStretch(1)
        self._stack.addWidget(empty)

        # --- content ----------------------------------------------------
        content = QWidget()
        row = QHBoxLayout(content)
        row.setContentsMargins(20, 20, 20, 20)
        row.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(16)
        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(380)

        self._quick = Card(label='Quick win')
        self._quick_lbl = _label('', size=theme.FONT_VALUE, color=theme.TEXT_PRIMARY,
                                 weight=theme.QFont.Weight.DemiBold)
        self._quick.body().addWidget(self._quick_lbl)
        left.addWidget(self._quick)

        lap_card = Card(label='Lap')
        self._picker = QComboBox()
        self._picker.currentIndexChanged.connect(self._on_pick)
        lap_card.body().addWidget(self._picker)
        self._lap_line = _label('', color=theme.TEXT_MUTED)
        lap_card.body().addWidget(self._lap_line)
        self._lap_fig = Figure(figsize=(3.2, 1.4), facecolor=theme.SURFACE)
        self._lap_ax = self._lap_fig.add_subplot(111)
        self._trend = FigureCanvas(self._lap_fig)
        self._trend.setFixedHeight(140)
        lap_card.body().addWidget(self._trend)
        left.addWidget(lap_card)

        self._session_card = Card(label='Session progress')
        self._session_lbl = _label('')
        self._session_card.body().addWidget(self._session_lbl)
        left.addWidget(self._session_card)

        self._tyre_card = Card(label='Tyres')
        self._tyre_lbl = _label('')
        self._tyre_card.body().addWidget(self._tyre_lbl)
        left.addWidget(self._tyre_card)
        left.addStretch(1)
        row.addWidget(left_w)

        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(_label('Corners', size=theme.FONT_LABEL, color=theme.TEXT_MUTED, wrap=False))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget()
        self._corner_list = QVBoxLayout(holder)
        self._corner_list.setContentsMargins(0, 0, 0, 0)
        self._corner_list.setSpacing(10)
        self._corner_msg = _label('', color=theme.TEXT_MUTED)
        self._corner_list.addWidget(self._corner_msg)
        self._corner_list.addStretch(1)
        scroll.setWidget(holder)
        right.addWidget(scroll, 1)
        right_w = QWidget()
        right_w.setLayout(right)
        row.addWidget(right_w, 1)

        self._stack.addWidget(content)
        self._stack.setCurrentIndex(0)

    # -- public -----------------------------------------------------------
    def set_report(self, report: LapReport | None, history: list[LapReport] | None = None) -> None:
        if report is None:
            return
        self._history = list(history) if history else [report]
        self._picker.blockSignals(True)
        self._picker.clear()
        for r in self._history:
            self._picker.addItem(f'Lap {r.lap_number} · {_fmt_lap(r.lap_time_s)}')
        self._picker.setCurrentIndex(self._history.index(report) if report in self._history
                                     else len(self._history) - 1)
        self._picker.blockSignals(False)
        self._show(report)

    def isEmptyState(self) -> bool:     return self._stack.currentIndex() == 0
    def quickWinText(self) -> str:      return self._quick_lbl.text()
    def cornerCount(self) -> int:       return len(self._corner_rows)
    def cornerListMessage(self) -> str: return self._corner_msg.text()
    def lapPickerCount(self) -> int:    return self._picker.count()

    # -- internals --------------------------------------------------------
    def _on_pick(self, idx: int) -> None:
        if 0 <= idx < len(self._history):
            self._show(self._history[idx])

    def _show(self, report: LapReport) -> None:
        self._report = report
        self._stack.setCurrentIndex(1)

        message = report.quick_win_message or 'Clean lap. Nothing stands out; keep building consistency.'
        highlighted = re.sub(r'(~[0-9]+(?:\.[0-9]+)?s)',
                             lambda m: f'<span style="color:{theme.GOOD_FG}">{m.group(1)}</span>',
                             html.escape(message))
        self._quick_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._quick_lbl.setText(highlighted)
        pb = ' · personal best' if report.is_personal_best else f' · {report.delta_vs_best_lap:+.3f}s vs best'
        self._lap_line.setText(f'Lap {report.lap_number} · {_fmt_lap(report.lap_time_s)}{pb}')

        sp = report.session_progress
        times = list(sp.lap_times) if sp and sp.lap_times else [r.lap_time_s for r in self._history]
        self._lap_ax.clear()
        _style_ax(self._lap_ax, self._lap_fig)
        best = min(times)
        numbers = ([r.lap_number for r in self._history] if len(times) == len(self._history)
                   else list(range(1, len(times) + 1)))
        self._lap_ax.bar(numbers, times, color=[theme.GOOD if v == best else theme.ACCENT for v in times])
        self._lap_ax.set_xticks(numbers)
        self._lap_ax.set_ylabel('Seconds', color=theme.TEXT_MUTED, fontsize=theme.FONT_FINE)
        self._lap_fig.subplots_adjust(left=0.19, right=0.97, bottom=0.23, top=0.95)
        self._trend.draw_idle()
        self._session_lbl.setText(session_progress_text(sp) or 'More laps needed for trends.')
        self._tyre_lbl.setText(tyre_summary_text(report.tyre_summary) or 'No tyre data for this lap.')

        for w in self._corner_rows:
            w.setParent(None)
            w.deleteLater()
        self._corner_rows = []
        braking = {b.corner.corner_id: b for b in report.braking_analyses}
        trail = {t.corner.corner_id: t for t in report.trail_brake_analyses}
        perfs = sorted(report.corner_performances, key=lambda p: p.corner.corner_id)
        for perf in perfs:
            extra = []
            cid = perf.corner.corner_id
            if cid in braking:
                extra.append(braking_message(braking[cid]))
            if cid in trail and trail[cid].detected:
                extra.append(trail_brake_message(trail[cid]))
            row = _CornerRow(perf, [e for e in extra if e])
            self._corner_list.insertWidget(self._corner_list.count() - 1, row)
            self._corner_rows.append(row)
        self._corner_msg.setText('' if perfs else 'No corners detected on this lap yet.')
        self._corner_msg.setVisible(not perfs)
