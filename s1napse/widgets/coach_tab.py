"""Coach tab — coaching insights UI for the S1napse telemetry dashboard."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QComboBox, QSplitter,
)

from ..constants import C_SPEED
from .. import theme
from ..theme import (
    BG, SURFACE as BG1,
    BORDER_STRONG as BORDER2,
    TEXT_SECONDARY as TXT, TEXT_MUTED as TXT2, TEXT_PRIMARY as WHITE,
)
from .primitives import Card
from ..coaching.models import (
    LapReport, CornerPerformance, BrakingAnalysis,
    TrailBrakeAnalysis, TyreLapSummary, SessionProgress,
)
from ..coaching.insight_messages import (
    corner_message, braking_message, trail_brake_message,
    lap_summary_text, grade_summary_text,
    trail_brake_summary_text, tyre_summary_text,
    session_progress_text,
)


# Grade colours
_C_GREEN = '#00C853'
_C_YELLOW = '#FFD600'
_C_RED = '#FF1744'

_GRADE_COLORS = {
    'green': _C_GREEN,
    'yellow': _C_YELLOW,
    'red': _C_RED,
}

# Trail brake stage → (icon, colour)
_TB_STYLE = {
    0: ("\u274C", _C_RED),
    1: ("\u26A0\uFE0F", _C_YELLOW),
    2: ("\u2705", _C_GREEN),
}


class CoachTab(QWidget):
    """Two-column coaching tab: overview (left) + detail panel (right)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._report: LapReport | None = None
        self._all_reports: list[LapReport] = []

        self._build_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_report(self, report: LapReport) -> None:
        """Display a new lap report."""
        self._report = report
        if report not in self._all_reports:
            self._all_reports.append(report)
            self._lap_combo.blockSignals(True)
            self._lap_combo.addItem(f"Lap {report.lap_number}")
            self._lap_combo.setCurrentIndex(self._lap_combo.count() - 1)
            self._lap_combo.blockSignals(False)
        self._refresh()

    def set_corners_on_map(self, corners, trail_analyses, track_widget) -> None:
        """Overlay corner numbers + trail brake icons on the track map."""
        if not corners or track_widget is None:
            return
        length_m = getattr(track_widget, '_track_length', None)
        if length_m is None or length_m <= 0:
            return

        # Build a lookup for trail brake stage by corner_id
        tb_map: dict[int, int] = {}
        if trail_analyses:
            for tb in trail_analyses:
                tb_map[tb.corner.corner_id] = tb.stage

        turns = []
        for c in corners:
            frac = c.apex_distance / length_m
            frac = max(0.0, min(1.0, frac))
            icon = _TB_STYLE.get(tb_map.get(c.corner_id, 0), ("\u274C", _C_RED))[0]
            label = f"{c.corner_id}{icon}"
            turns.append((frac, label, '', 0, -14))
        track_widget._turns = turns
        track_widget.update()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(2)

        # ── Left: overview panel ─────────────────────────────────────
        left = QWidget()
        left.setStyleSheet(f'background: {BG1};')
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(12, 12, 12, 12)
        left_lay.setSpacing(8)

        # Lap summary header
        self._summary_label = QLabel("Waiting for first lap...")
        self._summary_label.setFont(theme.mono_font(13, bold=True))
        self._summary_label.setStyleSheet(f'color: {WHITE};')
        self._summary_label.setWordWrap(True)
        left_lay.addWidget(self._summary_label)

        # Corner grade counts
        self._grade_label = QLabel("")
        self._grade_label.setFont(theme.mono_font(10))
        self._grade_label.setStyleSheet(f'color: {TXT2};')
        left_lay.addWidget(self._grade_label)

        # Trail braking summary line
        self._trail_label = QLabel("")
        self._trail_label.setFont(theme.mono_font(10))
        self._trail_label.setStyleSheet(f'color: {TXT2};')
        left_lay.addWidget(self._trail_label)

        # Tyre summary line
        self._tyre_label = QLabel("")
        self._tyre_label.setFont(theme.mono_font(10))
        self._tyre_label.setStyleSheet(f'color: {TXT2};')
        left_lay.addWidget(self._tyre_label)

        # Braking consistency
        self._consistency_label = QLabel("")
        self._consistency_label.setFont(theme.mono_font(10))
        self._consistency_label.setStyleSheet(f'color: {TXT2};')
        left_lay.addWidget(self._consistency_label)

        # ── Live tips: Quick Win card (top, no stretch) ──────────────
        self._live_tips_card = Card(label='QUICK WIN', dense=True)
        self._quick_win_body = QLabel("")
        self._quick_win_body.setFont(theme.ui_font(10))
        self._quick_win_body.setStyleSheet(f'color: {TXT};')
        self._quick_win_body.setWordWrap(True)
        self._live_tips_card.body().addWidget(self._quick_win_body)
        left_lay.addWidget(self._live_tips_card, 0)

        # Tyre detail card (top, no stretch)
        self._tyre_card = Card(label='TYRES', dense=True)
        self._tyre_body = QLabel("")
        self._tyre_body.setFont(theme.ui_font(10))
        self._tyre_body.setStyleSheet(f'color: {TXT};')
        self._tyre_body.setWordWrap(True)
        self._tyre_card.body().addWidget(self._tyre_body)
        left_lay.addWidget(self._tyre_card, 0)

        # ── History: Session progress card (bottom, stretch=1) ───────
        self._history_card = Card(label='SESSION PROGRESS', dense=True)
        self._progress_body = QLabel("")
        self._progress_body.setFont(theme.ui_font(10))
        self._progress_body.setStyleSheet(f'color: {TXT};')
        self._progress_body.setWordWrap(True)
        self._history_card.body().addWidget(self._progress_body)

        # Lap time sparkline inside history card
        self._sparkline = _Sparkline()
        self._sparkline.setFixedHeight(60)
        self._history_card.body().addWidget(self._sparkline)

        left_lay.addWidget(self._history_card, 1)

        left_lay.addStretch()

        # ── Right: corner detail list ────────────────────────────────
        right = QWidget()
        right.setStyleSheet(f'background: {BG};')
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(8, 8, 8, 8)
        right_lay.setSpacing(4)

        # Lap selector
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Lap:"))
        self._lap_combo = QComboBox()
        self._lap_combo.setFixedWidth(110)
        self._lap_combo.currentIndexChanged.connect(self._on_lap_selected)
        top_bar.addWidget(self._lap_combo)
        top_bar.addStretch()
        right_lay.addLayout(top_bar)

        # Scrollable corner list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._corner_container = QWidget()
        self._corner_layout = QVBoxLayout(self._corner_container)
        self._corner_layout.setContentsMargins(0, 0, 0, 0)
        self._corner_layout.setSpacing(4)
        self._corner_layout.addStretch()
        scroll.setWidget(self._corner_container)
        right_lay.addWidget(scroll, stretch=1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)

        root.addWidget(splitter)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh(self):
        r = self._report
        if r is None:
            return

        # Header
        self._summary_label.setText(lap_summary_text(r))
        self._grade_label.setText(grade_summary_text(r))

        # Trail braking summary
        if r.trail_brake_analyses:
            self._trail_label.setText(trail_brake_summary_text(r.trail_brake_analyses))
            self._trail_label.show()
        else:
            self._trail_label.hide()

        # Tyre summary line
        self._tyre_label.setText(tyre_summary_text(r.tyre_summary))

        # Braking consistency
        self._consistency_label.setText(
            f"Braking consistency: {r.braking_consistency_pct:.0f}%")

        # Quick win card (live tips)
        if r.quick_win_message:
            self._quick_win_body.setText(r.quick_win_message)
            self._live_tips_card.show()
        else:
            self._live_tips_card.hide()

        # Tyre detail card
        ts = r.tyre_summary
        if ts and ts.balance != "unknown":
            self._tyre_body.setText(ts.message)
            self._tyre_card.show()
        else:
            self._tyre_card.hide()

        # Session progress card (history)
        sp = r.session_progress
        if sp:
            txt = session_progress_text(sp)
            if txt:
                self._progress_body.setText(txt)
                self._history_card.show()
            else:
                self._history_card.hide()
            self._sparkline.set_data(sp.lap_times, sp.best_lap_number)
            self._sparkline.show()
        else:
            self._history_card.hide()
            self._sparkline.hide()

        # Rebuild corner cards
        self._clear_corner_list()

        # Build trail-brake lookup
        tb_map: dict[int, TrailBrakeAnalysis] = {}
        for tb in (r.trail_brake_analyses or []):
            tb_map[tb.corner.corner_id] = tb

        for perf in r.corner_performances:
            ba = None
            for b in r.braking_analyses:
                if b.corner.corner_id == perf.corner.corner_id:
                    ba = b
                    break
            tb = tb_map.get(perf.corner.corner_id)
            card = _CornerCard(perf, ba, tb)
            self._corner_layout.insertWidget(
                self._corner_layout.count() - 1, card)

    def _clear_corner_list(self):
        while self._corner_layout.count() > 1:
            item = self._corner_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _on_lap_selected(self, index: int):
        if 0 <= index < len(self._all_reports):
            self._report = self._all_reports[index]
            self._refresh()


