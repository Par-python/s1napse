"""Lap Comparison tab — A/B lap pickers + side-by-side graphs + delta chart.

Roomy bucket. Selector bar at top, scrollable comparison graphs below (speed,
throttle, brake, gear, RPM, steering, delta). The spec calls for equal-weight
A/B columns, but the existing implementation uses a single set of overlaid
ComparisonGraph widgets (both laps on the same axes) which is functionally
equivalent and signal-heavy to restructure — kept as-is inside a Card.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel,
    QComboBox, QPushButton, QFrame,
)

from ... import theme
from ...constants import (
    C_SPEED, C_THROTTLE, C_BRAKE, C_RPM, C_GEAR, C_STEER, C_DELTA,
    mono, sans,
)
from ...theme import (
    BG, SURFACE_RAISED, SURFACE_HOVER, BORDER_SUBTLE, BORDER_STRONG,
    TEXT_SECONDARY, TEXT_MUTED,
)
from ...utils import _channel_header
from ..primitives import Card
from ..graphs import ComparisonGraph, ComparisonDeltaGraph

# Legacy shorthand aliases (match app.py)
BG2 = SURFACE_RAISED
BG3 = SURFACE_HOVER
BORDER = BORDER_SUBTLE
BORDER2 = BORDER_STRONG
TXT = TEXT_SECONDARY
TXT2 = TEXT_MUTED


class LapComparisonTab(QWidget):
    """Lap Comparison tab: selector bar + scrollable overlaid channel graphs."""

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        # ── Selector bar Card ─────────────────────────────────────────
        sel_card = Card(dense=False)
        sel_row = QHBoxLayout()
        sel_row.setSpacing(12)

        def _lbl(text, color=TXT2):
            l = QLabel(text)
            l.setFont(sans(8, bold=True))
            l.setStyleSheet(f'color: {color}; letter-spacing: 1px;')
            return l

        sel_row.addWidget(_lbl('LAP A'))
        self._app._cmp_combo_a = QComboBox()
        self._app._cmp_combo_a.setStyleSheet(
            f'background: {BG3}; color: {TXT}; border: 1px solid {BORDER2};'
            f' border-radius: 4px; padding: 4px 8px;')
        self._app._cmp_combo_a.setMinimumWidth(180)
        sel_row.addWidget(self._app._cmp_combo_a)

        self._app._cmp_time_a = QLabel('—')
        self._app._cmp_time_a.setFont(mono(9))
        self._app._cmp_time_a.setStyleSheet(f'color: {C_SPEED};')
        sel_row.addWidget(self._app._cmp_time_a)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f'color: {BORDER2};')
        sel_row.addWidget(sep)

        sel_row.addWidget(_lbl('LAP B'))
        self._app._cmp_combo_b = QComboBox()
        self._app._cmp_combo_b.setStyleSheet(
            f'background: {BG3}; color: {TXT}; border: 1px solid {BORDER2};'
            f' border-radius: 4px; padding: 4px 8px;')
        self._app._cmp_combo_b.setMinimumWidth(180)
        sel_row.addWidget(self._app._cmp_combo_b)

        self._app._cmp_time_b = QLabel('—')
        self._app._cmp_time_b.setFont(mono(9))
        self._app._cmp_time_b.setStyleSheet(f'color: {C_STEER};')
        sel_row.addWidget(self._app._cmp_time_b)

        sel_row.addStretch()

        self._app._cmp_delta_lbl = QLabel('')
        self._app._cmp_delta_lbl.setFont(mono(9, bold=True))
        self._app._cmp_delta_lbl.setStyleSheet(f'color: {TXT2};')
        sel_row.addWidget(self._app._cmp_delta_lbl)

        cmp_btn = QPushButton('COMPARE')
        cmp_btn.setFont(sans(8, bold=True))
        cmp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cmp_btn.setStyleSheet(
            f'background: {BG3}; color: {TXT}; border: 1px solid {BORDER2};'
            f' border-radius: 4px; padding: 6px 18px;'
            f' letter-spacing: 1px;')
        cmp_btn.clicked.connect(self._app._refresh_comparison)
        sel_row.addWidget(cmp_btn)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet(f'color: {BORDER2};')
        sel_row.addWidget(sep2)

        _btn_style = (
            f'QPushButton {{ background: {BG3}; color: {TXT2}; border: 1px solid {BORDER2};'
            f' border-radius: 4px; padding: 6px 12px; font-size: 10px; letter-spacing: 1px; }}'
            f'QPushButton:hover {{ color: {C_SPEED}; border-color: {C_SPEED}; }}'
        )

        export_lap_btn = QPushButton('⬇  EXPORT LAP')
        export_lap_btn.setFont(sans(8, bold=True))
        export_lap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_lap_btn.setStyleSheet(_btn_style)
        export_lap_btn.clicked.connect(self._app._export_lap_json)
        sel_row.addWidget(export_lap_btn)

        import_lap_btn = QPushButton('⬆  IMPORT LAP')
        import_lap_btn.setFont(sans(8, bold=True))
        import_lap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_lap_btn.setStyleSheet(_btn_style)
        import_lap_btn.clicked.connect(self._app._import_lap_json)
        sel_row.addWidget(import_lap_btn)

        sel_card.body().addLayout(sel_row)
        outer.addWidget(sel_card)

        # ── Legend ────────────────────────────────────────────────────
        legend_row = QHBoxLayout()
        legend_row.setSpacing(16)
        for label, color, style in [('Lap A', C_SPEED, '─────'),
                                     ('Lap B', C_STEER, '- - -')]:
            dot = QLabel(f'{style}  {label}')
            dot.setFont(mono(8))
            dot.setStyleSheet(f'color: {color};')
            legend_row.addWidget(dot)
        legend_row.addStretch()
        outer.addLayout(legend_row)

        # ── Scrollable graphs Card ────────────────────────────────────
        graphs_card = Card(dense=False)
        graphs_vbox = graphs_card.body()
        graphs_vbox.setSpacing(4)

        COLOR_A = '#00d4ff'  # cyan — Lap A
        COLOR_B = '#ffb020'  # amber — Lap B (high contrast vs cyan)

        self._app._cmp_speed = ComparisonGraph(
            'Speed km/h', COLOR_A, COLOR_B, ylim=(0, 320))
        self._app._cmp_thr_brk_a = ComparisonGraph(
            'Throttle %', COLOR_A, COLOR_B, ylim=(0, 100))
        self._app._cmp_brk = ComparisonGraph(
            'Brake %', C_BRAKE, '#ff99aa', ylim=(0, 100))
        self._app._cmp_gear = ComparisonGraph(
            'Gear', COLOR_A, COLOR_B, ylim=(-1, 8))
        self._app._cmp_rpm = ComparisonGraph(
            'RPM', C_RPM, '#ffdd88', ylim=(0, 10000))
        self._app._cmp_steer = ComparisonGraph(
            'Steer °', COLOR_A, COLOR_B, ylim=(-540, 540))

        for title, color, graph in [
            ('SPEED', C_SPEED, self._app._cmp_speed),
            ('THROTTLE', C_THROTTLE, self._app._cmp_thr_brk_a),
            ('BRAKE', C_BRAKE, self._app._cmp_brk),
            ('GEAR', C_GEAR, self._app._cmp_gear),
            ('RPM', C_RPM, self._app._cmp_rpm),
            ('STEERING', C_STEER, self._app._cmp_steer),
        ]:
            graphs_vbox.addWidget(_channel_header(color, title))
            graphs_vbox.addWidget(graph)

        # Delta graph (full-width, below all channel graphs)
        graphs_vbox.addWidget(_channel_header(C_DELTA, 'TIME DELTA', 's'))
        self._app._cmp_delta_graph = ComparisonDeltaGraph()
        graphs_vbox.addWidget(self._app._cmp_delta_graph)

        graphs_scroll = QScrollArea()
        graphs_scroll.setWidgetResizable(True)
        graphs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        graphs_scroll.setWidget(graphs_card)
        graphs_scroll.setStyleSheet(f'background: {BG}; border: none;')
        outer.addWidget(graphs_scroll, stretch=1)

    def update_tick(self, data: dict | None) -> None:
        # Comparison graphs are updated via _refresh_comparison() (user-triggered),
        # not on every telemetry tick. Nothing to do here.
        pass
