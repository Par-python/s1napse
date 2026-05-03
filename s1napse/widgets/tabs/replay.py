"""Replay tab — playback controls + telemetry graphs + mini dashboard.

Roomy bucket (dense=False). Layout:
  - Top strip : lap selector + import/load + play/pause + speed (Card, dense=True)
  - Middle    : sector scrubber + horizontal splitter
                  left  → mini dashboard (sector, speed, gear, RPM, steering, pedals, ABS/TC)
                  right → track map + sector times
  - Bottom    : scrollable telemetry graphs (speed, T/B, steer, RPM, gear)

All ``self._rpl_*``, ``self._replay_*`` widget attributes are mirrored onto
``self._app`` so that the legacy replay timer / scrub handlers in app.py keep
working without modification.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QPushButton, QComboBox, QScrollArea, QSplitter,
)

from ...constants import (
    C_SPEED, C_THROTTLE, C_BRAKE, C_RPM, C_GEAR, C_STEER, C_DELTA,
    mono, sans,
)
from ...theme import (
    BG, SURFACE_RAISED, SURFACE_HOVER, BORDER_SUBTLE, BORDER_STRONG,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
)
from ...utils import h_line, _channel_header
from ..graphs import ReplayGraph, ReplayMultiGraph
from ..primitives import Card
from ..track_map import TrackMapWidget
from ..gauges import RevBar, PedalBar, SteeringWidget
from ..badges import AidBadge
from ..panels import SectorScrubWidget

# Legacy shorthand aliases (mirrors app.py module-level block)
BG2     = SURFACE_RAISED
BG3     = SURFACE_HOVER
BORDER  = BORDER_SUBTLE
BORDER2 = BORDER_STRONG
TXT     = TEXT_SECONDARY
TXT2    = TEXT_MUTED
WHITE   = TEXT_PRIMARY


class ReplayTab(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        _btn_style = (
            f'QPushButton {{ background: {BG3}; color: {TXT2}; border: 1px solid {BORDER2};'
            f' border-radius: 4px; padding: 6px 12px; font-size: 10px; letter-spacing: 1px; }}'
            f'QPushButton:hover {{ color: {C_SPEED}; border-color: {C_SPEED}; }}'
        )

        # ── Top controls bar ──────────────────────────────────────────
        ctrl_card = QFrame()
        ctrl_card.setStyleSheet(
            f'background: {BG2}; border: 1px solid {BORDER}; border-radius: 6px;')
        ctrl_row = QHBoxLayout(ctrl_card)
        ctrl_row.setContentsMargins(14, 8, 14, 8)
        ctrl_row.setSpacing(10)

        def _lbl(text):
            l = QLabel(text)
            l.setFont(sans(8, bold=True))
            l.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
            return l

        ctrl_row.addWidget(_lbl('LAP'))
        self._replay_combo = QComboBox()
        self._replay_combo.setStyleSheet(
            f'background: {BG3}; color: {TXT}; border: 1px solid {BORDER2};'
            f' border-radius: 4px; padding: 4px 8px;')
        self._replay_combo.setMinimumWidth(200)
        ctrl_row.addWidget(self._replay_combo)

        import_btn = QPushButton('IMPORT LAP')
        import_btn.setFont(sans(8, bold=True))
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setStyleSheet(_btn_style)
        import_btn.clicked.connect(self._app._import_replay_lap_json)
        ctrl_row.addWidget(import_btn)

        load_btn = QPushButton('LOAD')
        load_btn.setFont(sans(8, bold=True))
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.setStyleSheet(
            f'QPushButton {{ background: {BG3}; color: {C_SPEED}; border: 1px solid {C_SPEED};'
            f' border-radius: 4px; padding: 6px 18px; font-size: 10px; letter-spacing: 1px; }}'
            f'QPushButton:hover {{ background: #0a2030; }}'
        )
        load_btn.clicked.connect(
            lambda: self._app._load_replay_lap(self._replay_combo.currentIndex()))
        ctrl_row.addWidget(load_btn)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet(f'color: {BORDER2};')
        ctrl_row.addWidget(sep1)

        self._replay_play_btn = QPushButton('PLAY')
        self._replay_play_btn.setFont(sans(9, bold=True))
        self._replay_play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._replay_play_btn.setFixedWidth(72)
        self._replay_play_btn.setStyleSheet(
            f'QPushButton {{ background: {BG3}; color: {C_THROTTLE}; border: 1px solid {C_THROTTLE};'
            f' border-radius: 4px; padding: 6px; letter-spacing: 1px; }}'
            f'QPushButton:hover {{ background: #0a2018; }}'
        )
        self._replay_play_btn.clicked.connect(self._app._toggle_replay_playback)
        ctrl_row.addWidget(self._replay_play_btn)

        ctrl_row.addWidget(_lbl('SPEED'))
        self._replay_speed_combo = QComboBox()
        self._replay_speed_combo.addItems(['0.25x', '0.5x', '1x', '2x', '5x', '10x'])
        self._replay_speed_combo.setCurrentIndex(2)
        self._replay_speed_combo.setFixedWidth(70)
        self._replay_speed_combo.setStyleSheet(
            f'background: {BG3}; color: {TXT}; border: 1px solid {BORDER2};'
            f' border-radius: 4px; padding: 4px 6px;')
        self._replay_speed_combo.currentTextChanged.connect(self._app._on_replay_speed_changed)
        ctrl_row.addWidget(self._replay_speed_combo)

        ctrl_row.addStretch()

        self._rpl_time_lbl = QLabel('—:——.——— / —:——.———')
        self._rpl_time_lbl.setFont(mono(10, bold=True))
        self._rpl_time_lbl.setStyleSheet(f'color: {C_SPEED};')
        ctrl_row.addWidget(self._rpl_time_lbl)

        outer.addWidget(ctrl_card)

        # ── Sector scrubber ───────────────────────────────────────────
        self._replay_scrub = SectorScrubWidget()
        self._replay_scrub.valueChanged.connect(self._app._replay_scrubber_moved)
        outer.addWidget(self._replay_scrub)

        # ── Main content (left dashboard + right track map) ───────────
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setHandleWidth(4)
        content_splitter.setStyleSheet(f'QSplitter::handle {{ background: {BORDER2}; }}')

        # ── Left: mini dashboard ──────────────────────────────────────
        left_panel = QFrame()
        left_panel.setStyleSheet(
            f'background: {BG2}; border: 1px solid {BORDER}; border-radius: 6px;')
        left_panel.setMinimumWidth(270)
        left_panel.setMaximumWidth(370)
        ll = QVBoxLayout(left_panel)
        ll.setContentsMargins(12, 10, 12, 10)
        ll.setSpacing(6)

        # ── Sector badge ──────────────────────────────
        sec_row = QHBoxLayout()
        sec_hdr = QLabel('SECTOR')
        sec_hdr.setFont(sans(7, bold=True))
        sec_hdr.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        sec_row.addWidget(sec_hdr)
        sec_row.addStretch()
        self._rpl_sector_lbl = QLabel('—')
        self._rpl_sector_lbl.setFont(mono(12, bold=True))
        self._rpl_sector_lbl.setStyleSheet(f'color: {TXT2};')
        sec_row.addWidget(self._rpl_sector_lbl)
        ll.addLayout(sec_row)
        ll.addWidget(h_line())

        # ── Two-column body: info (left) | pedals + aids (right) ──────
        body_row = QHBoxLayout()
        body_row.setSpacing(10)

        # Info column
        info_col = QVBoxLayout()
        info_col.setSpacing(4)

        # Speed + Gear on same row
        sg_row = QHBoxLayout()
        sg_row.setSpacing(14)

        speed_col = QVBoxLayout()
        speed_col.setSpacing(0)
        spd_hdr = QLabel('SPEED')
        spd_hdr.setFont(sans(7, bold=True))
        spd_hdr.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        self._rpl_speed_lbl = QLabel('0')
        self._rpl_speed_lbl.setFont(mono(22, bold=True))
        self._rpl_speed_lbl.setStyleSheet(f'color: {C_SPEED};')
        spd_unit = QLabel('km/h')
        spd_unit.setFont(sans(7))
        spd_unit.setStyleSheet(f'color: {TXT2};')
        speed_col.addWidget(spd_hdr)
        speed_col.addWidget(self._rpl_speed_lbl)
        speed_col.addWidget(spd_unit)
        sg_row.addLayout(speed_col)

        gear_col = QVBoxLayout()
        gear_col.setSpacing(0)
        gear_hdr = QLabel('GEAR')
        gear_hdr.setFont(sans(7, bold=True))
        gear_hdr.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        self._rpl_gear_lbl = QLabel('—')
        self._rpl_gear_lbl.setFont(mono(22, bold=True))
        self._rpl_gear_lbl.setStyleSheet(f'color: {C_GEAR};')
        gear_col.addWidget(gear_hdr)
        gear_col.addWidget(self._rpl_gear_lbl)
        sg_row.addLayout(gear_col)
        sg_row.addStretch()
        info_col.addLayout(sg_row)

        # RPM: label + value on one row, then bar
        rpm_row = QHBoxLayout()
        rpm_lbl_hdr = QLabel('RPM')
        rpm_lbl_hdr.setFont(sans(7, bold=True))
        rpm_lbl_hdr.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        self._rpl_rpm_lbl = QLabel('0')
        self._rpl_rpm_lbl.setFont(mono(8))
        self._rpl_rpm_lbl.setStyleSheet(f'color: {C_RPM};')
        rpm_row.addWidget(rpm_lbl_hdr)
        rpm_row.addWidget(self._rpl_rpm_lbl)
        rpm_row.addStretch()
        info_col.addLayout(rpm_row)
        self._rpl_rev_bar = RevBar()
        info_col.addWidget(self._rpl_rev_bar)

        # Steering
        steer_hdr = QLabel('STEERING')
        steer_hdr.setFont(sans(7, bold=True))
        steer_hdr.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        info_col.addWidget(steer_hdr)
        self._rpl_steer = SteeringWidget()
        self._rpl_steer.setMinimumHeight(80)
        self._rpl_steer.setMaximumHeight(120)
        info_col.addWidget(self._rpl_steer, stretch=1)

        body_row.addLayout(info_col, stretch=1)

        # Pedals + ABS/TC column (right side)
        side_col = QVBoxLayout()
        side_col.setSpacing(4)

        ped_hdr = QLabel('T / B')
        ped_hdr.setFont(sans(7, bold=True))
        ped_hdr.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        side_col.addWidget(ped_hdr)

        ped_row = QHBoxLayout()
        ped_row.setSpacing(4)
        self._rpl_throttle_bar = PedalBar(C_THROTTLE, 'T')
        self._rpl_brake_bar    = PedalBar(C_BRAKE,    'B')
        ped_row.addWidget(self._rpl_throttle_bar)
        ped_row.addWidget(self._rpl_brake_bar)
        side_col.addLayout(ped_row, stretch=1)

        side_col.addSpacing(6)
        self._rpl_abs_badge = AidBadge('ABS')
        self._rpl_tc_badge  = AidBadge('TC')
        side_col.addWidget(self._rpl_abs_badge)
        side_col.addWidget(self._rpl_tc_badge)

        body_row.addLayout(side_col)
        ll.addLayout(body_row, stretch=1)

        content_splitter.addWidget(left_panel)

        # ── Right: track map ──────────────────────────────────────────
        right_panel = QFrame()
        right_panel.setStyleSheet(
            f'background: {BG2}; border: 1px solid {BORDER}; border-radius: 6px;')
        rl = QVBoxLayout(right_panel)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.setSpacing(4)

        map_hdr_row = QHBoxLayout()
        map_title = QLabel('TRACK POSITION')
        map_title.setFont(sans(7, bold=True))
        map_title.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        map_hdr_row.addWidget(map_title)
        map_hdr_row.addStretch()

        self._rpl_s1_lbl = QLabel('S1: —')
        self._rpl_s2_lbl = QLabel('S2: —')
        self._rpl_s3_lbl = QLabel('S3: —')
        for i, lbl in enumerate((self._rpl_s1_lbl, self._rpl_s2_lbl, self._rpl_s3_lbl)):
            colors = [C_DELTA, C_STEER, C_RPM]
            lbl.setFont(mono(8, bold=True))
            lbl.setStyleSheet(f'color: {colors[i]};')
            map_hdr_row.addWidget(lbl)
            map_hdr_row.addSpacing(8)

        rl.addLayout(map_hdr_row)

        self._rpl_map = TrackMapWidget()
        self._rpl_map.setMinimumSize(180, 150)
        rl.addWidget(self._rpl_map, stretch=1)

        content_splitter.addWidget(right_panel)
        content_splitter.setSizes([310, 500])

        outer.addWidget(content_splitter, stretch=1)

        # ── Bottom: scrollable telemetry graphs ───────────────────────
        graphs_container = QWidget()
        graphs_container.setStyleSheet(f'background: {BG};')
        gv = QVBoxLayout(graphs_container)
        gv.setContentsMargins(4, 4, 4, 8)
        gv.setSpacing(4)

        self._rpl_speed_graph   = ReplayGraph('Speed km/h', C_SPEED, ylim=(0, 320))
        self._rpl_thr_brk_graph = ReplayMultiGraph(
            'T/B %', C_THROTTLE, C_BRAKE, 'Throttle', 'Brake', ylim=(0, 100))
        self._rpl_steer_graph   = ReplayGraph('Steer °', C_STEER, ylim=(-540, 540))
        self._rpl_rpm_graph     = ReplayGraph('RPM', C_RPM, ylim=(0, 10000))
        self._rpl_gear_graph    = ReplayGraph('Gear', C_GEAR, ylim=(-1, 8))

        self._replay_graphs = [
            self._rpl_speed_graph, self._rpl_thr_brk_graph,
            self._rpl_steer_graph, self._rpl_rpm_graph, self._rpl_gear_graph,
        ]

        for title, color, graph in [
            ('SPEED',            C_SPEED,    self._rpl_speed_graph),
            ('THROTTLE / BRAKE', C_THROTTLE, self._rpl_thr_brk_graph),
            ('STEERING',        C_STEER,    self._rpl_steer_graph),
            ('RPM',             C_RPM,      self._rpl_rpm_graph),
            ('GEAR',            C_GEAR,     self._rpl_gear_graph),
        ]:
            gv.addWidget(_channel_header(color, title))
            gv.addWidget(graph)

        graphs_scroll = QScrollArea()
        graphs_scroll.setWidgetResizable(True)
        graphs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        graphs_scroll.setWidget(graphs_container)
        graphs_scroll.setStyleSheet(
            f'QScrollArea {{ border: none; background: transparent; }}')
        graphs_scroll.setFixedHeight(240)

        outer.addWidget(graphs_scroll)

        # ── Mirror all widget attrs onto app so legacy handlers keep working ──
        self._mirror_to_app()

    def _mirror_to_app(self) -> None:
        """Assign all Qt widget attrs that legacy app.py code references."""
        app = self._app
        # Controls
        app._replay_combo       = self._replay_combo
        app._replay_play_btn    = self._replay_play_btn
        app._replay_speed_combo = self._replay_speed_combo
        app._rpl_time_lbl       = self._rpl_time_lbl
        app._replay_scrub       = self._replay_scrub
        # Mini-dashboard labels
        app._rpl_sector_lbl    = self._rpl_sector_lbl
        app._rpl_speed_lbl     = self._rpl_speed_lbl
        app._rpl_gear_lbl      = self._rpl_gear_lbl
        app._rpl_rpm_lbl       = self._rpl_rpm_lbl
        app._rpl_rev_bar       = self._rpl_rev_bar
        app._rpl_steer         = self._rpl_steer
        app._rpl_throttle_bar  = self._rpl_throttle_bar
        app._rpl_brake_bar     = self._rpl_brake_bar
        app._rpl_abs_badge     = self._rpl_abs_badge
        app._rpl_tc_badge      = self._rpl_tc_badge
        # Track map + sector labels
        app._rpl_map    = self._rpl_map
        app._rpl_s1_lbl = self._rpl_s1_lbl
        app._rpl_s2_lbl = self._rpl_s2_lbl
        app._rpl_s3_lbl = self._rpl_s3_lbl
        # Telemetry graphs
        app._rpl_speed_graph   = self._rpl_speed_graph
        app._rpl_thr_brk_graph = self._rpl_thr_brk_graph
        app._rpl_steer_graph   = self._rpl_steer_graph
        app._rpl_rpm_graph     = self._rpl_rpm_graph
        app._rpl_gear_graph    = self._rpl_gear_graph
        app._replay_graphs     = self._replay_graphs

    def update_tick(self, data: dict | None) -> None:
        # Replay updates are driven by the replay timer and scrub position,
        # not by live telemetry ticks — this is intentionally a no-op stub.
        pass