# ======================================================================
# Helper widgets
# ======================================================================

class _Sparkline(QWidget):
    """Mini lap-time sparkline chart drawn with QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._times: list[float] = []
        self._best_lap: int = 0
        self.setMinimumHeight(40)

    def set_data(self, times: list[float], best_lap_number: int):
        self._times = list(times)
        self._best_lap = best_lap_number
        self.update()

    def paintEvent(self, event):
        if len(self._times) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width() - 8
        h = self.height() - 8
        ox, oy = 4, 4

        mn = min(self._times)
        mx = max(self._times)
        span = mx - mn if mx > mn else 1.0

        n = len(self._times)
        step = w / max(n - 1, 1)

        # Draw grid line at best time
        best_y = oy + h - ((mn - mn) / span) * h
        p.setPen(QPen(QColor(BORDER2), 1, Qt.PenStyle.DashLine))
        p.drawLine(int(ox), int(best_y), int(ox + w), int(best_y))

        # Draw line
        p.setPen(QPen(QColor(C_SPEED), 2))
        prev_x = prev_y = None
        for i, t in enumerate(self._times):
            x = ox + i * step
            y = oy + h - ((t - mn) / span) * h
            if prev_x is not None:
                p.drawLine(int(prev_x), int(prev_y), int(x), int(y))
            prev_x, prev_y = x, y

        # Highlight best lap dot
        if 1 <= self._best_lap <= n:
            idx = self._best_lap - 1
            bx = ox + idx * step
            by = oy + h - ((self._times[idx] - mn) / span) * h
            p.setBrush(QBrush(QColor('#a855f7')))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(bx - 4, by - 4, 8, 8))

        # Dot on latest
        last_x = ox + (n - 1) * step
        last_y = oy + h - ((self._times[-1] - mn) / span) * h
        p.setBrush(QBrush(QColor(WHITE)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(last_x - 3, last_y - 3, 6, 6))

        p.end()


class _CornerCard(QFrame):
    """Expandable card for one corner's coaching detail."""

    def __init__(self, perf: CornerPerformance,
                 ba: BrakingAnalysis | None,
                 tb: TrailBrakeAnalysis | None,
                 parent=None):
        super().__init__(parent)
        self._expanded = False
        self._perf = perf

        color = _GRADE_COLORS.get(perf.grade, TXT2)
        self.setStyleSheet(
            f'background: {theme.SURFACE_RAISED}; border: 1px solid {theme.BORDER_SUBTLE}; '
            f'border-left: 3px solid {color}; border-radius: {theme.RADIUS["md"]}px;')
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(10, 6, 10, 6)
        self._lay.setSpacing(2)

        # Header row: corner label + trail brake icon + delta
        hdr = QHBoxLayout()
        c = perf.corner
        dir_str = c.direction[0]  # L or R

        # Trail brake icon
        tb_icon = ""
        tb_color = TXT2
        if tb is not None:
            icon_str, tb_color = _TB_STYLE.get(tb.stage, ("\u274C", _C_RED))
            tb_icon = f" {icon_str}"

        lbl = QLabel(f"T{c.corner_id} ({dir_str}){tb_icon}")
        lbl.setFont(theme.mono_font(11, bold=True))
        lbl.setStyleSheet(f'color: {color}; border: none;')
        hdr.addWidget(lbl)

        delta_txt = _fmt_delta(perf.delta_vs_best)
        delta_lbl = QLabel(delta_txt)
        delta_lbl.setFont(theme.mono_font(11))
        delta_color = _C_GREEN if perf.delta_vs_best <= 0.005 else (
            _C_YELLOW if perf.delta_vs_best < 0.5 else _C_RED)
        delta_lbl.setStyleSheet(f'color: {delta_color}; border: none;')
        delta_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        hdr.addWidget(delta_lbl)
        self._lay.addLayout(hdr)

        # One-line issue
        self._issue_lbl = QLabel(corner_message(perf))
        self._issue_lbl.setFont(theme.ui_font(9))
        self._issue_lbl.setStyleSheet(f'color: {TXT}; border: none;')
        self._issue_lbl.setWordWrap(True)
        self._lay.addWidget(self._issue_lbl)

        # Detail section (hidden by default)
        self._detail = QWidget()
        self._detail.setVisible(False)
        detail_lay = QVBoxLayout(self._detail)
        detail_lay.setContentsMargins(0, 4, 0, 0)
        detail_lay.setSpacing(2)

        details = [
            f"Entry: {perf.entry_speed:.0f} km/h   "
            f"Apex: {perf.min_speed:.0f} km/h   "
            f"Exit: {perf.exit_speed:.0f} km/h",
            f"Braking dist: {perf.braking_distance:.0f}m   "
            f"Time: {perf.time_in_corner:.2f}s",
        ]
        if ba:
            details.append(
                f"Brake: {ba.peak_brake_pct:.0f}% peak, "
                f"{ba.brake_application_shape}   "
                f"Speed scrubbed: {ba.speed_scrubbed:.0f} km/h"
            )
            details.append(braking_message(ba))
        if tb:
            if tb.detected:
                details.append(
                    f"Trail brake: {tb.overlap_distance:.0f}m overlap, "
                    f"{tb.overlap_entry_brake_pct:.0f}% entry brake, "
                    f"release: {tb.release_quality}"
                )
            details.append(trail_brake_message(tb))

        for txt in details:
            d = QLabel(txt)
            d.setFont(theme.ui_font(9))
            d.setStyleSheet(f'color: {TXT2}; border: none;')
            d.setWordWrap(True)
            detail_lay.addWidget(d)

        self._lay.addWidget(self._detail)

    def mousePressEvent(self, event):
        self._expanded = not self._expanded
        self._detail.setVisible(self._expanded)
        super().mousePressEvent(event)


# ======================================================================
# Formatting helpers
# ======================================================================

def _fmt_delta(delta: float) -> str:
    if delta <= -0.005:
        return f"-{abs(delta):.2f}s"
    if delta >= 0.005:
        return f"+{delta:.2f}s"
    return "PB"
