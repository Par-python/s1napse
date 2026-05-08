"""Main TelemetryApp window — orchestrates all tabs, timers, and data flow."""

import sys
import json
import gzip
import time
import math
import threading
from collections import deque
from pathlib import Path

import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QLineEdit, QSlider,
    QTabWidget, QFileDialog, QMessageBox, QSplitter, QScrollArea,
    QFrame, QGridLayout, QSizePolicy, QSpinBox, QDoubleSpinBox,
    QStackedWidget, QButtonGroup, QRadioButton, QCheckBox,
)
from PyQt6.QtCore import QTimer, Qt, QRectF, QPointF
from PyQt6.QtGui import (QFont, QPainter, QColor, QPen, QBrush, QFontMetrics,
                         QRadialGradient, QShortcut, QKeySequence)

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from .constants import (
    C_SPEED, C_THROTTLE, C_BRAKE, C_RPM, C_GEAR, C_STEER,
    C_ABS, C_TC, C_DELTA, C_PURPLE, C_PURPLE_BG, C_GREEN_BG, C_REF,
    N_TRACK_SEG, MONZA_LENGTH_M,
    mono, sans,
)
from . import theme
from .theme import (
    BG, SURFACE, SURFACE_RAISED, SURFACE_HOVER, BORDER_SUBTLE, BORDER_STRONG,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, TEXT_FAINT,
    ACCENT, GOOD, WARN, BAD, INFO,
    ui_font, mono_font, label_font,
)
from .utils import (
    _safe_list, h_line, _channel_header, _vsep,
    _interp_time_at_dist, _compute_sector_times,
)
from .readers import ACUDPReader, ACCReader, IRacingReader, ELM327Reader
from .track_recorder import TrackRecorder, TRACKS, TRACK_NAME_MAP, load_saved_tracks, _get_tracks_dir
from .widgets import (
    RevBar, PedalBar, ValueDisplay, SteeringWidget, SteeringBar,
    TyreCard, _lerp_color, _TYRE_TEMP_KP, TrackMapWidget,
    ChannelGraph, MultiChannelGraph,
    AnalysisTelemetryGraph, AnalysisMultiLineGraph,
    TimeDeltaGraph, ComparisonGraph, ComparisonDeltaGraph,
    RacePaceChart, ReplayGraph, ReplayMultiGraph,
    SectorTimesPanel, SectorScrubWidget, LapHistoryPanel,
    AidBadge, LiveTabBar,
)
from .widgets.title_bar import TitleBar
from .widgets.graphs import _style_ax
from .widgets.math_channel_panel import MathChannelPanel
from .widgets.tabs import RaceTab, TyresTab, DashboardTab, LapAnalysisTab, TelemetryTab, LapComparisonTab, SessionTab, ReplayTab
from .coaching.lap_coach import LapCoach
from .coaching.math_engine import MathEngine
from .coaching.strategy_engine import StrategyEngine


class TelemetrySampler(threading.Thread):
    """Background thread: reads shared memory at ~120 Hz, buffers raw dicts."""

    def __init__(self):
        super().__init__(daemon=True)
        self._lock = threading.Lock()
        self._buffer: list[dict] = []
        self._latest: dict | None = None
        self._reader = None
        self._running = True

    def set_reader(self, reader):
        self._reader = reader

    def run(self):
        while self._running:
            reader = self._reader
            if reader is not None:
                try:
                    data = reader.read()
                except Exception:
                    data = None
                if data is not None:
                    with self._lock:
                        self._buffer.append(data)
                        self._latest = data
            time.sleep(0.008)  # ~120 Hz

    def drain(self) -> list[dict]:
        with self._lock:
            buf = self._buffer
            self._buffer = []
            return buf

    @property
    def latest(self) -> dict | None:
        with self._lock:
            return self._latest

    def stop(self):
        self._running = False




class TelemetryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('s1napse')
        _screen = QApplication.primaryScreen().availableGeometry()
        _w = min(1640, _screen.width() - 40)
        _h = min(980, _screen.height() - 60)
        self.setGeometry(_screen.left() + 20, _screen.top() + 30, _w, _h)
        self.setMinimumSize(900, 600)

        self.ac_reader  = None
        self.acc_reader = ACCReader()
        self.ir_reader  = IRacingReader()
        self.elm_reader = None
        self.current_reader = None
        self.auto_detect = True
        self._app_mode = 'sim'  # 'sim' or 'real'

        self.last_lap_time = 0
        self.current_lap_count = 0

        self.session_laps = []
        self._reset_current_lap_data()

        # Fuel strategy tracking
        self._fuel_at_lap_start: float | None = None
        self._fuel_per_lap_history: list[float] = []

        # Outlap detection: True when car exits pit lane during current lap
        self._current_lap_had_pit_exit: bool = True   # first lap is always an outlap
        self._prev_is_in_pit_lane: bool = True

        # Validity latch: once False this lap it stays False until next lap starts
        self._current_lap_valid: bool = True

        # Tyre stint age (laps on current set, reset at each pit exit)
        self._tyre_stint_laps: int = 0

        # Race strategy state
        self._last_known_fuel: float = 0.0
        self._last_gap_ahead: int = 0   # ms
        self._last_gap_behind: int = 0  # ms

        # Track selection (None = auto-detect from telemetry data)
        self._active_track_key: str | None = None
        self._auto_track = True

        # Last-known session metadata (updated every tick, saved with each lap)
        self._last_car_name: str = ''
        self._last_track_name: str = ''
        self._last_session_type: str = ''
        self._last_tyre_compound: str = ''
        self._last_air_temp: float = 0.0
        self._last_road_temp: float = 0.0

        # Cached telemetry data — written by fast sampler, read by render timer
        self._last_data: dict | None = None

        # Track recorder
        self.recorder = TrackRecorder()

        # Coaching engine
        self._lap_coach = LapCoach()

        # Math channel engine
        self._math_engine = MathEngine()

        # Strategy engine (live race-strategy state)
        self._strategy_engine = StrategyEngine()

        # Reference lap for delta / sector comparison (last completed lap)
        self._ref_lap_dists: list[float] = []
        self._ref_lap_times: list[float] = []
        self._ref_lap_time_s: float = 0.0
        self._current_deltas: list[float] = []

        # Replay tab state
        self._replay_data: dict | None = None
        self._replay_pos_ms: int = 0
        self._replay_playing: bool = False
        self._replay_speed: float = 1.0
        self._replay_total_ms: int = 0
        self._replay_sector_ms: list = []  # [(label, time_ms), ...]

        self._init_ui()

        # Background sampler thread — ~50 Hz shared memory reads
        self._sampler = TelemetrySampler()
        self._sampler.start()
        self._empty_drain_count = 0

        # Attempt initial detection immediately
        if self.auto_detect:
            detected = self._detect_game()
            if detected:
                self.current_reader = detected
                self._sampler.set_reader(detected)

        # UI render timer — ~5 Hz (200 ms), all widget updates
        self._render_timer = QTimer()
        self._render_timer.timeout.connect(self._render_telemetry)
        self._render_timer.start(200)

        # 60 fps animation timer — smooth lerp for car dot + steering
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._anim_tick)
        self._anim_timer.start(16)

        # Replay uses wall-clock deltas via _anim_tick (no separate timer)
        self._replay_last_mono: float = 0.0

        # Real racing update timer (started when OBD connects)
        self._real_timer = QTimer()
        self._real_timer.timeout.connect(self._update_real_telemetry)
        self._real_lap_count = 0
        self._real_lap_start = time.monotonic()

    # ------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------

    def _init_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Stacked widget: page 0 = welcome, page 1 = main app
        self._stack = QStackedWidget()
        root_layout.addWidget(self._stack)

        # --- Page 0: Welcome screen ---
        self._stack.addWidget(self._build_welcome_screen())

        # --- Page 1: Main telemetry app ---
        main_page = QWidget()
        main_layout = QVBoxLayout(main_page)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = TitleBar()
        main_layout.addWidget(self.title_bar)

        controls = self._build_connection_strip_controls()
        for w in controls:
            self.title_bar.addTrailing(w)

        self.tabs = QTabWidget()
        self.tabs.setTabBar(LiveTabBar(self.tabs))
        main_layout.addWidget(self.tabs)

        # The merged Race tab owns the Strategy data (pit window, deg, rivals,
        # fuel-save / undercut calculators). The legacy Strategy tab is gone;
        # `self.strategy_tab` aliases the Race tab so existing back-end calls
        # (e.g. self.strategy_tab._fs_laps_spin.value()) keep working.
        self.dashboard_tab = DashboardTab(self)
        self.tabs.addTab(self.dashboard_tab, 'DASHBOARD')
        self.telemetry_tab = TelemetryTab(self)
        self.tabs.addTab(self.telemetry_tab, 'TELEMETRY GRAPHS')
        self.lap_analysis_tab = LapAnalysisTab(self)
        self.tabs.addTab(self.lap_analysis_tab, 'LAP ANALYSIS')
        self.race_tab = RaceTab(self)
        self.strategy_tab = self.race_tab  # alias for legacy back-end handlers
        self.race_tab._fs_laps_spin.valueChanged.connect(self._update_fuel_save)
        self.race_tab._uco_pit_loss_spin.valueChanged.connect(self._update_undercut)
        self.race_tab._uco_pace_delta_spin.valueChanged.connect(self._update_undercut)
        self.tabs.addTab(self.race_tab, 'RACE')
        self.tyres_tab = TyresTab(self)
        self.tabs.addTab(self.tyres_tab, 'TYRES')
        self.comparison_tab = LapComparisonTab(self)
        self.tabs.addTab(self.comparison_tab, 'LAP COMPARISON')
        self.session_tab = SessionTab(self)
        self.tabs.addTab(self.session_tab, 'SESSION')
        self.replay_tab = ReplayTab(self)
        self.tabs.addTab(self.replay_tab, 'REPLAY')

        # Math channel panel (side panel on graphs tab, initialized after UI)
        self._math_panel = MathChannelPanel(self._math_engine)
        self._math_panel.hide()
        self._math_panel.initialize()
        self._math_panel.start()
        self._math_panel.channels_changed.connect(self._sync_math_graphs)
        self._math_panel.visibility_changed.connect(
            lambda _n, _v: self._sync_math_graphs())
        self._sync_math_graphs()

        self._stack.addWidget(main_page)

        # --- Page 2: OBD-II connection setup ---
        self._stack.addWidget(self._build_obd_setup_page())

        # --- Page 3: Real racing dashboard ---
        self._stack.addWidget(self._build_real_racing_page())

        self._stack.setCurrentIndex(0)

        self._set_graph_title_suffix('Lap 1')

    # ------------------------------------------------------------------
    # WELCOME SCREEN
    # ------------------------------------------------------------------

    def _build_welcome_screen(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f'background: {BG};')
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        # Centred content wrapper
        outer.addStretch(3)

        # Title: s1napse
        title = QLabel('s1napse')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(sans(48, bold=True))
        title.setStyleSheet(f'color: {TEXT_PRIMARY}; background: transparent; letter-spacing: 6px;')
        outer.addWidget(title)

        # Accent line under title
        line_w = QWidget()
        line_w.setFixedSize(60, 3)
        line_w.setStyleSheet(f'background: {C_SPEED}; border-radius: 1px;')
        line_container = QHBoxLayout()
        line_container.setContentsMargins(0, 8, 0, 0)
        line_container.addStretch()
        line_container.addWidget(line_w)
        line_container.addStretch()
        lc_widget = QWidget()
        lc_widget.setLayout(line_container)
        lc_widget.setStyleSheet('background: transparent;')
        outer.addWidget(lc_widget)

        outer.addSpacing(40)

        # Mode selection cards
        cards_row = QHBoxLayout()
        cards_row.setContentsMargins(0, 0, 0, 0)
        cards_row.setSpacing(24)
        cards_row.addStretch()

        self._mode_group = QButtonGroup(page)
        self._mode_group.setExclusive(True)

        # --- Sim Racing card ---
        sim_card, sim_radio = self._make_mode_card(
            'SIM RACING',
            'ACC, iRacing, Assetto Corsa\nReal-time telemetry from simulators',
            checked=True,
        )
        self._mode_group.addButton(sim_radio, 0)
        cards_row.addWidget(sim_card)

        # --- Real Racing card ---
        real_card, real_radio = self._make_mode_card(
            'REAL RACING',
            'On-track data acquisition\nELM327 OBD-II adapter',
        )
        self._mode_group.addButton(real_radio, 1)
        cards_row.addWidget(real_card)

        cards_row.addStretch()
        cards_container = QWidget()
        cards_container.setLayout(cards_row)
        cards_container.setStyleSheet('background: transparent;')
        outer.addWidget(cards_container)

        outer.addSpacing(36)

        # Next button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        next_btn = QPushButton('NEXT')
        next_btn.setFont(sans(11, bold=True))
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.setFixedSize(160, 44)
        next_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_SPEED};
                color: {BG};
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 2px;
            }}
            QPushButton:hover {{
                background: #33e0ff;
            }}
            QPushButton:pressed {{
                background: #00a8cc;
            }}
        """)
        next_btn.clicked.connect(self._on_welcome_next)
        btn_row.addWidget(next_btn)
        btn_row.addStretch()
        btn_widget = QWidget()
        btn_widget.setLayout(btn_row)
        btn_widget.setStyleSheet('background: transparent;')
        outer.addWidget(btn_widget)

        outer.addStretch(2)

        # Description at the bottom
        desc = QLabel('Real-time telemetry analysis and lap replay')
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setFont(sans(10))
        desc.setStyleSheet(f'color: {TEXT_MUTED}; background: transparent; padding-bottom: 24px;')
        outer.addWidget(desc)

        return page

    def _make_mode_card(self, title: str, subtitle: str,
                        checked: bool = False, enabled: bool = True):
        """Build a selectable mode card with a radio button. Returns (card_widget, radio)."""
        card = QWidget()
        card.setFixedSize(240, 150)
        card.setEnabled(enabled)

        border_col = BORDER_STRONG if enabled else '#1a1a1a'
        text_col = TEXT_SECONDARY if enabled else TEXT_MUTED
        sub_col = TEXT_MUTED if enabled else '#3a3a3a'

        card.setStyleSheet(f"""
            QWidget {{
                background: {SURFACE_RAISED};
                border: 1px solid {border_col};
                border-radius: 10px;
            }}
            QWidget:hover {{
                border-color: {C_SPEED if enabled else border_col};
            }}
        """)

        vl = QVBoxLayout(card)
        vl.setContentsMargins(20, 18, 20, 18)
        vl.setSpacing(8)

        radio = QRadioButton()
        radio.setChecked(checked)
        radio.setEnabled(enabled)
        radio.setStyleSheet(f"""
            QRadioButton {{
                background: transparent;
                border: none;
                color: {text_col};
                spacing: 6px;
            }}
            QRadioButton::indicator {{
                width: 14px; height: 14px;
                border-radius: 7px;
                border: 2px solid {BORDER_STRONG if enabled else '#1a1a1a'};
                background: {SURFACE_HOVER};
            }}
            QRadioButton::indicator:checked {{
                background: {C_SPEED};
                border-color: {C_SPEED};
            }}
        """)
        vl.addWidget(radio)

        lbl = QLabel(title)
        lbl.setFont(sans(14, bold=True))
        lbl.setStyleSheet(f'color: {text_col}; background: transparent; border: none;'
                          f' letter-spacing: 1.5px;')
        vl.addWidget(lbl)

        sub = QLabel(subtitle)
        sub.setFont(sans(9))
        sub.setWordWrap(True)
        sub.setStyleSheet(f'color: {sub_col}; background: transparent; border: none;')
        vl.addWidget(sub)

        vl.addStretch()

        if not enabled:
            tag = QLabel('COMING SOON')
            tag.setFont(sans(7, bold=True))
            tag.setAlignment(Qt.AlignmentFlag.AlignRight)
            tag.setStyleSheet(f'color: {TEXT_MUTED}; background: transparent; border: none;'
                              f' letter-spacing: 1px;')
            vl.addWidget(tag)

        return card, radio

    def _on_welcome_next(self):
        mode_id = self._mode_group.checkedId()
        if mode_id == 1:
            # Real racing — OBD setup page
            self._app_mode = 'real'
            self._stack.setCurrentIndex(2)
            return
        # Sim racing — show main app
        self._app_mode = 'sim'
        self._stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    # OBD-II SETUP PAGE
    # ------------------------------------------------------------------

    def _build_obd_setup_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f'background: {BG};')
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(2)

        # Title
        title = QLabel('ELM327 OBD-II SETUP')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(sans(28, bold=True))
        title.setStyleSheet(f'color: {TEXT_PRIMARY}; background: transparent; letter-spacing: 4px;')
        outer.addWidget(title)

        # Accent line
        line_w = QWidget()
        line_w.setFixedSize(60, 3)
        line_w.setStyleSheet(f'background: {C_SPEED}; border-radius: 1px;')
        lc = QHBoxLayout()
        lc.setContentsMargins(0, 8, 0, 0)
        lc.addStretch(); lc.addWidget(line_w); lc.addStretch()
        lc_w = QWidget(); lc_w.setLayout(lc)
        lc_w.setStyleSheet('background: transparent;')
        outer.addWidget(lc_w)

        outer.addSpacing(32)

        # --- Form container ---
        form = QWidget()
        form.setFixedWidth(400)
        form.setStyleSheet(f"""
            QWidget {{ background: {SURFACE_RAISED}; border: 1px solid {BORDER_STRONG}; border-radius: 10px; }}
        """)
        fl = QVBoxLayout(form)
        fl.setContentsMargins(28, 24, 28, 24)
        fl.setSpacing(14)

        # Connection type
        type_lbl = QLabel('CONNECTION TYPE')
        type_lbl.setFont(sans(8, bold=True))
        type_lbl.setStyleSheet(f'color: {TEXT_MUTED}; background: transparent; border: none;'
                               f' letter-spacing: 1px;')
        fl.addWidget(type_lbl)

        self._obd_type_combo = QComboBox()
        self._obd_type_combo.addItems(['WiFi', 'Bluetooth / Serial'])
        self._obd_type_combo.setStyleSheet(f"""
            QComboBox {{ background: {SURFACE_HOVER}; color: {TEXT_SECONDARY}; border: 1px solid {BORDER_STRONG};
                         border-radius: 4px; padding: 6px 10px; }}
        """)
        self._obd_type_combo.currentIndexChanged.connect(self._on_obd_type_changed)
        fl.addWidget(self._obd_type_combo)

        # WiFi fields
        self._obd_wifi_box = QWidget()
        self._obd_wifi_box.setStyleSheet('background: transparent; border: none;')
        wfl = QVBoxLayout(self._obd_wifi_box)
        wfl.setContentsMargins(0, 0, 0, 0)
        wfl.setSpacing(8)

        ip_lbl = QLabel('IP ADDRESS')
        ip_lbl.setFont(sans(8, bold=True))
        ip_lbl.setStyleSheet(f'color: {TEXT_MUTED}; background: transparent; border: none;'
                             f' letter-spacing: 1px;')
        wfl.addWidget(ip_lbl)
        self._obd_ip = QLineEdit('192.168.0.10')
        self._obd_ip.setStyleSheet(f"""
            QLineEdit {{ background: {SURFACE_HOVER}; color: {TEXT_SECONDARY}; border: 1px solid {BORDER_STRONG};
                         border-radius: 4px; padding: 6px 10px; }}
        """)
        wfl.addWidget(self._obd_ip)

        port_lbl = QLabel('PORT')
        port_lbl.setFont(sans(8, bold=True))
        port_lbl.setStyleSheet(f'color: {TEXT_MUTED}; background: transparent; border: none;'
                               f' letter-spacing: 1px;')
        wfl.addWidget(port_lbl)
        self._obd_port = QLineEdit('35000')
        self._obd_port.setStyleSheet(f"""
            QLineEdit {{ background: {SURFACE_HOVER}; color: {TEXT_SECONDARY}; border: 1px solid {BORDER_STRONG};
                         border-radius: 4px; padding: 6px 10px; }}
        """)
        wfl.addWidget(self._obd_port)
        fl.addWidget(self._obd_wifi_box)

        # Bluetooth fields (hidden by default)
        self._obd_bt_box = QWidget()
        self._obd_bt_box.setStyleSheet('background: transparent; border: none;')
        self._obd_bt_box.setVisible(False)
        bfl = QVBoxLayout(self._obd_bt_box)
        bfl.setContentsMargins(0, 0, 0, 0)
        bfl.setSpacing(8)

        serial_lbl = QLabel('SERIAL PORT')
        serial_lbl.setFont(sans(8, bold=True))
        serial_lbl.setStyleSheet(f'color: {TEXT_MUTED}; background: transparent; border: none;'
                                 f' letter-spacing: 1px;')
        bfl.addWidget(serial_lbl)
        import platform as _plat
        default_serial = 'COM3' if _plat.system() == 'Windows' else '/dev/rfcomm0'
        self._obd_serial = QLineEdit(default_serial)
        self._obd_serial.setStyleSheet(f"""
            QLineEdit {{ background: {SURFACE_HOVER}; color: {TEXT_SECONDARY}; border: 1px solid {BORDER_STRONG};
                         border-radius: 4px; padding: 6px 10px; }}
        """)
        bfl.addWidget(self._obd_serial)
        fl.addWidget(self._obd_bt_box)

        # Status label
        self._obd_status = QLabel('')
        self._obd_status.setFont(sans(9))
        self._obd_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._obd_status.setStyleSheet(f'color: {TEXT_MUTED}; background: transparent; border: none;')
        fl.addWidget(self._obd_status)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        back_btn = QPushButton('BACK')
        back_btn.setFont(sans(10, bold=True))
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedHeight(40)
        back_btn.setStyleSheet(f"""
            QPushButton {{ background: {SURFACE_HOVER}; color: {TEXT_SECONDARY}; border: 1px solid {BORDER_STRONG};
                           border-radius: 6px; letter-spacing: 1px; }}
            QPushButton:hover {{ background: #2d2d2d; border-color: #4a4a4a; }}
        """)
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        btn_row.addWidget(back_btn)

        connect_btn = QPushButton('CONNECT')
        connect_btn.setFont(sans(10, bold=True))
        connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        connect_btn.setFixedHeight(40)
        connect_btn.setStyleSheet(f"""
            QPushButton {{ background: {C_SPEED}; color: {BG}; border: none;
                           border-radius: 6px; font-weight: bold; letter-spacing: 2px; }}
            QPushButton:hover {{ background: #33e0ff; }}
            QPushButton:pressed {{ background: #00a8cc; }}
        """)
        connect_btn.clicked.connect(self._on_obd_connect)
        btn_row.addWidget(connect_btn)

        btn_w = QWidget()
        btn_w.setLayout(btn_row)
        btn_w.setStyleSheet('background: transparent; border: none;')
        fl.addWidget(btn_w)

        # Demo button — test without real adapter
        demo_btn = QPushButton('DEMO MODE (no adapter)')
        demo_btn.setFont(sans(9))
        demo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        demo_btn.setFixedHeight(32)
        demo_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_MUTED};
                           border: 1px solid {BORDER_STRONG}; border-radius: 4px;
                           letter-spacing: 0.5px; }}
            QPushButton:hover {{ color: {C_SPEED}; border-color: {C_SPEED}; }}
        """)
        demo_btn.clicked.connect(self._on_obd_demo)
        fl.addWidget(demo_btn)

        # Centre the form card
        form_row = QHBoxLayout()
        form_row.addStretch()
        form_row.addWidget(form)
        form_row.addStretch()
        form_w = QWidget()
        form_w.setLayout(form_row)
        form_w.setStyleSheet('background: transparent;')
        outer.addWidget(form_w)

        outer.addStretch(3)

        # Bottom hint
        hint = QLabel('Plug the ELM327 adapter into your OBD-II port and ensure it is powered on')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setFont(sans(9))
        hint.setStyleSheet(f'color: {TEXT_MUTED}; background: transparent; padding-bottom: 24px;')
        outer.addWidget(hint)

        return page

    def _on_obd_type_changed(self, idx: int):
        self._obd_wifi_box.setVisible(idx == 0)
        self._obd_bt_box.setVisible(idx == 1)

    def _on_obd_connect(self):
        if self._obd_type_combo.currentIndex() == 0:
            conn_str = f"{self._obd_ip.text().strip()}:{self._obd_port.text().strip()}"
        else:
            conn_str = self._obd_serial.text().strip()

        self._obd_status.setText('Connecting...')
        self._obd_status.setStyleSheet(f'color: {C_SPEED}; background: transparent; border: none;')
        QApplication.processEvents()

        self.elm_reader = ELM327Reader(conn_str)
        if self.elm_reader.connect():
            self.current_reader = self.elm_reader
            self.auto_detect = False
            self._obd_status.setText('Connected!')
            self._obd_status.setStyleSheet(f'color: {C_THROTTLE}; background: transparent;'
                                           f' border: none;')
            # Show manual lap button in connection strip
            if hasattr(self, '_manual_lap_btn'):
                self._manual_lap_btn.setVisible(True)
            # Enable lap keyboard shortcut
            if hasattr(self, '_lap_shortcut'):
                self._lap_shortcut.setEnabled(True)
            # Select ELM327 in game combo if available
            if hasattr(self, 'game_combo'):
                idx = self.game_combo.findText('ELM327 (OBD-II)')
                if idx >= 0:
                    self.game_combo.setCurrentIndex(idx)
            self._start_real_racing_ui()
            QTimer.singleShot(600, lambda: self._stack.setCurrentIndex(3))
        else:
            self._obd_status.setText('Connection failed — check adapter and settings.')
            self._obd_status.setStyleSheet(f'color: {C_BRAKE}; background: transparent;'
                                           f' border: none;')
            self.elm_reader = None

    def _on_obd_demo(self):
        """Start simulated OBD-II data — no adapter needed."""
        self._obd_status.setText('Starting demo...')
        self._obd_status.setStyleSheet(f'color: {C_SPEED}; background: transparent; border: none;')
        QApplication.processEvents()

        self.elm_reader = ELM327Reader(simulate=True)
        self.elm_reader.connect()
        self.current_reader = self.elm_reader
        self.auto_detect = False

        self._start_real_racing_ui()
        QTimer.singleShot(400, lambda: self._stack.setCurrentIndex(3))

    def _start_real_racing_ui(self):
        """Enable real-racing-specific UI elements and start the update timer."""
        if hasattr(self, '_manual_lap_btn'):
            self._manual_lap_btn.setVisible(True)
        if hasattr(self, '_lap_shortcut'):
            self._lap_shortcut.setEnabled(True)
        if not self._real_timer.isActive():
            self._real_timer.start(50)

    def _on_manual_lap(self):
        if self.elm_reader and self.elm_reader.is_connected():
            self.elm_reader.trigger_lap()

    # ------------------------------------------------------------------
    # REAL RACING PAGE
    # ------------------------------------------------------------------

    def _build_real_racing_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f'background: {BG};')
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────────
        top = QWidget()
        top.setFixedHeight(42)
        top.setStyleSheet(f'background: {SURFACE_RAISED}; border-bottom: 1px solid {BORDER_STRONG};')
        tl = QHBoxLayout(top)
        tl.setContentsMargins(16, 0, 16, 0)
        tl.setSpacing(14)

        self._real_dot = QLabel('\u25cf')
        self._real_dot.setFont(sans(10))
        self._real_dot.setStyleSheet(f'color: {C_THROTTLE};')
        tl.addWidget(self._real_dot)

        self._real_status = QLabel('OBD-II CONNECTED')
        self._real_status.setFont(sans(9, bold=True))
        self._real_status.setStyleSheet(f'color: {TEXT_PRIMARY}; letter-spacing: 1px;')
        tl.addWidget(self._real_status)

        tl.addWidget(_vsep())

        # Lap button in top bar
        real_lap_btn = QPushButton('LAP')
        real_lap_btn.setFixedSize(60, 26)
        real_lap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        real_lap_btn.setFont(sans(9, bold=True))
        real_lap_btn.setStyleSheet(
            f'QPushButton {{ background: #0a2218; color: {C_THROTTLE};'
            f' border: 1px solid {C_THROTTLE}; border-radius: 4px;'
            f' letter-spacing: 1px; }}'
            f'QPushButton:hover {{ background: #0f3322; }}'
            f'QPushButton:pressed {{ background: #061a10; }}'
        )
        real_lap_btn.setToolTip('Complete current lap (shortcut: L)')
        real_lap_btn.clicked.connect(self._on_manual_lap)
        tl.addWidget(real_lap_btn)

        tl.addStretch()

        # Lap info
        self._real_lap_lbl = QLabel('LAP 0')
        self._real_lap_lbl.setFont(sans(9, bold=True))
        self._real_lap_lbl.setStyleSheet(f'color: {TEXT_SECONDARY}; letter-spacing: 1px;')
        tl.addWidget(self._real_lap_lbl)

        tl.addWidget(_vsep())

        self._real_laptime_lbl = QLabel('0:00.000')
        self._real_laptime_lbl.setFont(mono(12, bold=True))
        self._real_laptime_lbl.setStyleSheet(f'color: {C_SPEED};')
        tl.addWidget(self._real_laptime_lbl)

        tl.addWidget(_vsep())

        self._real_last_lbl = QLabel('LAST  --:--.---')
        self._real_last_lbl.setFont(mono(10))
        self._real_last_lbl.setStyleSheet(f'color: {TEXT_MUTED};')
        tl.addWidget(self._real_last_lbl)

        tl.addWidget(_vsep())

        # Back to menu
        back_btn = QPushButton('MENU')
        back_btn.setFixedSize(60, 26)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFont(sans(8, bold=True))
        back_btn.setStyleSheet(
            f'QPushButton {{ background: {SURFACE_HOVER}; color: {TEXT_MUTED};'
            f' border: 1px solid {BORDER_STRONG}; border-radius: 4px; letter-spacing: 1px; }}'
            f'QPushButton:hover {{ color: {TEXT_SECONDARY}; border-color: #4a4a4a; }}'
        )
        back_btn.clicked.connect(self._on_real_back)
        tl.addWidget(back_btn)

        root.addWidget(top)

        # ── Main content ─────────────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet(f'background: {BG};')
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(14)

        # ── Row 1: Speed + RPM (big hero gauges) ────────────────────────
        hero_row = QHBoxLayout()
        hero_row.setSpacing(14)

        # Speed card
        speed_card = QFrame()
        speed_card.setStyleSheet(
            f'QFrame {{ background: {SURFACE_RAISED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; }}')
        sc_l = QVBoxLayout(speed_card)
        sc_l.setContentsMargins(24, 20, 24, 20)
        sc_l.setSpacing(4)
        sc_hdr = QLabel('SPEED')
        sc_hdr.setFont(sans(8, bold=True))
        sc_hdr.setStyleSheet(f'color: {TEXT_MUTED}; letter-spacing: 2px;')
        sc_l.addWidget(sc_hdr)
        self._real_speed = QLabel('0')
        self._real_speed.setFont(mono(52, bold=True))
        self._real_speed.setStyleSheet(f'color: {C_SPEED};')
        self._real_speed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sc_l.addWidget(self._real_speed)
        sc_unit = QLabel('km/h')
        sc_unit.setFont(sans(10))
        sc_unit.setStyleSheet(f'color: {TEXT_MUTED};')
        sc_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sc_l.addWidget(sc_unit)
        hero_row.addWidget(speed_card, 3)

        # RPM card
        rpm_card = QFrame()
        rpm_card.setStyleSheet(
            f'QFrame {{ background: {SURFACE_RAISED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; }}')
        rc_l = QVBoxLayout(rpm_card)
        rc_l.setContentsMargins(24, 20, 24, 20)
        rc_l.setSpacing(4)
        rc_hdr = QLabel('RPM')
        rc_hdr.setFont(sans(8, bold=True))
        rc_hdr.setStyleSheet(f'color: {TEXT_MUTED}; letter-spacing: 2px;')
        rc_l.addWidget(rc_hdr)
        self._real_rpm = QLabel('0')
        self._real_rpm.setFont(mono(52, bold=True))
        self._real_rpm.setStyleSheet(f'color: {C_RPM};')
        self._real_rpm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rc_l.addWidget(self._real_rpm)
        # RPM bar
        self._real_rev_bar = RevBar()
        self._real_rev_bar.setFixedHeight(36)
        rc_l.addWidget(self._real_rev_bar)
        hero_row.addWidget(rpm_card, 3)

        # Gear card
        gear_card = QFrame()
        gear_card.setStyleSheet(
            f'QFrame {{ background: {SURFACE_RAISED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; }}')
        gc_l = QVBoxLayout(gear_card)
        gc_l.setContentsMargins(16, 20, 16, 20)
        gc_l.setSpacing(4)
        gc_hdr = QLabel('GEAR')
        gc_hdr.setFont(sans(8, bold=True))
        gc_hdr.setStyleSheet(f'color: {TEXT_MUTED}; letter-spacing: 2px;')
        gc_hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gc_l.addWidget(gc_hdr)
        self._real_gear = QLabel('N')
        self._real_gear.setFont(mono(64, bold=True))
        self._real_gear.setStyleSheet(f'color: {TEXT_PRIMARY};')
        self._real_gear.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gc_l.addWidget(self._real_gear)
        gc_l.addStretch()
        hero_row.addWidget(gear_card, 1)

        cl.addLayout(hero_row, 4)

        # ── Row 2: Throttle + secondary gauges ──────────────────────────
        gauge_row = QHBoxLayout()
        gauge_row.setSpacing(14)

        # Throttle card
        thr_card = QFrame()
        thr_card.setStyleSheet(
            f'QFrame {{ background: {SURFACE_RAISED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; }}')
        tc_l = QVBoxLayout(thr_card)
        tc_l.setContentsMargins(20, 14, 20, 14)
        tc_l.setSpacing(6)
        tc_hdr = QLabel('THROTTLE')
        tc_hdr.setFont(sans(8, bold=True))
        tc_hdr.setStyleSheet(f'color: {TEXT_MUTED}; letter-spacing: 2px;')
        tc_l.addWidget(tc_hdr)
        self._real_throttle_val = QLabel('0%')
        self._real_throttle_val.setFont(mono(24, bold=True))
        self._real_throttle_val.setStyleSheet(f'color: {C_THROTTLE};')
        tc_l.addWidget(self._real_throttle_val)
        # Throttle progress bar
        self._real_throttle_bar = QWidget()
        self._real_throttle_bar.setFixedHeight(10)
        self._real_throttle_bar.setStyleSheet(
            f'background: {SURFACE_HOVER}; border-radius: 5px;')
        tc_l.addWidget(self._real_throttle_bar)
        self._real_thr_fill = QWidget(self._real_throttle_bar)
        self._real_thr_fill.setFixedHeight(10)
        self._real_thr_fill.setStyleSheet(
            f'background: {C_THROTTLE}; border-radius: 5px;')
        self._real_thr_fill.setFixedWidth(0)
        gauge_row.addWidget(thr_card, 2)

        # Fuel card
        fuel_card = QFrame()
        fuel_card.setStyleSheet(
            f'QFrame {{ background: {SURFACE_RAISED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; }}')
        fc_l = QVBoxLayout(fuel_card)
        fc_l.setContentsMargins(20, 14, 20, 14)
        fc_l.setSpacing(6)
        fc_hdr = QLabel('FUEL LEVEL')
        fc_hdr.setFont(sans(8, bold=True))
        fc_hdr.setStyleSheet(f'color: {TEXT_MUTED}; letter-spacing: 2px;')
        fc_l.addWidget(fc_hdr)
        self._real_fuel = QLabel('--%')
        self._real_fuel.setFont(mono(24, bold=True))
        self._real_fuel.setStyleSheet(f'color: {C_SPEED};')
        fc_l.addWidget(self._real_fuel)
        # Fuel bar
        self._real_fuel_bar = QWidget()
        self._real_fuel_bar.setFixedHeight(10)
        self._real_fuel_bar.setStyleSheet(
            f'background: {SURFACE_HOVER}; border-radius: 5px;')
        fc_l.addWidget(self._real_fuel_bar)
        self._real_fuel_fill = QWidget(self._real_fuel_bar)
        self._real_fuel_fill.setFixedHeight(10)
        self._real_fuel_fill.setStyleSheet(
            f'background: {C_SPEED}; border-radius: 5px;')
        self._real_fuel_fill.setFixedWidth(0)
        gauge_row.addWidget(fuel_card, 2)

        # Coolant temp card
        cool_card = QFrame()
        cool_card.setStyleSheet(
            f'QFrame {{ background: {SURFACE_RAISED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; }}')
        cc_l = QVBoxLayout(cool_card)
        cc_l.setContentsMargins(20, 14, 20, 14)
        cc_l.setSpacing(6)
        cc_hdr = QLabel('COOLANT TEMP')
        cc_hdr.setFont(sans(8, bold=True))
        cc_hdr.setStyleSheet(f'color: {TEXT_MUTED}; letter-spacing: 2px;')
        cc_l.addWidget(cc_hdr)
        self._real_coolant = QLabel('--\u00b0C')
        self._real_coolant.setFont(mono(24, bold=True))
        self._real_coolant.setStyleSheet(f'color: {C_BRAKE};')
        cc_l.addWidget(self._real_coolant)
        cc_l.addStretch()
        gauge_row.addWidget(cool_card, 1)

        # Intake temp card
        intake_card = QFrame()
        intake_card.setStyleSheet(
            f'QFrame {{ background: {SURFACE_RAISED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; }}')
        ic_l = QVBoxLayout(intake_card)
        ic_l.setContentsMargins(20, 14, 20, 14)
        ic_l.setSpacing(6)
        ic_hdr = QLabel('INTAKE TEMP')
        ic_hdr.setFont(sans(8, bold=True))
        ic_hdr.setStyleSheet(f'color: {TEXT_MUTED}; letter-spacing: 2px;')
        ic_l.addWidget(ic_hdr)
        self._real_intake = QLabel('--\u00b0C')
        self._real_intake.setFont(mono(24, bold=True))
        self._real_intake.setStyleSheet(f'color: {C_STEER};')
        ic_l.addWidget(self._real_intake)
        ic_l.addStretch()
        gauge_row.addWidget(intake_card, 1)

        cl.addLayout(gauge_row, 2)

        # ── Row 3: Live graphs (speed + throttle over time) ─────────────
        graph_row = QHBoxLayout()
        graph_row.setSpacing(14)

        # Speed history graph
        self._real_speed_history: list[float] = []
        self._real_speed_canvas = FigureCanvas(Figure(figsize=(5, 1.5), facecolor=SURFACE_RAISED))
        self._real_speed_ax = self._real_speed_canvas.figure.add_subplot(111)
        self._real_speed_ax.set_facecolor(SURFACE_RAISED)
        self._real_speed_ax.tick_params(colors=TEXT_MUTED, labelsize=7)
        self._real_speed_ax.spines['top'].set_visible(False)
        self._real_speed_ax.spines['right'].set_visible(False)
        self._real_speed_ax.spines['left'].set_color(BORDER_SUBTLE)
        self._real_speed_ax.spines['bottom'].set_color(BORDER_SUBTLE)
        self._real_speed_ax.set_ylabel('km/h', color=TEXT_MUTED, fontsize=7)
        self._real_speed_ax.set_title('SPEED', color=TEXT_MUTED, fontsize=8, pad=4)
        self._real_speed_canvas.figure.subplots_adjust(
            left=0.12, right=0.97, top=0.82, bottom=0.15)

        s_frame = QFrame()
        s_frame.setStyleSheet(
            f'QFrame {{ background: {SURFACE_RAISED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; }}')
        sfl = QVBoxLayout(s_frame)
        sfl.setContentsMargins(4, 4, 4, 4)
        sfl.addWidget(self._real_speed_canvas)
        graph_row.addWidget(s_frame)

        # Throttle history graph
        self._real_thr_history: list[float] = []
        self._real_thr_canvas = FigureCanvas(Figure(figsize=(5, 1.5), facecolor=SURFACE_RAISED))
        self._real_thr_ax = self._real_thr_canvas.figure.add_subplot(111)
        self._real_thr_ax.set_facecolor(SURFACE_RAISED)
        self._real_thr_ax.tick_params(colors=TEXT_MUTED, labelsize=7)
        self._real_thr_ax.spines['top'].set_visible(False)
        self._real_thr_ax.spines['right'].set_visible(False)
        self._real_thr_ax.spines['left'].set_color(BORDER_SUBTLE)
        self._real_thr_ax.spines['bottom'].set_color(BORDER_SUBTLE)
        self._real_thr_ax.set_ylabel('%', color=TEXT_MUTED, fontsize=7)
        self._real_thr_ax.set_title('THROTTLE', color=TEXT_MUTED, fontsize=8, pad=4)
        self._real_thr_canvas.figure.subplots_adjust(
            left=0.12, right=0.97, top=0.82, bottom=0.15)

        t_frame = QFrame()
        t_frame.setStyleSheet(
            f'QFrame {{ background: {SURFACE_RAISED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; }}')
        tfl = QVBoxLayout(t_frame)
        tfl.setContentsMargins(4, 4, 4, 4)
        tfl.addWidget(self._real_thr_canvas)
        graph_row.addWidget(t_frame)

        # RPM history graph
        self._real_rpm_history: list[float] = []
        self._real_rpm_canvas = FigureCanvas(Figure(figsize=(5, 1.5), facecolor=SURFACE_RAISED))
        self._real_rpm_ax = self._real_rpm_canvas.figure.add_subplot(111)
        self._real_rpm_ax.set_facecolor(SURFACE_RAISED)
        self._real_rpm_ax.tick_params(colors=TEXT_MUTED, labelsize=7)
        self._real_rpm_ax.spines['top'].set_visible(False)
        self._real_rpm_ax.spines['right'].set_visible(False)
        self._real_rpm_ax.spines['left'].set_color(BORDER_SUBTLE)
        self._real_rpm_ax.spines['bottom'].set_color(BORDER_SUBTLE)
        self._real_rpm_ax.set_ylabel('rpm', color=TEXT_MUTED, fontsize=7)
        self._real_rpm_ax.set_title('RPM', color=TEXT_MUTED, fontsize=8, pad=4)
        self._real_rpm_canvas.figure.subplots_adjust(
            left=0.12, right=0.97, top=0.82, bottom=0.15)

        r_frame = QFrame()
        r_frame.setStyleSheet(
            f'QFrame {{ background: {SURFACE_RAISED}; border: 1px solid {BORDER_SUBTLE}; border-radius: 8px; }}')
        rfl = QVBoxLayout(r_frame)
        rfl.setContentsMargins(4, 4, 4, 4)
        rfl.addWidget(self._real_rpm_canvas)
        graph_row.addWidget(r_frame)

        cl.addLayout(graph_row, 3)

        root.addWidget(content)
        return page

    def _on_real_back(self):
        """Return to welcome screen from real racing mode."""
        self._real_timer.stop()
        if self.elm_reader:
            self.elm_reader.disconnect()
            self.elm_reader = None
        self.current_reader = None
        self._stack.setCurrentIndex(0)

    def _update_title_bar(self) -> None:
        """Refresh the TitleBar with live source, track, temps, and lap info."""
        src_name = ''
        if self.current_reader is self.acc_reader: src_name = 'ACC'
        elif self.current_reader is self.ac_reader: src_name = 'AC'
        elif self.current_reader is self.ir_reader: src_name = 'iRacing'
        elif self.current_reader is self.elm_reader: src_name = 'OBD-II'
        track = self._last_track_name or ''
        air = f'{self._last_air_temp:.0f}°C' if self._last_air_temp else ''
        road = f'{self._last_road_temp:.0f}°C' if self._last_road_temp else ''
        parts = [p for p in (src_name, track, f'{air} / {road}' if air or road else '') if p]
        self.title_bar.setSource(' · '.join(parts), live=src_name != '')

        last_ms = int(self.last_lap_time)
        last_s = f'{last_ms//60000:01d}:{(last_ms//1000)%60:02d}.{last_ms%1000:03d}' if last_ms else '—'
        self.title_bar.setSession(
            lap=f'{self.current_lap_count} / —',
            stint='',
            last_lap=last_s,
        )

    def _update_tab_indicators(self) -> None:
        """Paint a live-dot on tabs that have active data."""
        bar = self.tabs.tabBar()
        if not hasattr(bar, 'setLive'):
            return
        race_live = self.current_reader is not None
        strategy_alert = bool(getattr(self.strategy_tab, 'has_alert', lambda: False)())
        for i in range(self.tabs.count()):
            title = self.tabs.tabText(i).upper()
            if title == 'RACE':
                bar.setLive(i, race_live)
            elif title == 'STRATEGY':
                bar.setLive(i, strategy_alert)

    def _update_real_telemetry(self):
        """Update the real racing dashboard from ELM327Reader data."""
        if not self.elm_reader or not self.elm_reader.is_connected():
            self._real_dot.setStyleSheet('color: #444;')
            self._real_status.setText('DISCONNECTED')
            return

        data = self.elm_reader.read()
        if data is None:
            return

        speed = data.get('speed', 0)
        rpm = data.get('rpm', 0)
        max_rpm = data.get('max_rpm', 7000)
        gear = data.get('gear', 1)
        throttle = data.get('throttle', 0)
        fuel = data.get('fuel', 0)
        coolant = data.get('road_temp', 0)
        intake = data.get('air_temp', 0)
        lap_count = data.get('lap_count', 0)
        current_time_ms = data.get('current_time', 0)
        last_lap_s = data.get('lap_time', 0)

        # Speed / RPM / Gear
        self._real_speed.setText(str(int(speed)))
        self._real_rpm.setText(str(int(rpm)))
        self._real_rev_bar.set_value(rpm, max_rpm)

        gear_map = {0: 'R', 1: 'N'}
        self._real_gear.setText(gear_map.get(gear, str(gear - 1)))

        # Throttle
        self._real_throttle_val.setText(f'{int(throttle)}%')
        bar_w = self._real_throttle_bar.width()
        self._real_thr_fill.setFixedWidth(max(0, int(bar_w * throttle / 100)))

        # Fuel
        self._real_fuel.setText(f'{fuel:.0f}%')
        fuel_w = self._real_fuel_bar.width()
        self._real_fuel_fill.setFixedWidth(max(0, int(fuel_w * fuel / 100)))

        # Temps
        self._real_coolant.setText(f'{coolant:.0f}\u00b0C')
        self._real_intake.setText(f'{intake:.0f}\u00b0C')

        # Lap info
        self._real_lap_lbl.setText(f'LAP {lap_count}')
        mins = current_time_ms // 60000
        secs = (current_time_ms % 60000) / 1000.0
        self._real_laptime_lbl.setText(f'{mins}:{secs:06.3f}')

        if last_lap_s > 0:
            lm = int(last_lap_s) // 60
            ls = last_lap_s - lm * 60
            self._real_last_lbl.setText(f'LAST  {lm}:{ls:06.3f}')

        # Live graphs — keep last 200 samples (~10 sec at 20Hz)
        max_hist = 200
        self._real_speed_history.append(speed)
        self._real_thr_history.append(throttle)
        self._real_rpm_history.append(rpm)
        if len(self._real_speed_history) > max_hist:
            self._real_speed_history = self._real_speed_history[-max_hist:]
        if len(self._real_thr_history) > max_hist:
            self._real_thr_history = self._real_thr_history[-max_hist:]
        if len(self._real_rpm_history) > max_hist:
            self._real_rpm_history = self._real_rpm_history[-max_hist:]

        # Redraw graphs every 4th tick (~5 Hz) to avoid perf issues
        if len(self._real_speed_history) % 4 == 0:
            for ax, hist, color in [
                (self._real_speed_ax, self._real_speed_history, C_SPEED),
                (self._real_thr_ax,   self._real_thr_history,   C_THROTTLE),
                (self._real_rpm_ax,   self._real_rpm_history,   C_RPM),
            ]:
                ax.clear()
                ax.set_facecolor(SURFACE_RAISED)
                ax.plot(hist, color=color, linewidth=1.2)
                ax.tick_params(colors=TEXT_MUTED, labelsize=7)
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                ax.spines['left'].set_color(BORDER_SUBTLE)
                ax.spines['bottom'].set_color(BORDER_SUBTLE)
            self._real_speed_ax.set_title('SPEED', color=TEXT_MUTED, fontsize=8, pad=4)
            self._real_speed_ax.set_ylabel('km/h', color=TEXT_MUTED, fontsize=7)
            self._real_thr_ax.set_title('THROTTLE', color=TEXT_MUTED, fontsize=8, pad=4)
            self._real_thr_ax.set_ylabel('%', color=TEXT_MUTED, fontsize=7)
            self._real_rpm_ax.set_title('RPM', color=TEXT_MUTED, fontsize=8, pad=4)
            self._real_rpm_ax.set_ylabel('rpm', color=TEXT_MUTED, fontsize=7)
            self._real_speed_canvas.draw_idle()
            self._real_thr_canvas.draw_idle()
            self._real_rpm_canvas.draw_idle()

    def _build_connection_strip_controls(self) -> list:
        """Return the trailing-slot controls for the title bar.

        After the UI revamp (tasks 12–13) the title bar replaces the legacy
        connection strip. To keep the bar uncluttered, only the minimal set of
        live controls is exposed here; the rest of the legacy widgets
        (connection_label, car_label, track_label, header_lap_label) are kept
        as off-screen state holders so existing setText() call sites continue
        to work — their information is now surfaced via the title bar's source
        pill and session block.
        """
        out: list = []

        # Status indicator (just the dot — pulses green when connected,
        # grey when disconnected). The accompanying "DISCONNECTED" /
        # "CONNECTED · ACC" text is redundant with the source pill.
        self.connection_dot = QLabel('●')
        self.connection_dot.setFont(sans(12))
        self.connection_dot.setStyleSheet(
            f'color: {TEXT_MUTED}; background: transparent; border: none;'
        )
        self.connection_dot.setToolTip('Disconnected')
        out.append(self.connection_dot)

        # Game source combo (no label — combo is self-explanatory)
        self.game_combo = QComboBox()
        self.game_combo.addItems([
            'Auto-Detect', 'ACC (Shared Memory)', 'AC (UDP)', 'iRacing (SDK)',
            'ELM327 (OBD-II)',
        ])
        self.game_combo.setFixedWidth(150)
        self.game_combo.setToolTip('Telemetry source')
        self.game_combo.currentTextChanged.connect(self._on_game_changed)
        out.append(self.game_combo)

        # Track combo (no label)
        self.track_combo = QComboBox()
        self.track_combo.addItem('Auto-Detect', userData=None)
        for key, td in TRACKS.items():
            self.track_combo.addItem(td['name'], userData=key)
        self.track_combo.setFixedWidth(140)
        self.track_combo.setToolTip('Track override')
        self.track_combo.currentIndexChanged.connect(self._on_track_changed)
        out.append(self.track_combo)

        # UDP host/port — kept off-screen as state holders. They're only
        # relevant to AC UDP; defaults are 127.0.0.1:9996. If a user needs
        # to change them, AC has its own settings; we don't need to expose
        # them in the chrome on every screen.
        self.udp_host = QLineEdit('127.0.0.1')
        self.udp_host.setFixedWidth(110)
        self.udp_host.hide()
        self.udp_port = QLineEdit('9996')
        self.udp_port.setFixedWidth(55)
        self.udp_port.hide()

        # Track recorder
        self.rec_btn = QPushButton('● REC')
        self.rec_btn.setFixedSize(64, 22)
        self.rec_btn.setCheckable(True)
        self.rec_btn.setToolTip('Record track map')
        self.rec_btn.setStyleSheet(
            f'QPushButton {{ background: {SURFACE_HOVER}; color: {TEXT_MUTED}; border: 1px solid {BORDER_STRONG};'
            f' border-radius: 3px; font-size: 10px; padding: 0 6px; }}'
            f'QPushButton:checked {{ background: #5a0000; color: {C_BRAKE};'
            f' border-color: {C_BRAKE}; }}'
        )
        self.rec_btn.toggled.connect(self._on_rec_toggled)
        # rec_label kept as state holder, hidden
        self.rec_label = QLabel('')
        self.rec_label.hide()
        out.append(self.rec_btn)

        # Import track map from JSON
        self.import_track_btn = QPushButton('⬆ MAP')
        self.import_track_btn.setFixedSize(72, 22)
        self.import_track_btn.setToolTip('Import track map JSON')
        self.import_track_btn.setStyleSheet(
            f'QPushButton {{ background: {SURFACE_HOVER}; color: {TEXT_MUTED}; border: 1px solid {BORDER_STRONG};'
            f' border-radius: 3px; font-size: 10px; padding: 0 6px; }}'
            f'QPushButton:hover {{ color: {C_SPEED}; border-color: {C_SPEED}; }}'
        )
        self.import_track_btn.clicked.connect(self._import_trackmap)
        out.append(self.import_track_btn)

        # Manual lap trigger (visible only in real racing mode)
        self._manual_lap_btn = QPushButton('LAP')
        self._manual_lap_btn.setFixedSize(55, 22)
        self._manual_lap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._manual_lap_btn.setStyleSheet(
            f'QPushButton {{ background: #0a2218; color: {C_THROTTLE};'
            f' border: 1px solid {C_THROTTLE}; border-radius: 3px;'
            f' font-size: 10px; font-weight: bold; letter-spacing: 1px; }}'
            f'QPushButton:hover {{ background: #0f3322; }}'
            f'QPushButton:pressed {{ background: #061a10; }}'
        )
        self._manual_lap_btn.setToolTip('Complete current lap (shortcut: L)')
        self._manual_lap_btn.clicked.connect(self._on_manual_lap)
        self._manual_lap_btn.setVisible(False)
        out.append(self._manual_lap_btn)

        # Keyboard shortcut for lap trigger (not a widget, wired here)
        self._lap_shortcut = QShortcut(QKeySequence('L'), self)
        self._lap_shortcut.activated.connect(self._on_manual_lap)
        self._lap_shortcut.setEnabled(False)

        # Off-screen state holders. These widgets exist so legacy setText()
        # call sites keep working; their information is surfaced via the
        # title bar's source pill (car/track) and session block (lap).
        self.connection_label = QLabel('DISCONNECTED')
        self.connection_label.hide()
        self.car_label = QLabel('—')
        self.car_label.hide()
        self.track_label = QLabel('—')
        self.track_label.hide()
        self.header_lap_label = QLabel('LAP —')
        self.header_lap_label.hide()

        return out

    # ------------------------------------------------------------------
    # DATA MANAGEMENT
    # ------------------------------------------------------------------

    # Channel names for the pre-allocated lap buffer (order must stay stable).
    _LAP_CHANNELS = (
        'time_ms', 'dist_m', 'speed', 'throttle', 'brake', 'steer_deg',
        'rpm', 'gear', 'abs', 'tc', 'fuel_l', 'brake_bias_pct',
        'world_x', 'world_z', 'air_temp', 'road_temp',
        'tyre_temp_fl', 'tyre_temp_fr', 'tyre_temp_rl', 'tyre_temp_rr',
        'tyre_pressure_fl', 'tyre_pressure_fr', 'tyre_pressure_rl', 'tyre_pressure_rr',
        'brake_temp_fl', 'brake_temp_fr', 'brake_temp_rl', 'brake_temp_rr',
        'tyre_wear_fl', 'tyre_wear_fr', 'tyre_wear_rl', 'tyre_wear_rr',
    )
    _LAP_BUF_INIT = 512  # initial capacity; doubles on overflow

    def _reset_current_lap_data(self):
        # Pre-allocate float32 arrays per channel.  _lap_n tracks how many
        # samples have been written; callers slice [:self._lap_n] to read.
        self._lap_buf = {ch: np.empty(self._LAP_BUF_INIT, dtype=np.float32)
                         for ch in self._LAP_CHANNELS}
        self._lap_n = 0
        self._current_deltas = []

    @property
    def current_lap_data(self) -> dict:
        """Live view of the current lap's channel arrays (sliced to written length)."""
        n = self._lap_n
        return {ch: self._lap_buf[ch][:n] for ch in self._LAP_CHANNELS}

    _MIN_LAP_TIME_S = 45  # ignore false laps from pause/resume glitches

    def _store_completed_lap(self):
        if self._current_lap_had_pit_exit:
            return  # outlap — car exited pit lane this lap, don't record
        # Snapshot once; avoids rebuilding the sliced-array dict multiple times.
        snap = self.current_lap_data
        if self._lap_n == 0:
            return
        dists = snap['dist_m']
        times = snap['time_ms']
        if len(times) == 0 or float(times[-1]) / 1000.0 < self._MIN_LAP_TIME_S:
            return  # too short — likely a pause/resume glitch
        if self._lap_n < 100:
            return  # too few samples — spurious lap-change misfire from stale telemetry

        total_time_s = float(times[-1]) / 1000.0

        sectors: list = [None, None, None]
        if len(dists) == len(times):
            _track_length_m = TRACKS.get(self._active_track_key or '', {}).get(
                'length_m', MONZA_LENGTH_M)
            # ACC takes a few ticks to update lap_dist_pct after the line crosses,
            # leaving stale samples at both ends of the buffer:
            #   head: dist_m near track_length (previous lap's final position)
            #   tail: dist_m near 0 (new lap's first position already written)
            # Strip both so sector boundaries land in clean monotonic data.
            stale_hi = _track_length_m * 0.95
            stale_lo = _track_length_m * 0.05
            head = 0
            while head < len(dists) - 1 and float(dists[head]) > stale_hi:
                head += 1
            tail = len(dists)
            while tail > head + 1 and float(dists[tail - 1]) < stale_lo:
                tail -= 1
            dists = dists[head:tail]
            times = times[head:tail]
            boundaries = [_track_length_m * f for f in (1/3, 2/3, 1.0)]
            sectors = _compute_sector_times(dists, times, boundaries)

        self.session_laps.append({
            'lap_number':    self.current_lap_count,
            'total_time_s':  total_time_s,
            'lap_valid':     self._current_lap_valid,
            'sectors':       sectors,
            'data':          {k: v.tolist() for k, v in snap.items()},
                # Session metadata snapshot at lap completion
                'meta': {
                    'car_name':      self._last_car_name,
                    'track_name':    self._last_track_name,
                    'track_key':     self._active_track_key or '',
                    'track_length_m': TRACKS.get(self._active_track_key or '', {}).get(
                        'length_m', MONZA_LENGTH_M),
                    'session_type':  self._last_session_type,
                    'tyre_compound': self._last_tyre_compound,
                    'air_temp_c':    round(self._last_air_temp, 1),
                    'road_temp_c':   round(self._last_road_temp, 1),
                },
        })
        self.lap_history.refresh(self.session_laps)
        self._populate_comparison_combos()
        self._populate_replay_combo()
        self._refresh_session_tab()

        # Coach tab was removed (raw-data focus). LapCoach engine still
        # runs for any internal use, but no UI consumer needs it now.

        # Promote this lap to the reference for delta / sector comparison
        if len(dists) > 0 and len(dists) == len(times):
            self._ref_lap_dists = dists.tolist()
            self._ref_lap_times = times.tolist()
            self._ref_lap_time_s = float(times[-1]) / 1000.0

    def _set_graph_title_suffix(self, suffix: str):
        # Lap info is shown in the connection strip header label.
        # Graph channel headers stay clean (no per-lap suffix in the label text).
        _ = suffix  # acknowledged, intentionally unused here

    # ------------------------------------------------------------------
    # LAP COMPARISON TAB
    # ------------------------------------------------------------------

    def _populate_comparison_combos(self):
        """Rebuild both QComboBoxes from self.session_laps (called after each lap stored)."""
        def _fmt(lap):
            t = lap.get('total_time_s', 0)
            m = int(t // 60)
            s = t % 60
            return f"Lap {lap['lap_number']}  {m}:{s:06.3f}"

        cur_a = self._cmp_combo_a.currentIndex()
        cur_b = self._cmp_combo_b.currentIndex()

        self._cmp_combo_a.blockSignals(True)
        self._cmp_combo_b.blockSignals(True)
        self._cmp_combo_a.clear()
        self._cmp_combo_b.clear()

        for lap in self.session_laps:
            label = _fmt(lap)
            if lap.get('imported'):
                label = '[IMP] ' + label
            self._cmp_combo_a.addItem(label)
            self._cmp_combo_b.addItem(label)

        # Default: most recent lap vs second most recent
        n = len(self.session_laps)
        self._cmp_combo_a.setCurrentIndex(max(0, n - 2))
        self._cmp_combo_b.setCurrentIndex(n - 1)
        if cur_a >= 0 and cur_a < n:
            self._cmp_combo_a.setCurrentIndex(cur_a)
        if cur_b >= 0 and cur_b < n:
            self._cmp_combo_b.setCurrentIndex(cur_b)

        self._cmp_combo_a.blockSignals(False)
        self._cmp_combo_b.blockSignals(False)

    def _refresh_comparison(self):
        """Plot both selected laps on the comparison graphs."""
        idx_a = self._cmp_combo_a.currentIndex()
        idx_b = self._cmp_combo_b.currentIndex()

        if idx_a < 0 or idx_b < 0 or idx_a >= len(self.session_laps) \
                or idx_b >= len(self.session_laps):
            return

        lap_a = self.session_laps[idx_a]
        lap_b = self.session_laps[idx_b]

        def _fmt_time(t_s):
            m = int(t_s // 60)
            s = t_s % 60
            return f'{m}:{s:06.3f}'

        self._cmp_time_a.setText(_fmt_time(lap_a.get('total_time_s', 0)))
        self._cmp_time_b.setText(_fmt_time(lap_b.get('total_time_s', 0)))

        dt = lap_a.get('total_time_s', 0) - lap_b.get('total_time_s', 0)
        sign = '+' if dt > 0 else ''
        self._cmp_delta_lbl.setText(f'Δ {sign}{dt:.3f}s')
        self._cmp_delta_lbl.setStyleSheet(
            f'color: {C_BRAKE if dt > 0 else C_THROTTLE};')

        da = lap_a['data']
        db = lap_b['data']
        dists_a = da.get('dist_m', [])
        dists_b = db.get('dist_m', [])

        self._cmp_speed.set_data(dists_a, da.get('speed', []),
                                 dists_b, db.get('speed', []))
        self._cmp_thr_brk_a.set_data(dists_a, da.get('throttle', []),
                                      dists_b, db.get('throttle', []))
        self._cmp_brk.set_data(dists_a, da.get('brake', []),
                               dists_b, db.get('brake', []))
        self._cmp_gear.set_data(dists_a, da.get('gear', []),
                                dists_b, db.get('gear', []))
        self._cmp_rpm.set_data(dists_a, da.get('rpm', []),
                               dists_b, db.get('rpm', []))
        self._cmp_steer.set_data(dists_a, da.get('steer_deg', []),
                                 dists_b, db.get('steer_deg', []))

        times_a = da.get('time_ms', [])
        times_b = db.get('time_ms', [])
        self._cmp_delta_graph.set_data(dists_a, times_a, dists_b, times_b)

    def _export_graphs_lap_json(self):
        """Export the last completed lap from the Telemetry Graphs tab as a replay-compatible JSON."""
        import os, re as _re, datetime

        if not self.session_laps:
            QMessageBox.information(self, 'Export JSON',
                                    'No completed laps to export yet.')
            return

        lap = self.session_laps[-1]
        t = lap.get('total_time_s', 0)
        m, s = int(t // 60), t % 60

        def _slug(text: str) -> str:
            return _re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

        date_str  = datetime.date.today().strftime('%Y-%m-%d')
        try:
            user_str = _slug(os.getlogin())
        except Exception:
            user_str = 'user'
        track_str = _slug(
            TRACKS.get(self._active_track_key or '', {}).get('name', '')
            or self.track_label.text()
            or 'unknown-track'
        )
        lap_str  = f'lap{lap["lap_number"]}'
        time_str = f'{m}m{s:06.3f}s'

        default_name = f'{date_str}-{user_str}-{track_str}-{lap_str}-{time_str}.json.gz'

        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Lap JSON', default_name,
            'Lap JSON (gzipped) (*.json.gz);;All files (*)')
        if not path:
            return

        payload = {
            'lap_number':   lap['lap_number'],
            'total_time_s': lap.get('total_time_s', 0),
            'sectors':      lap.get('sectors', [None, None, None]),
            'track_name':   TRACKS.get(self._active_track_key or '', {}).get('name', ''),
            'data':         {k: list(v) for k, v in lap['data'].items()},
        }
        with gzip.open(path, 'wt', encoding='utf-8', compresslevel=6) as f:
            json.dump(payload, f)
        QMessageBox.information(self, 'Export JSON', f'Lap saved to:\n{path}')

    def _build_lap_json_payload(self, lap: dict) -> dict:
        """Build a full JSON payload dict for any stored lap."""
        import datetime

        d    = lap['data']
        meta = lap.get('meta', {})
        t    = lap.get('total_time_s', 0)
        m, s = int(t // 60), t % 60

        def _safe_avg(lst): return round(sum(lst) / len(lst), 2) if lst else 0.0
        def _safe_max(lst): return round(max(lst), 2) if lst else 0.0

        speeds    = d.get('speed', [])
        rpms      = d.get('rpm', [])
        throttles = d.get('throttle', [])
        brakes    = d.get('brake', [])
        fuels     = d.get('fuel_l', [])
        fuel_used = round(fuels[0] - fuels[-1], 3) if len(fuels) >= 2 else 0.0

        sectors_raw = lap.get('sectors', [None, None, None])
        def _fmt_sector(s_val):
            if s_val is None:
                return None
            sm, ss = int(s_val // 60), s_val % 60
            return f'{sm}:{ss:06.3f}' if sm else f'{ss:.3f}'

        track_key = meta.get('track_key', '') or self._active_track_key or ''
        track_pts = TRACKS.get(track_key, {}).get('pts', [])
        if not track_pts and self.track_map._norm:
            track_pts = [[round(x, 5), round(y, 5)] for x, y in self.track_map._norm]

        return {
            'schema_version': '2.0',
            'export_timestamp': datetime.datetime.now().isoformat(timespec='seconds'),
            'session': {
                'date':          datetime.date.today().strftime('%Y-%m-%d'),
                'car':           meta.get('car_name', ''),
                'track':         meta.get('track_name', ''),
                'track_key':     track_key,
                'track_length_m': meta.get('track_length_m', 0),
                'session_type':  meta.get('session_type', ''),
                'tyre_compound': meta.get('tyre_compound', ''),
                'air_temp_c':    meta.get('air_temp_c', 0.0),
                'road_temp_c':   meta.get('road_temp_c', 0.0),
            },
            'lap': {
                'lap_number':    lap['lap_number'],
                'total_time_s':  t,
                'total_time_fmt': f'{m}:{s:06.3f}',
                'sectors_s':     sectors_raw,
                'sectors_fmt':   [_fmt_sector(sv) for sv in sectors_raw],
            },
            'summary': {
                'max_speed_kph':    _safe_max(speeds),
                'avg_speed_kph':    _safe_avg(speeds),
                'max_rpm':          _safe_max(rpms),
                'avg_rpm':          _safe_avg(rpms),
                'avg_throttle_pct': round(_safe_avg(throttles), 1),
                'avg_brake_pct':    round(_safe_avg(brakes), 1),
                'fuel_used_l':      fuel_used,
                'tyre_wear_pct': {
                    'fl': round(_safe_max(d.get('tyre_wear_fl', [])) * 100, 2),
                    'fr': round(_safe_max(d.get('tyre_wear_fr', [])) * 100, 2),
                    'rl': round(_safe_max(d.get('tyre_wear_rl', [])) * 100, 2),
                    'rr': round(_safe_max(d.get('tyre_wear_rr', [])) * 100, 2),
                },
                'max_tyre_temp_c': {
                    'fl': _safe_max(d.get('tyre_temp_fl', [])),
                    'fr': _safe_max(d.get('tyre_temp_fr', [])),
                    'rl': _safe_max(d.get('tyre_temp_rl', [])),
                    'rr': _safe_max(d.get('tyre_temp_rr', [])),
                },
                'max_brake_temp_c': {
                    'fl': _safe_max(d.get('brake_temp_fl', [])),
                    'fr': _safe_max(d.get('brake_temp_fr', [])),
                    'rl': _safe_max(d.get('brake_temp_rl', [])),
                    'rr': _safe_max(d.get('brake_temp_rr', [])),
                },
            },
            'telemetry': {
                'time_ms':        d.get('time_ms', []),
                'dist_m':         d.get('dist_m', []),
                'speed_kph':      d.get('speed', []),
                'throttle':       d.get('throttle', []),
                'brake':          d.get('brake', []),
                'steer_deg':      d.get('steer_deg', []),
                'rpm':            d.get('rpm', []),
                'gear':           d.get('gear', []),
                'abs':            d.get('abs', []),
                'tc':             d.get('tc', []),
                'fuel_l':         d.get('fuel_l', []),
                'brake_bias_pct': d.get('brake_bias_pct', []),
                'world_x':        d.get('world_x', []),
                'world_z':        d.get('world_z', []),
                'air_temp_c':     d.get('air_temp', []),
                'road_temp_c':    d.get('road_temp', []),
                'tyre_temp':     {'fl': d.get('tyre_temp_fl', []),     'fr': d.get('tyre_temp_fr', []),
                                  'rl': d.get('tyre_temp_rl', []),     'rr': d.get('tyre_temp_rr', [])},
                'tyre_pressure': {'fl': d.get('tyre_pressure_fl', []), 'fr': d.get('tyre_pressure_fr', []),
                                  'rl': d.get('tyre_pressure_rl', []), 'rr': d.get('tyre_pressure_rr', [])},
                'brake_temp':    {'fl': d.get('brake_temp_fl', []),    'fr': d.get('brake_temp_fr', []),
                                  'rl': d.get('brake_temp_rl', []),    'rr': d.get('brake_temp_rr', [])},
                'tyre_wear':     {'fl': d.get('tyre_wear_fl', []),     'fr': d.get('tyre_wear_fr', []),
                                  'rl': d.get('tyre_wear_rl', []),     'rr': d.get('tyre_wear_rr', [])},
            },
            'track_map': {
                'pts':      track_pts,
                'length_m': meta.get('track_length_m', 0),
            },
        }

    def _export_lap_to_json(self, lap: dict):
        """Export any stored lap as a full JSON file (save dialog)."""
        import os, re as _re, datetime

        t   = lap.get('total_time_s', 0)
        m, s = int(t // 60), t % 60

        def _slug(text: str) -> str:
            return _re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

        date_str  = datetime.date.today().strftime('%Y-%m-%d')
        try:
            user_str = _slug(os.getlogin())
        except Exception:
            user_str = 'user'
        meta      = lap.get('meta', {})
        track_str = _slug(meta.get('track_name', '') or self.track_label.text() or 'unknown-track')
        lap_str   = f'lap{lap["lap_number"]}'
        time_str  = f'{m}m{s:06.3f}s'

        default_name = f'{date_str}-{user_str}-{track_str}-{lap_str}-{time_str}-full.json.gz'
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Lap JSON', default_name,
            'Lap JSON (gzipped) (*.json.gz);;All files (*)')
        if not path:
            return

        payload = self._build_lap_json_payload(lap)
        with gzip.open(path, 'wt', encoding='utf-8', compresslevel=6) as f:
            json.dump(payload, f)
        QMessageBox.information(self, 'Export JSON',
                                f'Lap {lap["lap_number"]} saved to:\n{path}')

    def _export_full_lap_json(self):
        """Export the last completed lap as a comprehensive JSON with all telemetry,
        tyre data, fuel, track map, session metadata, and summary stats."""
        if not self.session_laps:
            QMessageBox.information(self, 'Export Full JSON',
                                    'No completed laps to export yet.')
            return
        self._export_lap_to_json(self.session_laps[-1])

    def _export_lap_json(self):
        """Export the lap currently selected in Combo A as a shareable JSON file."""
        import os, re as _re, datetime

        idx = self._cmp_combo_a.currentIndex()
        if idx < 0 or idx >= len(self.session_laps):
            QMessageBox.information(self, 'Export Lap', 'No lap selected in Lap A.')
            return

        lap = self.session_laps[idx]
        t = lap.get('total_time_s', 0)
        m, s = int(t // 60), t % 60

        def _slug(text: str) -> str:
            return _re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

        date_str  = datetime.date.today().strftime('%Y-%m-%d')
        try:
            user_str = _slug(os.getlogin())
        except Exception:
            user_str = 'user'
        track_str = _slug(
            TRACKS.get(self._active_track_key or '', {}).get('name', '')
            or self.track_label.text()
            or 'unknown-track'
        )
        lap_str   = f'lap{lap["lap_number"]}'
        time_str  = f'{m}m{s:06.3f}s'

        default_name = f'{date_str}-{user_str}-{track_str}-{lap_str}-{time_str}.json.gz'

        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Lap', default_name,
            'Lap JSON (gzipped) (*.json.gz);;All files (*)')
        if not path:
            return

        payload = {
            'lap_number':   lap['lap_number'],
            'total_time_s': lap.get('total_time_s', 0),
            'sectors':      lap.get('sectors', [None, None, None]),
            'track_name':   TRACKS.get(self._active_track_key or '', {}).get('name', ''),
            'data':         {k: list(v) for k, v in lap['data'].items()},
        }
        with gzip.open(path, 'wt', encoding='utf-8', compresslevel=6) as f:
            json.dump(payload, f)
        QMessageBox.information(self, 'Export Lap', f'Lap saved to:\n{path}')

    def _import_lap_json(self):
        """Import a shared lap JSON file and add it to the comparison dropdowns."""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Import Lap', '',
            'Lap JSON (gzipped) (*.json.gz);;All files (*)')
        if not path:
            return

        try:
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                payload = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, 'Import Failed', f'Could not read file:\n{e}')
            return

        if 'data' not in payload or 'dist_m' not in payload.get('data', {}):
            QMessageBox.warning(self, 'Import Failed',
                                'Invalid lap JSON: missing "data.dist_m".')
            return

        # Give the lap a unique number so it doesn't clash with live laps
        existing_nums = {l['lap_number'] for l in self.session_laps}
        lap_num = payload.get('lap_number', 0)
        if lap_num in existing_nums:
            lap_num = max(existing_nums) + 1

        lap = {
            'lap_number':   lap_num,
            'total_time_s': float(payload.get('total_time_s', 0)),
            'sectors':      payload.get('sectors', [None, None, None]),
            'data':         {k: list(v) for k, v in payload['data'].items()},
            'imported':     True,
        }
        self.session_laps.append(lap)
        self._populate_comparison_combos()
        self._populate_replay_combo()
        self._refresh_session_tab()

        # Auto-select the imported lap in combo B
        self._cmp_combo_b.setCurrentIndex(len(self.session_laps) - 1)

        t = lap['total_time_s']
        m, s = int(t // 60), t % 60
        QMessageBox.information(self, 'Import Lap',
                                f'Imported lap {lap_num}  ({m}:{s:06.3f})')

    # ------------------------------------------------------------------
    # REPLAY TAB
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # REPLAY HELPERS
    # ------------------------------------------------------------------

    def _populate_replay_combo(self):
        """Rebuild the replay lap dropdown from session_laps."""
        cur = self._replay_combo.currentIndex()
        self._replay_combo.blockSignals(True)
        self._replay_combo.clear()
        for lap in self.session_laps:
            t = lap.get('total_time_s', 0)
            m, s = int(t // 60), t % 60
            label = f"Lap {lap['lap_number']}  {m}:{s:06.3f}"
            if lap.get('imported'):
                label = '[IMP] ' + label
            self._replay_combo.addItem(label)
        if cur >= 0 and cur < len(self.session_laps):
            self._replay_combo.setCurrentIndex(cur)
        elif self.session_laps:
            self._replay_combo.setCurrentIndex(len(self.session_laps) - 1)
        self._replay_combo.blockSignals(False)

    def _load_replay_lap(self, idx: int):
        """Load the selected lap into the replay engine."""
        if idx < 0 or idx >= len(self.session_laps):
            return
        lap = self.session_laps[idx]
        data = lap.get('data', {})
        if not data.get('time_ms'):
            return

        # Stop any running playback
        self._replay_playing = False
        self._replay_last_mono = 0.0
        self._replay_play_btn.setText('PLAY')

        self._replay_data = data
        times = data['time_ms']
        self._replay_total_ms = int(times[-1]) if times else 0
        self._replay_pos_ms = 0

        # Compute sector boundary times from sector durations
        sectors = lap.get('sectors', [None, None, None])
        self._replay_sector_ms = []
        accum_s = 0.0
        labels = ['S1', 'S2', 'S3']
        for i, dur in enumerate(sectors or []):
            if dur is not None:
                accum_s += dur
                self._replay_sector_ms.append((labels[i], int(accum_s * 1000)))

        # Update scrubber
        self._replay_scrub.set_duration(
            self._replay_total_ms, self._replay_sector_ms)
        self._replay_scrub.set_value(0)

        # Load sector time labels
        sec_fmts = []
        for dur in (sectors or []):
            if dur is not None:
                sm, ss = int(dur // 60), dur % 60
                sec_fmts.append(f'{sm}:{ss:06.3f}')
            else:
                sec_fmts.append('—')
        while len(sec_fmts) < 3:
            sec_fmts.append('—')
        self._rpl_s1_lbl.setText(f'S1: {sec_fmts[0]}')
        self._rpl_s2_lbl.setText(f'S2: {sec_fmts[1]}')
        self._rpl_s3_lbl.setText(f'S3: {sec_fmts[2]}')

        # Load track map — prefer saved track, fall back to live-built shape
        track_key = self._active_track_key or ''
        if track_key and track_key in TRACKS:
            self._rpl_map.set_track(track_key)
        else:
            self._rpl_map.reset_track()

        # If set_track found no saved pts, borrow the shape the live map built this session
        if not self._rpl_map._norm and self.track_map._norm:
            self._rpl_map._norm = list(self.track_map._norm)
            self._rpl_map._pts = []
            self._rpl_map._last_sz = (0, 0)

        self._rpl_map.reset()

        # Paint throttle/brake heatmap from lap data
        dists = data.get('dist_m', [])
        throttles = data.get('throttle', [])
        brakes = data.get('brake', [])
        track_len = TRACKS.get(track_key, {}).get('length_m', MONZA_LENGTH_M)
        for d, th, br in zip(dists, throttles, brakes):
            prog = d / track_len if track_len > 0 else 0
            self._rpl_map.update_telemetry(prog, th, br)

        # Load graphs
        self._rpl_speed_graph.set_lap_data(times, data.get('speed', []))
        self._rpl_thr_brk_graph.set_lap_data(
            times, data.get('throttle', []), data.get('brake', []))
        self._rpl_steer_graph.set_lap_data(times, data.get('steer_deg', []))
        self._rpl_rpm_graph.set_lap_data(times, data.get('rpm', []))
        self._rpl_gear_graph.set_lap_data(times, data.get('gear', []))

        # Seek to start
        self._replay_seek(0)

    def _replay_seek(self, pos_ms: int):
        """Update all replay displays to the given position in ms."""
        if not self._replay_data:
            return
        self._replay_pos_ms = max(0, min(pos_ms, self._replay_total_ms))
        times = self._replay_data.get('time_ms', [])
        if not times:
            return

        # Binary-search for insertion point
        lo, hi = 0, len(times) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if times[mid] < self._replay_pos_ms:
                lo = mid + 1
            else:
                hi = mid
        idx = lo

        # Interpolate between surrounding samples for smooth playback
        if idx > 0 and idx < len(times):
            t0, t1 = times[idx - 1], times[idx]
            span = t1 - t0
            t = (self._replay_pos_ms - t0) / span if span > 0 else 0.0
            t = max(0.0, min(1.0, t))
            i0, i1 = idx - 1, idx
        else:
            t = 0.0
            i0 = i1 = idx

        def _lerp(key, default=0):
            vals = self._replay_data.get(key, [default])
            v0 = vals[i0] if i0 < len(vals) else default
            v1 = vals[i1] if i1 < len(vals) else default
            return v0 + t * (v1 - v0)

        def _nearest(key, default=0):
            vals = self._replay_data.get(key, [default])
            pick = i1 if t >= 0.5 else i0
            return vals[pick] if pick < len(vals) else default

        # Continuous channels → lerp for smooth transitions
        speed    = _lerp('speed')
        rpm      = _lerp('rpm')
        throttle = _lerp('throttle')
        brake    = _lerp('brake')
        steer_d  = _lerp('steer_deg')
        dist_m   = _lerp('dist_m')

        # Discrete channels → snap to nearest sample
        gear  = _nearest('gear', 1)
        abs_v = _nearest('abs')
        tc_v  = _nearest('tc')

        # Dashboard widgets
        self._rpl_speed_lbl.setText(f'{int(speed)}')
        self._rpl_rpm_lbl.setText(f'{int(rpm):,}')
        self._rpl_rev_bar.set_value(rpm, 8000)
        if gear == 0:
            gear_text = 'R'
        elif gear == 1:
            gear_text = 'N'
        else:
            gear_text = str(gear - 1)
        self._rpl_gear_lbl.setText(gear_text)
        self._rpl_throttle_bar.set_value(throttle)
        self._rpl_brake_bar.set_value(brake)
        self._rpl_steer.set_angle(math.radians(steer_d))
        self._rpl_abs_badge.set_active(abs_v > 0, f'{abs_v:.1f}')
        self._rpl_tc_badge.set_active(tc_v > 0, f'{tc_v:.1f}')

        # Sector label
        track_key = self._active_track_key or ''
        track_len = TRACKS.get(track_key, {}).get('length_m', MONZA_LENGTH_M)
        frac = (dist_m / track_len) if track_len > 0 else 0
        if frac < 1 / 3:
            sec_txt, sec_col = 'S1', C_DELTA
        elif frac < 2 / 3:
            sec_txt, sec_col = 'S2', C_STEER
        else:
            sec_txt, sec_col = 'S3', C_RPM
        self._rpl_sector_lbl.setText(sec_txt)
        self._rpl_sector_lbl.setStyleSheet(
            f'color: {sec_col}; font-family: Consolas; font-size: 14px; font-weight: bold;')

        # Track map car position
        lap_prog = (dist_m / track_len) if track_len > 0 else 0
        self._rpl_map.car_progress = max(0.0, min(1.0, lap_prog))

        # Time display
        cur_m  = int(self._replay_pos_ms // 60000)
        cur_s  = (self._replay_pos_ms % 60000) / 1000.0
        tot_m  = int(self._replay_total_ms // 60000)
        tot_s  = (self._replay_total_ms % 60000) / 1000.0
        self._rpl_time_lbl.setText(f'{cur_m}:{cur_s:06.3f} / {tot_m}:{tot_s:06.3f}')

        # Scrubber (block signals to avoid feedback loop)
        self._replay_scrub.set_value(self._replay_pos_ms)

        # Graph playheads
        for g in self._replay_graphs:
            g.set_playhead(self._replay_pos_ms)

    def _replay_scrubber_moved(self, value: int):
        """Called when the user drags the scrubber slider."""
        self._replay_seek(value)

    def _toggle_replay_playback(self):
        if not self._replay_data:
            return
        self._replay_playing = not self._replay_playing
        if self._replay_playing:
            if self._replay_pos_ms >= self._replay_total_ms:
                self._replay_seek(0)
            self._replay_play_btn.setText('PAUSE')
            self._replay_last_mono = time.monotonic()
        else:
            self._replay_play_btn.setText('PLAY')
            self._replay_last_mono = 0.0

    def _on_replay_speed_changed(self, text: str):
        try:
            self._replay_speed = float(text.replace('x', ''))
        except ValueError:
            self._replay_speed = 1.0

    def _import_replay_lap_json(self):
        """Import a lap JSON directly into the replay tab."""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Import Lap for Replay', '',
            'Lap JSON (gzipped) (*.json.gz);;All files (*)')
        if not path:
            return
        try:
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                payload = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, 'Import Failed', f'Could not read file:\n{e}')
            return
        if 'data' not in payload or 'time_ms' not in payload.get('data', {}):
            QMessageBox.warning(self, 'Import Failed',
                                'Invalid lap JSON: missing "data.time_ms".')
            return

        existing_nums = {l['lap_number'] for l in self.session_laps}
        lap_num = payload.get('lap_number', 0)
        if lap_num in existing_nums:
            lap_num = (max(existing_nums) + 1) if existing_nums else 1

        lap = {
            'lap_number':   lap_num,
            'total_time_s': float(payload.get('total_time_s', 0)),
            'sectors':      payload.get('sectors', [None, None, None]),
            'data':         {k: list(v) for k, v in payload['data'].items()},
            'imported':     True,
        }
        self.session_laps.append(lap)
        self._populate_replay_combo()
        self._populate_comparison_combos()
        self._refresh_session_tab()

        self._replay_combo.setCurrentIndex(len(self.session_laps) - 1)
        self._load_replay_lap(len(self.session_laps) - 1)

    # ------------------------------------------------------------------
    # SESSION TAB
    # ------------------------------------------------------------------

    def _refresh_session_tab(self):
        """Rebuild session summary rows and stats bar from self.session_laps."""
        laps = self.session_laps

        # Clear existing rows (keep trailing stretch)
        while self._sess_rows_layout.count() > 1:
            item = self._sess_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not laps:
            self._sess_empty_lbl.setVisible(True)
            self._sess_lbl_count.setText('0')
            for l in (self._sess_lbl_best, self._sess_lbl_avg, self._sess_lbl_gap):
                l.setText('—')
            return
        self._sess_empty_lbl.setVisible(False)

        def _fmt(t_s):
            m = int(t_s // 60)
            s = t_s % 60
            return f'{m}:{s:06.3f}'

        valid_times = [l['total_time_s'] for l in laps
                       if l.get('total_time_s', 0) > 0
                       and l.get('lap_valid', True)]
        best_t = min(valid_times) if valid_times else None
        avg_t  = (sum(valid_times) / len(valid_times)) if valid_times else None

        best_sectors: list = []
        for si in range(3):
            col = [l['sectors'][si] for l in laps
                   if l.get('sectors') and l['sectors'][si] is not None
                   and l.get('lap_valid', True)]
            best_sectors.append(min(col) if col else None)

        # Stats bar
        self._sess_lbl_count.setText(str(len(laps)))
        self._sess_lbl_best.setText(_fmt(best_t) if best_t else '—')
        self._sess_lbl_avg.setText(_fmt(avg_t) if avg_t else '—')
        if best_t and avg_t:
            gap = avg_t - best_t
            self._sess_lbl_gap.setText(f'+{gap:.3f}s')
        else:
            self._sess_lbl_gap.setText('—')

        # Rows (newest first)
        for lap in reversed(laps):
            t          = lap.get('total_time_s', 0)
            secs       = lap.get('sectors', [None, None, None]) or [None, None, None]
            lap_valid  = lap.get('lap_valid', True)
            valid      = lap_valid and t > 20 and all(s is not None for s in secs)
            is_best    = bool(best_t is not None and t > 0 and abs(t - best_t) < 0.001)
            samples    = len(lap['data'].get('speed', []))

            row = QFrame()
            if is_best:
                row.setStyleSheet(
                    f'background: {C_PURPLE_BG}; border: 1px solid {C_PURPLE};'
                    f' border-radius: 4px;')
            else:
                row.setStyleSheet(
                    f'background: {SURFACE_RAISED}; border: 1px solid {BORDER_SUBTLE};'
                    f' border-radius: 4px;')
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 6, 10, 6)
            rl.setSpacing(0)

            def _cell(text, color=TEXT_SECONDARY, bold=False, stretch=0, align=Qt.AlignmentFlag.AlignCenter):
                l = QLabel(text)
                l.setFont(mono(9, bold=bold))
                l.setStyleSheet(f'color: {color};')
                l.setAlignment(align)
                l.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                rl.addWidget(l, stretch)
                return l

            lap_color = C_PURPLE if is_best else TEXT_MUTED
            _cell(str(lap['lap_number']), color=lap_color, bold=is_best)
            _cell(_fmt(t), color=C_PURPLE if is_best else TEXT_SECONDARY, bold=is_best, stretch=2)

            for si, sec_t in enumerate(secs):
                if sec_t is None:
                    _cell('—', color=TEXT_MUTED, stretch=1)
                elif not lap_valid:
                    _cell(f'{sec_t:.3f}', color=C_BRAKE, stretch=1)
                else:
                    is_best_sec = bool(best_sectors[si] is not None
                                       and abs(sec_t - best_sectors[si]) < 0.001)
                    if is_best_sec:
                        _cell(f'{sec_t:.3f}', color=C_PURPLE, bold=True, stretch=1)
                    else:
                        _cell(f'{sec_t:.3f}', color=C_THROTTLE, stretch=1)

            _cell(str(samples), color=TEXT_MUTED, stretch=1)
            valid_lbl = QLabel('✓' if valid else '✗')
            valid_lbl.setFont(sans(9, bold=True))
            valid_lbl.setStyleSheet(
                f'color: {C_THROTTLE if valid else C_BRAKE};')
            valid_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            valid_lbl.setMinimumWidth(40)
            rl.addWidget(valid_lbl)

            export_btn = QPushButton('⬇')
            export_btn.setFont(sans(9))
            export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            export_btn.setFixedSize(32, 24)
            export_btn.setToolTip('Export this lap as JSON')
            export_btn.setStyleSheet(
                f'QPushButton {{ background: transparent; color: {TEXT_MUTED}; border: 1px solid {BORDER_STRONG};'
                f' border-radius: 3px; }}'
                f'QPushButton:hover {{ color: {C_SPEED}; border-color: {C_SPEED}; }}')
            _lap_ref = lap  # capture for lambda
            export_btn.clicked.connect(lambda _, lr=_lap_ref: self._export_lap_to_json(lr))
            rl.addWidget(export_btn)

            self._sess_rows_layout.insertWidget(0, row)

    def _export_csv(self):
        """Export all session lap data to a CSV file chosen by the user."""
        if not self.session_laps:
            QMessageBox.information(self, 'Export CSV',
                                    'No completed laps to export.')
            return

        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Session CSV', 'session.csv',
            'CSV files (*.csv);;All files (*)')
        if not path:
            return

        import csv

        def _fmt_time(seconds: float) -> str:
            if seconds <= 0:
                return '--:--.---'
            m = int(seconds // 60)
            s = seconds - m * 60
            return f'{m}:{s:06.3f}'

        def _sector_str(val) -> str:
            if val is None or val <= 0:
                return '--:--.---'
            return _fmt_time(val)

        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)

            # ── SECTION 1: Lap Summary ────────────────────────────────────
            writer.writerow(['=== LAP SUMMARY ==='])
            writer.writerow([
                'Lap', 'Lap Time', 'Sector 1', 'Sector 2', 'Sector 3',
                'Max Speed (km/h)', 'Avg Speed (km/h)',
                'Max Throttle (%)', 'Max Brake (%)',
                'Max RPM', 'Avg RPM',
                'ABS Events', 'TC Events',
            ])
            for lap in self.session_laps:
                d = lap['data']
                speeds   = [v for v in d.get('speed', []) if v > 0]
                throttles = d.get('throttle', [])
                brakes   = d.get('brake', [])
                rpms     = [v for v in d.get('rpm', []) if v > 0]
                abs_vals = d.get('abs', [])
                tc_vals  = d.get('tc', [])

                max_spd  = round(max(speeds),   1) if speeds   else ''
                avg_spd  = round(sum(speeds) / len(speeds), 1) if speeds else ''
                max_thr  = round(max(throttles), 1) if throttles else ''
                max_brk  = round(max(brakes),    1) if brakes   else ''
                max_rpm  = round(max(rpms))         if rpms     else ''
                avg_rpm  = round(sum(rpms) / len(rpms)) if rpms else ''
                abs_evts = sum(1 for v in abs_vals if v > 0)
                tc_evts  = sum(1 for v in tc_vals  if v > 0)

                sects = lap.get('sectors', [None, None, None]) or [None, None, None]
                writer.writerow([
                    lap['lap_number'],
                    _fmt_time(lap.get('total_time_s', 0)),
                    _sector_str(sects[0] if len(sects) > 0 else None),
                    _sector_str(sects[1] if len(sects) > 1 else None),
                    _sector_str(sects[2] if len(sects) > 2 else None),
                    max_spd, avg_spd,
                    max_thr, max_brk,
                    max_rpm, avg_rpm,
                    abs_evts, tc_evts,
                ])

            writer.writerow([])
            writer.writerow([])

            # ── SECTION 2: Raw Telemetry ──────────────────────────────────
            writer.writerow(['=== RAW TELEMETRY ==='])
            writer.writerow([
                'lap', 'dist_m', 'lap_time',
                'speed_kmh', 'throttle_%', 'brake_%',
                'steer_deg', 'rpm', 'gear',
                'abs_%', 'tc_%',
            ])
            for lap in self.session_laps:
                d = lap['data']
                n = len(d.get('dist_m', []))
                for i in range(n):
                    def _v(key, idx=i):
                        arr = d.get(key, [])
                        return arr[idx] if idx < len(arr) else ''
                    time_ms = _v('time_ms')
                    lap_time_str = _fmt_time(time_ms / 1000.0) if time_ms != '' else ''
                    writer.writerow([
                        lap['lap_number'],
                        round(_v('dist_m'), 1) if _v('dist_m') != '' else '',
                        lap_time_str,
                        round(_v('speed'), 1) if _v('speed') != '' else '',
                        round(_v('throttle'), 1) if _v('throttle') != '' else '',
                        round(_v('brake'), 1) if _v('brake') != '' else '',
                        round(_v('steer_deg'), 2) if _v('steer_deg') != '' else '',
                        round(_v('rpm')) if _v('rpm') != '' else '',
                        int(_v('gear')) if _v('gear') != '' else '',
                        round(_v('abs'), 1) if _v('abs') != '' else '',
                        round(_v('tc'), 1) if _v('tc') != '' else '',
                    ])

        QMessageBox.information(self, 'Export CSV',
                                f'Saved {len(self.session_laps)} laps to:\n{path}')

    def _update_fuel_save(self):
        history = self._fuel_per_lap_history
        if not history:
            self.strategy_tab._fs_result_lbl.setText('Complete a lap first.')
            self.strategy_tab._fs_result_lbl.setStyleSheet(f'color: {TEXT_MUTED};')
            return
        avg = sum(history[-5:]) / len(history[-5:])
        fuel = self._last_known_fuel
        laps_to_go = self.strategy_tab._fs_laps_spin.value()
        needed = avg * laps_to_go
        delta = fuel - needed
        if delta >= 0:
            save_per_lap = delta / laps_to_go
            self.strategy_tab._fs_result_lbl.setText(
                f'Buffer  +{delta:.1f} L   ({save_per_lap:.2f} L/lap spare)')
            self.strategy_tab._fs_result_lbl.setStyleSheet(f'color: {C_THROTTLE};')
        else:
            save_per_lap = abs(delta) / laps_to_go
            self.strategy_tab._fs_result_lbl.setText(
                f'SAVE  {save_per_lap:.2f} L/lap   (need {needed:.1f} L, have {fuel:.1f} L)')
            col = C_RPM if save_per_lap < 0.5 else C_BRAKE
            self.strategy_tab._fs_result_lbl.setStyleSheet(f'color: {col};')

    def _update_undercut(self):
        gap_a = abs(self._last_gap_ahead) / 1000.0
        gap_b = abs(self._last_gap_behind) / 1000.0
        pit_loss = self.strategy_tab._uco_pit_loss_spin.value()
        pace_delta = self.strategy_tab._uco_pace_delta_spin.value()

        if pace_delta > 0 and gap_a > 0:
            laps_to_catch = (gap_a + pit_loss) / pace_delta
            if laps_to_catch <= 3:
                uc_text = f'UNDERCUT: viable in ~{laps_to_catch:.1f} laps on fresh tyres'
                uc_col = C_THROTTLE
            else:
                uc_text = f'UNDERCUT: needs ~{laps_to_catch:.1f} laps — gap too large'
                uc_col = C_BRAKE
        else:
            uc_text = 'UNDERCUT: no car ahead data'
            uc_col = TEXT_MUTED
        self.strategy_tab._uco_undercut_lbl.setText(uc_text)
        self.strategy_tab._uco_undercut_lbl.setStyleSheet(f'color: {uc_col};')

        if gap_b > 0:
            margin = pit_loss - gap_b
            if margin > 0:
                oc_text = f'OVERCUT: risky — gap only {gap_b:.1f}s, need >{pit_loss:.0f}s'
                oc_col = C_BRAKE
            else:
                laps_buffer = gap_b / pace_delta if pace_delta > 0 else 99
                oc_text = f'OVERCUT: safe ~{laps_buffer:.1f} laps buffer after their stop'
                oc_col = C_THROTTLE
        else:
            oc_text = 'OVERCUT: no car behind data'
            oc_col = TEXT_MUTED
        self.strategy_tab._uco_overcut_lbl.setText(oc_text)
        self.strategy_tab._uco_overcut_lbl.setStyleSheet(f'color: {oc_col};')

    # ------------------------------------------------------------------
    # GAME SELECTION / AUTO-DETECT
    # ------------------------------------------------------------------

    def _on_game_changed(self, game: str):
        self.auto_detect = False
        if game == 'Auto-Detect':
            self.auto_detect = True
            self.current_reader = None
        elif game == 'ACC (Shared Memory)':
            self.current_reader = self.acc_reader
        elif game == 'iRacing (SDK)':
            self.current_reader = self.ir_reader
        elif game == 'ELM327 (OBD-II)':
            if self.elm_reader and self.elm_reader.is_connected():
                self.current_reader = self.elm_reader
            else:
                self.current_reader = None
        else:  # 'AC (UDP)'
            if self.ac_reader:
                self.ac_reader.disconnect()
            self.ac_reader = ACUDPReader(self.udp_host.text(), int(self.udp_port.text()))
            self.current_reader = self.ac_reader
        self._sampler.set_reader(self.current_reader)
        self._empty_drain_count = 0

    def _detect_game(self):
        """Priority: ELM327 (real mode) → ACC → iRacing → AC UDP."""
        if self._app_mode == 'real':
            if self.elm_reader and self.elm_reader.is_connected():
                return self.elm_reader
            return None
        if self.acc_reader.is_connected():
            return self.acc_reader
        if self.ir_reader.is_connected():
            return self.ir_reader
        if not self.ac_reader:
            self.ac_reader = ACUDPReader(self.udp_host.text(), int(self.udp_port.text()))
        if self.ac_reader.is_connected():
            return self.ac_reader
        return None

    # ------------------------------------------------------------------
    # TRACK SELECTION / AUTO-DETECT
    # ------------------------------------------------------------------

    def _on_track_changed(self, index: int):
        key = self.track_combo.itemData(index)   # None = Auto-Detect
        self._auto_track = (key is None)
        if key and key in TRACKS:
            self._apply_track(key)

    def _apply_track(self, key: str):
        global MONZA_LENGTH_M
        self._active_track_key = key
        if key in TRACKS:
            self.track_map.set_track(key)
            MONZA_LENGTH_M = TRACKS[key].get('length_m', MONZA_LENGTH_M)
        else:
            # New unknown track – reset to live-build mode
            display = key.replace('_', ' ').title()
            self.track_map.reset_track(display_name=display)
        self._update_track_edit_buttons()

    def _sector_boundaries(self, track_length_m: float) -> list[float]:
        """Return sector boundary distances in metres for the active track.
        Falls back to equal thirds if no real sector data is available."""
        td = TRACKS.get(self._active_track_key or '', {})
        custom = td.get('sector_boundaries')
        if custom:
            return custom
        return [track_length_m * f for f in (1/3, 2/3, 1.0)]

    def _update_track_edit_buttons(self):
        """Disable REC / LOCK SHAPE when the active track is already saved."""
        already_saved = bool(self._active_track_key and self._active_track_key in TRACKS)
        tip = 'Track already saved — delete the JSON to re-record.' if already_saved else ''
        rec = getattr(self, 'rec_btn', None)
        if rec is not None:
            if already_saved and rec.isChecked():
                rec.setChecked(False)
            rec.setEnabled(not already_saved)
            rec.setToolTip(tip)
        lock = getattr(self, '_track_lock_btn', None)
        if lock is not None:
            lock.blockSignals(True)
            lock.setChecked(already_saved)
            lock.blockSignals(False)
            lock.setText('UNLOCK SHAPE' if already_saved else 'LOCK SHAPE')
            lock.setEnabled(not already_saved)
            lock.setToolTip(tip)

    def _auto_detect_track(self, track_name: str):
        if not self._auto_track:
            return
        import re
        # Derive a stable key from whatever string the game reports
        key = re.sub(r'[^a-z0-9_]', '_', track_name.lower()).strip('_')
        key = re.sub(r'_+', '_', key)
        # Also check TRACK_NAME_MAP for any manual overrides
        name_lc = track_name.lower()
        for substr, mapped in TRACK_NAME_MAP.items():
            if substr in name_lc:
                key = mapped
                break
        if key != self._active_track_key:
            self._apply_track(key)

    # ------------------------------------------------------------------
    # TRACK RECORDING
    # ------------------------------------------------------------------

    def _on_track_lock_toggled(self, checked: bool):
        self.track_map._shape_locked = checked
        self._track_lock_btn.setText('UNLOCK SHAPE' if checked else 'LOCK SHAPE')

    def _on_raceline_toggled(self, checked: bool):
        self.track_map.set_show_raceline(checked)
        if hasattr(self, '_rpl_map'):
            self._rpl_map.set_show_raceline(checked)

    def _on_rec_toggled(self, checked: bool):
        if checked:
            self.recorder.start()
            self.rec_label.setText('0 pts')
            self.rec_label.setStyleSheet(f'color: {C_BRAKE};')
        else:
            self.recorder.stop()
            self._finish_recording()

    def _finish_recording(self):
        data = self._sampler.latest
        track_name = data.get('track_name', 'Unknown Track') if data else 'Unknown Track'
        length_m = TRACKS.get(self._active_track_key or '', {}).get('length_m', MONZA_LENGTH_M)

        path = self.recorder.save(track_name, length_m)
        if path:
            load_saved_tracks()
            self._reload_track_combo()
            self._update_track_edit_buttons()
            self.rec_label.setText(f'Saved: {Path(path).stem}')
            self.rec_label.setStyleSheet(f'color: {C_THROTTLE};')
        else:
            n = self.recorder.sample_count
            self.rec_label.setText(f'Too few pts ({n})')
            self.rec_label.setStyleSheet(f'color: {C_ABS};')

    def _reload_track_combo(self):
        self.track_combo.blockSignals(True)
        self.track_combo.clear()
        self.track_combo.addItem('Auto-Detect', userData=None)
        for key, td in TRACKS.items():
            self.track_combo.addItem(td['name'], userData=key)
        self.track_combo.blockSignals(False)

    def _import_trackmap(self):
        """Let the user pick a track JSON file and copy it into the tracks/ directory."""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Import Track Map', '', 'Track JSON files (*.json);;All files (*)')
        if not path:
            return

        import re
        try:
            with open(path) as f:
                td = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, 'Import Failed', f'Could not read file:\n{e}')
            return

        # Validate required fields
        if 'pts' not in td or not isinstance(td.get('pts'), list) or len(td['pts']) < 10:
            QMessageBox.warning(self, 'Import Failed',
                                'Invalid track JSON: missing or too-short "pts" array.')
            return

        # Derive key and name if not already present
        name = td.get('name') or Path(path).stem
        raw_key = td.get('track_key') or name
        track_key = re.sub(r'[^a-z0-9_]', '_', raw_key.lower()).strip('_')
        track_key = re.sub(r'_+', '_', track_key)
        length_m = int(td.get('length_m', 0)) or MONZA_LENGTH_M

        # Normalise pts to [[x, z], ...] — accept both lists and dicts
        raw_pts = td['pts']
        try:
            if isinstance(raw_pts[0], dict):
                pts = [[float(p.get('x', p.get('X', 0))),
                        float(p.get('z', p.get('Z', p.get('y', p.get('Y', 0)))))]
                       for p in raw_pts]
            else:
                pts = [[float(p[0]), float(p[1])] for p in raw_pts]
        except Exception as e:
            QMessageBox.warning(self, 'Import Failed', f'Could not parse pts:\n{e}')
            return

        # Re-normalise coordinates to [0..1] range with padding
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        min_x, max_x = min(xs), max(xs)
        min_z, max_z = min(zs), max(zs)
        span = max(max_x - min_x, max_z - min_z)
        if span > 1.01 or span == 0:
            # Raw world coords — normalise them
            if span == 0:
                QMessageBox.warning(self, 'Import Failed', 'All points are identical.')
                return
            PAD = 0.06
            scale = (1.0 - 2 * PAD) / span
            pts = [[round((p[0] - min_x) * scale + PAD, 4),
                    round((p[1] - min_z) * scale + PAD, 4)] for p in pts]

        out_data = {
            'name': name,
            'track_key': track_key,
            'length_m': length_m,
            'pts': pts,
            'turns': [list(t) for t in td.get('turns', [])],
        }

        out_dir = _get_tracks_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f'{track_key}.json'

        if dest.exists():
            reply = QMessageBox.question(
                self, 'Overwrite?',
                f'A track named "{track_key}" already exists.\nOverwrite it?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        with open(dest, 'w') as f:
            json.dump(out_data, f, indent=2)

        load_saved_tracks()
        self._reload_track_combo()

        # Select the just-imported track
        for i in range(self.track_combo.count()):
            if self.track_combo.itemData(i) == track_key:
                self.track_combo.setCurrentIndex(i)
                break

        QMessageBox.information(self, 'Import Successful',
                                f'Imported "{name}" ({len(pts)} pts)\nSaved to: {dest}')

    # ------------------------------------------------------------------
    # TELEMETRY UPDATE LOOP
    # ------------------------------------------------------------------

    def _anim_tick(self):
        """60 fps animation tick — smooth lerp for car dot, steering, and replay."""
        self.track_map.tick_lerp()
        self._rpl_map.tick_lerp()
        self._rpl_steer.tick_lerp()

        # Replay: advance using wall-clock delta for smooth playback
        if self._replay_playing and self._replay_data:
            now = time.monotonic()
            if self._replay_last_mono > 0:
                dt_ms = (now - self._replay_last_mono) * 1000.0 * self._replay_speed
                new_pos = self._replay_pos_ms + dt_ms
                if new_pos >= self._replay_total_ms:
                    new_pos = self._replay_total_ms
                    self._replay_playing = False
                    self._replay_play_btn.setText('PLAY')
                self._replay_seek(int(new_pos))
            self._replay_last_mono = now

    def _process_sample(self, data: dict):
        """Process a single raw telemetry sample on the main thread."""
        # Lap change detection
        current_lap = data.get('lap_count', 0)
        current_time = data.get('current_time', 0)
        lap_changed = (
            current_lap > self.current_lap_count
            or (current_lap == 0 and self.current_lap_count > 0)
            or (current_time < 5000 and self.last_lap_time > 5000)
        )

        # Outlap detection: pit lane exit during this lap = outlap
        cur_in_pit_lane = data.get('is_in_pit_lane', False)
        _pit_exit_this_tick = self._prev_is_in_pit_lane and not cur_in_pit_lane
        if _pit_exit_this_tick:
            self._current_lap_had_pit_exit = True
            self._tyre_stint_laps = 0
        self._prev_is_in_pit_lane = cur_in_pit_lane

        # Validity latch: once the lap is invalid it stays invalid until next lap
        if not data.get('lap_valid', True):
            self._current_lap_valid = False

        if lap_changed:
            _fuel_now = data.get('fuel', 0.0)
            if self._fuel_at_lap_start is not None and 0 < _fuel_now < self._fuel_at_lap_start:
                self._fuel_per_lap_history.append(self._fuel_at_lap_start - _fuel_now)
            self._strategy_engine._fuel_per_lap_history = list(self._fuel_per_lap_history)
            self._fuel_at_lap_start = _fuel_now
            self._math_engine.on_lap_complete()
            self._store_completed_lap()
            self._current_lap_had_pit_exit = False
            self._current_lap_valid = True
            self._tyre_stint_laps += 1
            self._reset_graphs()
            self._reset_analysis_graphs()
            self._reset_current_lap_data()
            try:
                self._math_engine.on_lap_start({
                    'speed': data.get('speed', 0.0) or 0.0,
                    'throttle': data.get('throttle', 0.0) or 0.0,
                    'brake': data.get('brake', 0.0) or 0.0,
                    'fuel_l': data.get('fuel', 0.0) or 0.0,
                })
            except Exception:
                pass
            display_lap = current_lap if current_lap > 0 else 1
            self.header_lap_label.setText(f'LAP {display_lap}')
            if self.recorder.recording and self.recorder.sample_count >= TrackRecorder.MIN_SAMPLES:
                self.rec_btn.setChecked(False)

        self.current_lap_count = current_lap
        self.last_lap_time = current_time

        # ── Compute lap progress & distance (needed for data recording) ──
        lap_dur_ms = 90000
        if 'lap_dist_pct' in data and data['lap_dist_pct'] > 0:
            lap_progress = float(data['lap_dist_pct'])
        else:
            lap_progress = min(1.0, current_time / lap_dur_ms) if lap_dur_ms > 0 else 0
        _track_length_m = TRACKS.get(self._active_track_key or '', {}).get('length_m', MONZA_LENGTH_M)
        distance_m = lap_progress * _track_length_m

        # ── Track map (lightweight — no Qt paint, just data) ─────────────
        self.track_map.update_telemetry(lap_progress, data.get('throttle', 0.0) or 0.0, data.get('brake', 0.0) or 0.0)
        if self.current_lap_count >= 1 and self._current_lap_valid:
            self.track_map.feed_world_pos(
                lap_progress,
                data.get('world_x', 0.0),
                data.get('world_z', 0.0),
            )

        # Feed recorder
        if self.recorder.recording:
            self.recorder.feed(
                lap_progress,
                data.get('world_x', 0.0),
                data.get('world_z', 0.0),
            )

        # Seed fuel-at-lap-start on first telemetry tick
        fuel = data.get('fuel', 0.0)
        if self._fuel_at_lap_start is None and fuel > 0:
            self._fuel_at_lap_start = fuel

        # ── Store raw lap data ───────────────────────────────────────────
        gear = data.get('gear', 1)
        if gear is None:
            gear = 1
        gear_int = gear if isinstance(gear, int) else 0
        _steer_angle = data.get('steer_angle', 0.0)
        if _steer_angle is None:
            _steer_angle = 0.0
        steer_deg = math.degrees(_steer_angle)
        rpm = data.get('rpm', 0.0)
        if rpm is None:
            rpm = 0.0

        _raw_bias = data.get('brake_bias', 0.0)
        if 0.0 < _raw_bias <= 1.0:
            _bias_pct = _raw_bias * 100.0
        elif 50.0 <= _raw_bias <= 80.0:
            _bias_pct = float(_raw_bias)
        else:
            _bias_pct = 0.0
        _tt = data.get('tyre_temp',     [0.0, 0.0, 0.0, 0.0])
        _tp = data.get('tyre_pressure', [0.0, 0.0, 0.0, 0.0])
        _bt = data.get('brake_temp',    [0.0, 0.0, 0.0, 0.0])
        _tw = data.get('tyre_wear',     [0.0, 0.0, 0.0, 0.0])

        # Grow buffer if full (doubles capacity, amortised O(1) like list.append).
        n = self._lap_n
        if n >= len(self._lap_buf['speed']):
            new_cap = max(n * 2, self._LAP_BUF_INIT)
            for ch in self._LAP_CHANNELS:
                grown = np.empty(new_cap, dtype=np.float32)
                grown[:n] = self._lap_buf[ch]
                self._lap_buf[ch] = grown

        b = self._lap_buf
        b['time_ms'][n]          = current_time
        b['dist_m'][n]           = distance_m
        b['speed'][n]            = data.get('speed', 0.0) or 0.0
        b['throttle'][n]         = data.get('throttle', 0.0) or 0.0
        b['brake'][n]            = data.get('brake', 0.0) or 0.0
        b['steer_deg'][n]        = steer_deg
        b['rpm'][n]              = rpm
        b['gear'][n]             = gear_int
        b['abs'][n]              = data.get('abs', 0.0) or 0.0
        b['tc'][n]               = data.get('tc', 0.0) or 0.0
        b['fuel_l'][n]           = fuel
        b['brake_bias_pct'][n]   = _bias_pct
        b['world_x'][n]          = data.get('world_x', 0.0)
        b['world_z'][n]          = data.get('world_z', 0.0)
        b['air_temp'][n]         = data.get('air_temp', 0.0)
        b['road_temp'][n]        = data.get('road_temp', 0.0)
        b['tyre_temp_fl'][n]     = _tt[0]
        b['tyre_temp_fr'][n]     = _tt[1]
        b['tyre_temp_rl'][n]     = _tt[2]
        b['tyre_temp_rr'][n]     = _tt[3]
        b['tyre_pressure_fl'][n] = _tp[0]
        b['tyre_pressure_fr'][n] = _tp[1]
        b['tyre_pressure_rl'][n] = _tp[2]
        b['tyre_pressure_rr'][n] = _tp[3]
        b['brake_temp_fl'][n]    = _bt[0]
        b['brake_temp_fr'][n]    = _bt[1]
        b['brake_temp_rl'][n]    = _bt[2]
        b['brake_temp_rr'][n]    = _bt[3]
        b['tyre_wear_fl'][n]     = _tw[0]
        b['tyre_wear_fr'][n]     = _tw[1]
        b['tyre_wear_rl'][n]     = _tw[2]
        b['tyre_wear_rr'][n]     = _tw[3]
        self._lap_n = n + 1

        # ── Delta vs reference lap (data part only) ──────────────────────
        if self._ref_lap_dists:
            ref_t = _interp_time_at_dist(self._ref_lap_dists, self._ref_lap_times,
                                         distance_m)
            if ref_t is not None:
                self._current_deltas.append((current_time - ref_t) / 1000.0)

        # Cache session-level metadata for lap storage
        self._last_car_name     = data.get('car_name', self._last_car_name).split('\x00')[0]
        self._last_track_name   = data.get('track_name', self._last_track_name).split('\x00')[0]
        self._last_session_type = data.get('session_type', self._last_session_type)
        self._last_tyre_compound = data.get('tyre_compound', self._last_tyre_compound).split('\x00')[0]
        self._last_air_temp     = data.get('air_temp', self._last_air_temp)
        self._last_road_temp    = data.get('road_temp', self._last_road_temp)

        self._last_known_fuel = fuel
        self._last_gap_ahead  = data.get('gap_ahead', 0)
        self._last_gap_behind = data.get('gap_behind', 0)

        # Cache for the render timer
        self._last_data = data

        # Strategy engine — last call so it sees the freshest state
        import time as _time
        sample_with_synth = dict(data)
        sample_with_synth['_clock_s'] = _time.monotonic()
        sample_with_synth['_pit_exit'] = _pit_exit_this_tick
        self._strategy_engine.update(
            sample_with_synth, self.current_lap_data, self.session_laps)

    def _render_telemetry(self):
        """~5 Hz UI render — drain buffered samples, then update widgets."""
        self._update_title_bar()
        self._update_tab_indicators()
        # ── Phase 1: Drain and process all buffered samples ──
        samples = self._sampler.drain()
        for s in samples:
            self._process_sample(s)

        # The merged Race tab reads engine.state directly inside its
        # update_tick (called below via race_tab.update_tick).

        # ── Phase 2: Connection hysteresis ──
        if samples:
            self._empty_drain_count = 0
        else:
            self._empty_drain_count += 1

        if self._empty_drain_count > 5:          # >1s with no data
            if self.auto_detect:
                detected = self._detect_game()
                self._sampler.set_reader(detected)
                self.current_reader = detected
            if self.current_reader is None:
                self.connection_dot.setStyleSheet('color: #444;')
                self.connection_label.setText('DISCONNECTED')
                self.connection_label.setStyleSheet(f'color: {TEXT_MUTED}; letter-spacing: 0.5px;')
                self._reset_display()
                return

        # ── Phase 3: Render UI from cached data ──
        data = self._last_data
        if data is None:
            return

        if isinstance(self.current_reader, ELM327Reader):
            game_type = 'OBD-II'
        elif isinstance(self.current_reader, ACUDPReader):
            game_type = 'AC'
        elif isinstance(self.current_reader, IRacingReader):
            game_type = 'iRacing'
        else:
            game_type = 'ACC'
        self.connection_dot.setStyleSheet(f'color: {C_THROTTLE};')
        self.connection_label.setText(f'CONNECTED  ·  {game_type}')
        self.connection_label.setStyleSheet(f'color: {TEXT_SECONDARY}; letter-spacing: 0.5px;')

        # Gear text  (all readers normalise to: 0=R, 1=N, 2+=1st,2nd,…)
        gear = data.get('gear', 1)
        if gear is None:
            gear = 1
        if gear == 0:
            gear_text = 'R'
        elif gear == 1:
            gear_text = 'N'
        else:
            gear_text = str(gear - 1)  # 2→1st, 3→2nd, …

        # ── Variables used by graph updates and tab update_tick below ───────
        speed = data.get('speed', 0.0) or 0.0
        rpm = data.get('rpm', 0.0) or 0.0
        throttle = data.get('throttle', 0.0) or 0.0
        brake = data.get('brake', 0.0) or 0.0
        steer_angle = data.get('steer_angle', 0.0) or 0.0
        abs_val = data.get('abs', 0.0) or 0.0
        tc_val = data.get('tc', 0.0) or 0.0
        fuel = data.get('fuel', 0.0)

        car_name = data.get('car_name', '') or ''
        track_name = data.get('track_name', '') or ''
        self.car_label.setText(
            QFontMetrics(self.car_label.font()).elidedText(
                car_name, Qt.TextElideMode.ElideRight, 196))
        self.track_label.setText(
            QFontMetrics(self.track_label.font()).elidedText(
                track_name, Qt.TextElideMode.ElideRight, 236))
        self._auto_detect_track(track_name)

        self.dashboard_tab.update_tick(self._last_data)
        self.race_tab.update_tick(self._last_data)
        self.tyres_tab.update_tick(self._last_data)
        self._update_fuel_save()
        self._update_undercut()

        # Recorder label
        if self.recorder.recording:
            self.rec_label.setText(f'{self.recorder.sample_count} pts')

        # ── Graph updates (only render when visible) ──────────────────────
        steer_deg = math.degrees(steer_angle)
        gear_int = gear if isinstance(gear, int) else 0
        _current_tab = self.tabs.currentIndex()

        if _current_tab == 1:  # TELEMETRY GRAPHS
            self.speed_graph.update_data(speed)
            self.pedals_graph.update_data(throttle, brake)
            self.steering_graph.update_data(steer_deg)
            self.rpm_graph.update_data(rpm)
            self.gear_graph.update_data(gear_int)
            self.aids_graph.update_data(abs_val, tc_val)

        # ── Lap Analysis graphs ──────────────────────────────────────────
        current_time = data.get('current_time', 0)
        lap_dur_ms = 90000
        if 'lap_dist_pct' in data and data['lap_dist_pct'] > 0:
            lap_progress = float(data['lap_dist_pct'])
        else:
            lap_progress = min(1.0, current_time / lap_dur_ms) if lap_dur_ms > 0 else 0
        _track_length_m = TRACKS.get(self._active_track_key or '', {}).get('length_m', MONZA_LENGTH_M)
        distance_m = lap_progress * _track_length_m

        if _current_tab == 2:  # LAP ANALYSIS
            self.ana_speed.update_data(distance_m, speed)
            self.ana_throttle_brake.update_data(distance_m, throttle, brake)
            self.ana_gear.update_data(distance_m, gear_int)
            self.ana_rpm.update_data(distance_m, rpm)
            self.ana_steer.update_data(distance_m, steer_deg)

        # ── Math channel evaluation ────────────────────────────────────────
        _tt = data.get('tyre_temp', [0.0, 0.0, 0.0, 0.0])
        _tp = data.get('tyre_pressure', [0.0, 0.0, 0.0, 0.0])
        _bt = data.get('brake_temp', [0.0, 0.0, 0.0, 0.0])
        _tw = data.get('tyre_wear', [0.0, 0.0, 0.0, 0.0])
        _raw_bias = data.get('brake_bias', 0.0)
        if 0.0 < _raw_bias <= 1.0:
            _bias_pct = round(_raw_bias * 100, 2)
        elif 50.0 <= _raw_bias <= 80.0:
            _bias_pct = round(_raw_bias, 2)
        else:
            _bias_pct = 0.0
        _math_raw = {
            'speed': speed, 'throttle': throttle,
            'brake': brake, 'steer_deg': steer_deg,
            'rpm': float(rpm), 'gear': float(gear_int),
            'abs': abs_val, 'tc': tc_val,
            'fuel_l': data.get('fuel', 0.0), 'brake_bias_pct': _bias_pct,
            'air_temp': data.get('air_temp', 0.0),
            'road_temp': data.get('road_temp', 0.0),
            'tyre_temp_fl': _tt[0], 'tyre_temp_fr': _tt[1],
            'tyre_temp_rl': _tt[2], 'tyre_temp_rr': _tt[3],
            'tyre_pressure_fl': _tp[0], 'tyre_pressure_fr': _tp[1],
            'tyre_pressure_rl': _tp[2], 'tyre_pressure_rr': _tp[3],
            'brake_temp_fl': _bt[0], 'brake_temp_fr': _bt[1],
            'brake_temp_rl': _bt[2], 'brake_temp_rr': _bt[3],
            'tyre_wear_fl': _tw[0], 'tyre_wear_fr': _tw[1],
            'tyre_wear_rl': _tw[2], 'tyre_wear_rr': _tw[3],
        }
        self._math_engine.set_raw_channels(set(_math_raw.keys()))
        try:
            _math_vals = self._math_engine.evaluate(_math_raw, time.monotonic())
            if _current_tab == 1:  # TELEMETRY GRAPHS
                self._update_math_graphs(_math_vals)
        except Exception:
            pass  # never crash the tick loop for math channels

        # ── Delta graph render ───────────────────────────────────────────
        _lap_snap = self.current_lap_data  # snapshot once — property rebuilds dict each call
        if self._ref_lap_dists:
            if _current_tab == 2:  # LAP ANALYSIS
                n_d = min(len(_lap_snap['dist_m']), len(self._current_deltas))
                self.time_delta_graph.update_data(
                    _lap_snap['dist_m'][:n_d],
                    self._current_deltas[:n_d],
                    distance_m)
        elif _current_tab == 2:
            self.time_delta_graph.update_data([], [], distance_m)

        # ── Sector panel ─────────────────────────────────────────────────
        current_time_s = current_time / 1000.0
        if self._ref_lap_time_s > 0:
            boundaries = self._sector_boundaries(_track_length_m)
            ref_secs = _compute_sector_times(
                self._ref_lap_dists, self._ref_lap_times, boundaries)
            cur_secs = _compute_sector_times(
                _lap_snap['dist_m'],
                _lap_snap['time_ms'], boundaries)
            self.sector_panel.update_laps(current_time_s, self._ref_lap_time_s,
                                          ref_secs, cur_secs)
        else:
            self.sector_panel.update_current_time(current_time_s)

    # ------------------------------------------------------------------
    # GRAPH RESET
    # ------------------------------------------------------------------

    def _toggle_math_panel(self, checked: bool) -> None:
        if checked:
            # Only add to the splitter the first time — subsequent toggles
            # just show the existing widget. Re-adding creates duplicate
            # slots that stretch the right side of the splitter.
            if self._math_panel.parent() is not self._graphs_splitter:
                self._graphs_splitter.addWidget(self._math_panel)
            self._math_panel.show()
            self._math_panel.rebuild_list()
        else:
            self._math_panel.hide()

    def _sync_math_graphs(self) -> None:
        """Ensure a live graph widget exists for each visible math channel."""
        visible = {
            ch.name: ch for ch in self._math_engine.get_all_channels()
            if ch.visible
        }
        # Remove graphs for channels no longer visible
        for name in list(self._math_graph_widgets):
            if name not in visible:
                hdr, graph = self._math_graph_widgets.pop(name)
                hdr.setParent(None)
                hdr.deleteLater()
                graph.setParent(None)
                graph.deleteLater()

        # Add graphs for newly visible channels
        for name, ch in visible.items():
            if name not in self._math_graph_widgets:
                hdr = _channel_header(ch.color, name.upper(), ch.unit)
                graph = ChannelGraph(ch.color, ch.unit)
                self._math_graphs_container.addWidget(hdr)
                self._math_graphs_container.addWidget(graph)
                self._math_graphs_container.addWidget(h_line())
                self._math_graph_widgets[name] = (hdr, graph)

    def _update_math_graphs(self, values: dict[str, float]) -> None:
        """Push new math channel values into their live graph widgets."""
        for name, (_, graph) in self._math_graph_widgets.items():
            if name in values:
                graph.update_data(values[name])

    def _reset_graphs(self):
        self.speed_graph.clear()
        self.pedals_graph.clear()
        self.steering_graph.clear()
        self.rpm_graph.clear()
        self.gear_graph.clear()
        self.aids_graph.clear()
        for _, graph in self._math_graph_widgets.values():
            graph.clear()

    def _reset_analysis_graphs(self):
        self.ana_speed.clear()
        self.ana_throttle_brake.clear()
        self.ana_gear.clear()
        self.ana_rpm.clear()
        self.ana_steer.clear()
        self.time_delta_graph.clear()

    # ------------------------------------------------------------------
    # EXPORT
    # ------------------------------------------------------------------

    def _get_last_lap_data(self):
        if self.session_laps:
            return self.session_laps[-1]['data']
        return self.current_lap_data

    def _get_session_data(self):
        snap = self.current_lap_data
        combined = {k: [] for k in snap}
        for lap in self.session_laps:
            for key in combined:
                combined[key].extend(lap['data'].get(key, []))
        for key in combined:
            arr = snap.get(key)
            if arr is not None and len(arr) > 0:
                combined[key].extend(arr.tolist())
        return combined

    def _export_graphs(self, data_dict: dict, dialog_title: str, default_filename: str):
        if not data_dict.get('speed'):
            QMessageBox.information(self, 'Export', 'No telemetry data available to export yet.')
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, dialog_title, default_filename, 'PNG Image (*.png);;All Files (*)')
        if not file_path:
            return

        time_ms = data_dict.get('time_ms', [])
        if time_ms:
            start = time_ms[0]
            x_values = [(t - start) / 1000.0 for t in time_ms]
            x_label = 'Time (s)'
        else:
            x_values = list(range(len(data_dict['speed'])))
            x_label = 'Samples'

        export_fig = Figure(figsize=(12, 9), facecolor=BG)
        axs = export_fig.subplots(3, 2, sharex=True)
        axs = axs.flatten()

        def style_export_ax(ax, title):
            ax.set_facecolor(SURFACE)
            ax.set_title(title, color=TEXT_MUTED, fontsize=10, pad=4)
            ax.tick_params(colors=TEXT_MUTED, labelsize=7)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#303030')
            ax.spines['bottom'].set_color('#303030')
            ax.grid(True, color='#1c1c1c', linewidth=0.8, linestyle='-', axis='y')

        style_export_ax(axs[0], 'Speed')
        axs[0].plot(x_values, data_dict['speed'], color=C_SPEED, linewidth=1.0)
        axs[0].set_ylabel('km/h', color=TEXT_MUTED, fontsize=8)

        style_export_ax(axs[1], 'Throttle & Brake')
        axs[1].plot(x_values, data_dict['throttle'], color=C_THROTTLE, linewidth=1.0, label='Throttle')
        axs[1].plot(x_values, data_dict['brake'], color=C_BRAKE, linewidth=1.0, label='Brake')
        axs[1].set_ylabel('%', color=TEXT_MUTED, fontsize=8)
        axs[1].legend(loc='upper right', fontsize=7, framealpha=0, labelcolor=TEXT_MUTED)

        style_export_ax(axs[2], 'Steering Angle')
        axs[2].plot(x_values, data_dict['steer_deg'], color=C_STEER, linewidth=1.0)
        axs[2].set_ylabel('°', color=TEXT_MUTED, fontsize=8)

        style_export_ax(axs[3], 'RPM')
        axs[3].plot(x_values, data_dict['rpm'], color=C_RPM, linewidth=1.0)
        axs[3].set_ylabel('rpm', color=TEXT_MUTED, fontsize=8)

        style_export_ax(axs[4], 'Gear')
        axs[4].step(x_values, data_dict['gear'], color=C_GEAR, linewidth=1.0, where='post')
        axs[4].set_ylabel('gear', color=TEXT_MUTED, fontsize=8)

        style_export_ax(axs[5], 'ABS & TC Activity')
        axs[5].plot(x_values, data_dict['abs'], color=C_ABS, linewidth=1.0, label='ABS')
        axs[5].plot(x_values, data_dict['tc'], color=C_TC, linewidth=1.0, label='TC')
        axs[5].set_ylabel('activity', color=TEXT_MUTED, fontsize=8)
        axs[5].legend(loc='upper right', fontsize=7, framealpha=0, labelcolor=TEXT_MUTED)

        for ax in axs[4:]:
            ax.set_xlabel(x_label, color=TEXT_MUTED, fontsize=8)

        export_fig.tight_layout(pad=0.5)
        export_fig.savefig(file_path, dpi=150, facecolor=BG)
        QMessageBox.information(self, 'Export', f'Graphs saved to:\n{file_path}')

    def closeEvent(self, event):
        self._sampler.stop()
        self._sampler.join(timeout=1.0)
        super().closeEvent(event)

    def export_last_lap_graphs(self):
        self._export_graphs(self._get_last_lap_data(), 'Save Last Lap Graphs', 'last_lap.png')

    def export_session_graphs(self):
        self._export_graphs(self._get_session_data(), 'Save Full Session Graphs', 'session.png')

    # ------------------------------------------------------------------
    # DISPLAY RESET
    # ------------------------------------------------------------------

    def _reset_display(self):
        self.car_label.setText('—')
        self.track_label.setText('—')
        self.dashboard_tab.update_tick(None)
        self.race_tab.update_tick(None)
        self.tyres_tab.update_tick(None)
        self.strategy_tab._pit_rec_lbl.setText('—')
        self.strategy_tab._pit_rec_lbl.setStyleSheet(f'color: {TEXT_MUTED}; letter-spacing: 1px;')
        self.strategy_tab._pit_fuel_laps_lbl.setText('—')
        self.strategy_tab._pit_tyre_stint_lbl.setText('—')
        self.strategy_tab._pit_tyre_cond_lbl.setText('—')
        self.strategy_tab._pit_no_data_lbl.setVisible(True)
        self.strategy_tab._fs_result_lbl.setText('—')
        self.strategy_tab._fs_result_lbl.setStyleSheet(f'color: {TEXT_MUTED};')
        self.strategy_tab._uco_undercut_lbl.setText('UNDERCUT: —')
        self.strategy_tab._uco_undercut_lbl.setStyleSheet(f'color: {TEXT_MUTED};')
        self.strategy_tab._uco_overcut_lbl.setText('OVERCUT: —')
        self.strategy_tab._uco_overcut_lbl.setStyleSheet(f'color: {TEXT_MUTED};')
        self._reset_analysis_graphs()
        self.track_map.reset()


# ---------------------------------------------------------------------------
# SMALL HELPER WIDGETS
# ---------------------------------------------------------------------------

