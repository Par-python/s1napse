"""Lap Analysis tab — sectors, track map, telemetry graphs, delta.

Roomy bucket. Each major section gets its own Card with 16px padding
(dense=False, the default).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QCheckBox, QScrollArea,
)

from ... import theme
from ...constants import (
    C_SPEED, C_THROTTLE, C_BRAKE, C_RPM, C_GEAR, C_STEER,
    mono,
)
from ...theme import (
    BG, SURFACE_HOVER, BORDER_SUBTLE, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
)
from ...utils import h_line, _channel_header
from ..primitives import Card
from ..panels import SectorTimesPanel
from ..track_map import TrackMapWidget
from ..graphs import (
    AnalysisTelemetryGraph, AnalysisMultiLineGraph, TimeDeltaGraph,
)

# Aliases matching legacy app.py shorthand
BG3 = SURFACE_HOVER
BORDER = BORDER_SUBTLE
WHITE = TEXT_PRIMARY
TXT = TEXT_SECONDARY
TXT2 = TEXT_MUTED


class LapAnalysisTab(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        # ── Top: splitter holding sector panel / track map / graphs ──────
        splitter_card = Card(label='Lap Analysis', dense=False)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left column: sector times panel
        self.sector_panel = SectorTimesPanel()
        splitter.addWidget(self.sector_panel)

        # Centre column: track map + controls
        map_container = QWidget()
        map_container.setStyleSheet(f'background: {BG};')
        map_vbox = QVBoxLayout(map_container)
        map_vbox.setContentsMargins(0, 0, 0, 4)
        map_vbox.setSpacing(4)

        self.track_map = TrackMapWidget()
        self.track_map.setMinimumWidth(300)
        map_vbox.addWidget(self.track_map, stretch=1)

        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(8)

        self._track_lock_btn = QPushButton('LOCK SHAPE')
        self._track_lock_btn.setFont(mono(9, bold=True))
        self._track_lock_btn.setCheckable(True)
        self._track_lock_btn.setStyleSheet(
            f'QPushButton {{background:{BG3};color:{WHITE};border:1px solid {BORDER};'
            f'border-radius:4px;padding:4px 12px;}}'
            f'QPushButton:checked {{background:#b45309;color:#fff;border-color:#d97706;}}'
        )
        self._track_lock_btn.toggled.connect(app._on_track_lock_toggled)
        ctrl_row.addWidget(self._track_lock_btn)

        self._raceline_chk = QCheckBox('Raceline')
        self._raceline_chk.setFont(mono(9, bold=True))
        self._raceline_chk.setChecked(True)
        self._raceline_chk.setStyleSheet(
            f'QCheckBox {{color:{TXT};spacing:6px;}}'
            f'QCheckBox::indicator {{width:14px;height:14px;border:1px solid {BORDER};'
            f'border-radius:3px;background:{BG3};}}'
            f'QCheckBox::indicator:checked {{background:{C_THROTTLE};border-color:{C_THROTTLE};}}'
        )
        self._raceline_chk.toggled.connect(app._on_raceline_toggled)
        ctrl_row.addWidget(self._raceline_chk)
        ctrl_row.addStretch(1)
        map_vbox.addLayout(ctrl_row)
        splitter.addWidget(map_container)

        # Right column: telemetry graphs in a scroll area
        right_container = QWidget()
        right_container.setStyleSheet(f'background: {BG};')
        right_vbox = QVBoxLayout(right_container)
        right_vbox.setContentsMargins(4, 4, 4, 4)
        right_vbox.setSpacing(2)

        self.ana_speed = AnalysisTelemetryGraph('Speed km/h', color=C_SPEED, ylim=(0, 320))
        self.ana_throttle_brake = AnalysisMultiLineGraph(
            '%', 'Throttle', 'Brake', color1=C_THROTTLE, color2=C_BRAKE, ylim=(0, 100))
        self.ana_gear = AnalysisTelemetryGraph('Gear', color=C_GEAR, ylim=(-1, 8))
        self.ana_rpm = AnalysisTelemetryGraph('RPM', color=C_RPM, ylim=(0, 10000))
        self.ana_steer = AnalysisTelemetryGraph('Steer °', color=C_STEER, ylim=(-540, 540))

        for label, graph in [
            (('SPEED', C_SPEED, 'km/h'), self.ana_speed),
            (('THROTTLE & BRAKE', C_THROTTLE, '%'), self.ana_throttle_brake),
            (('GEAR', C_GEAR, ''), self.ana_gear),
            (('RPM', C_RPM, 'rpm'), self.ana_rpm),
            (('STEERING', C_STEER, '°'), self.ana_steer),
        ]:
            right_vbox.addWidget(_channel_header(label[1], label[0], label[2]))
            right_vbox.addWidget(graph)
            right_vbox.addWidget(h_line())

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setWidget(right_container)
        right_scroll.setMinimumWidth(300)
        splitter.addWidget(right_scroll)
        splitter.setSizes([220, 400, 420])

        splitter_card.body().addWidget(splitter)
        outer.addWidget(splitter_card, stretch=3)

        # ── Bottom: time delta graph ─────────────────────────────────────
        delta_card = Card(label='Time Delta', dense=False)
        self.time_delta_graph = TimeDeltaGraph()
        self.time_delta_graph.setMinimumHeight(130)
        delta_card.body().addWidget(self.time_delta_graph)

        # Sector marker strip inside the delta card
        sector_strip = QHBoxLayout()
        sector_strip.setSpacing(2)
        from PyQt6.QtWidgets import QLabel
        sector_colors = [C_SPEED, C_THROTTLE, C_RPM, C_STEER, C_BRAKE]
        for s, c in zip(['S1', 'S2', 'S3', 'S4', 'S5'], sector_colors):
            lbl = QLabel(s)
            lbl.setFont(mono(8, bold=True))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f'background: {BG3}; color: {c}; border: 1px solid {BORDER}; '
                f'padding: 2px 8px; border-radius: 2px;'
            )
            sector_strip.addWidget(lbl)
        sector_strip.addStretch()
        delta_card.body().addLayout(sector_strip)

        outer.addWidget(delta_card, stretch=1)

        # ── Mirror attributes onto app for legacy code paths ─────────────
        # These bridges let app.py methods (_on_track_lock_toggled,
        # _reset_analysis_graphs, track update handlers, etc.) keep
        # working via self.<attr> without any changes to app.py.
        # Task 27 will clean up these cross-cutting references.
        app.sector_panel = self.sector_panel
        app.track_map = self.track_map
        app._track_lock_btn = self._track_lock_btn
        app._raceline_chk = self._raceline_chk
        app.ana_speed = self.ana_speed
        app.ana_throttle_brake = self.ana_throttle_brake
        app.ana_gear = self.ana_gear
        app.ana_rpm = self.ana_rpm
        app.ana_steer = self.ana_steer
        app.time_delta_graph = self.time_delta_graph

    def update_tick(self, data: dict | None) -> None:
        # Per-tick updates are handled directly in app._render_telemetry via
        # the mirrored self.ana_*/self.sector_panel/self.time_delta_graph attrs.
        # This hook exists for completeness and future use.
        pass
