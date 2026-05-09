"""Telemetry Graphs tab — rolling per-channel graphs.

Roomy bucket. Channel toggles render as a horizontal row of Pill widgets;
clicking a pill toggles its tone between 'neutral' (off) and 'violet' (on).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QSplitter, QPushButton,
    QSizePolicy,
)

from ... import theme
from ...constants import (
    C_SPEED, C_THROTTLE, C_BRAKE, C_RPM, C_GEAR, C_STEER, C_ABS, C_TC,
    sans,
)
from ...theme import (
    SURFACE_HOVER, BORDER_STRONG, TEXT_MUTED, TEXT_PRIMARY,
    ACCENT_BG, ACCENT_BORDER, ACCENT_FG,
    SURFACE_RAISED, TEXT_SECONDARY, BG,
)
from ...utils import h_line, _channel_header
from ..primitives import Card, Pill
from ..graphs import ChannelGraph, MultiChannelGraph

# Aliases matching legacy app.py shorthand
BG3 = SURFACE_HOVER
BORDER2 = BORDER_STRONG
TXT2 = TEXT_MUTED
WHITE = TEXT_PRIMARY


class _ChannelTogglePill(Pill):
    """Pill that toggles its tone on click and reports state via callback."""

    def __init__(self, channel_id: str, label: str, on_toggle, *,
                 active: bool = True, parent=None):
        super().__init__(label, tone=('violet' if active else 'neutral'), parent=parent)
        self._cid = channel_id
        self._on = on_toggle
        self._active = active
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def is_active(self) -> bool:
        return self._active

    def mousePressEvent(self, ev):
        self._active = not self._active
        bg, border, fg = (
            (ACCENT_BG, ACCENT_BORDER, ACCENT_FG)
            if self._active
            else (SURFACE_RAISED, BORDER_STRONG, TEXT_SECONDARY)
        )
        self.setStyleSheet(
            f'background:{bg}; color:{fg}; border:1px solid {border};'
            f'border-radius:{theme.RADIUS["sm"]}px; padding:2px 7px;'
            f'letter-spacing:0.3px;'
        )
        self._on(self._cid, self._active)
        super().mousePressEvent(ev)


class TelemetryTab(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        # ── Top action row: math-channel toggle ───────────────────────────
        controls_card = Card(dense=True)
        controls_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        _math_btn_style = (
            f'QPushButton {{ background: {BG3}; color: {TXT2}; border: 1px solid {BORDER2};'
            f' border-radius: 4px; padding: 5px 12px; font-size: 10px; letter-spacing: 0.5px; }}'
            f'QPushButton:hover {{ color: {C_SPEED}; border-color: {C_SPEED}; }}'
            f'QPushButton:checked {{ color: {C_SPEED}; border-color: {C_SPEED}; background: #0d2a3a; }}'
        )
        self._math_toggle_btn = QPushButton('\U0001f9ee  MATH CHANNELS')
        self._math_toggle_btn.setFont(sans(8, bold=True))
        self._math_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._math_toggle_btn.setStyleSheet(_math_btn_style)
        self._math_toggle_btn.setCheckable(True)
        self._math_toggle_btn.setToolTip('Open the math channel manager')
        self._math_toggle_btn.toggled.connect(app._toggle_math_panel)
        btn_row.addWidget(self._math_toggle_btn)

        btn_row.addStretch()

        controls_card.body().addLayout(btn_row)
        outer.addWidget(controls_card, 0)  # no stretch — natural height

        # Mirror math toggle button on app so _toggle_math_panel state checks work
        app._math_toggle_btn = self._math_toggle_btn

        # ── Graphs area: scrollable graphs + optional math panel splitter ─
        self._graphs_splitter = QSplitter(Qt.Orientation.Horizontal)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')
        container = QWidget()
        container.setStyleSheet(f'background: {BG};')
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(4, 8, 4, 8)
        vbox.setSpacing(10)
        scroll.setWidget(container)

        self._graphs_splitter.addWidget(scroll)
        outer.addWidget(self._graphs_splitter, 1)  # take all remaining space

        # ── Speed graph ─────────────────────────────────────────────────
        self.speed_graph_title = _channel_header(C_SPEED, 'SPEED', 'km/h')
        vbox.addWidget(self.speed_graph_title)
        self.speed_graph = ChannelGraph(C_SPEED, 'km/h', ylim=(0, 300))
        vbox.addWidget(self.speed_graph)
        vbox.addWidget(h_line())

        # ── Throttle & Brake graph ───────────────────────────────────────
        self.pedals_graph_title = _channel_header(C_THROTTLE, 'THROTTLE & BRAKE', '%')
        vbox.addWidget(self.pedals_graph_title)
        self.pedals_graph = MultiChannelGraph(
            C_THROTTLE, C_BRAKE, '%', 'Throttle', 'Brake', ylim=(0, 100))
        vbox.addWidget(self.pedals_graph)
        vbox.addWidget(h_line())

        # ── Steering graph ───────────────────────────────────────────────
        self.steering_graph_title = _channel_header(C_STEER, 'STEERING', '°')
        vbox.addWidget(self.steering_graph_title)
        self.steering_graph = ChannelGraph(C_STEER, '°', ylim=(-540, 540))
        vbox.addWidget(self.steering_graph)
        vbox.addWidget(h_line())

        # ── RPM graph ────────────────────────────────────────────────────
        self.rpm_graph_title = _channel_header(C_RPM, 'RPM', 'rpm')
        vbox.addWidget(self.rpm_graph_title)
        self.rpm_graph = ChannelGraph(C_RPM, 'rpm', ylim=(0, 10000))
        vbox.addWidget(self.rpm_graph)
        vbox.addWidget(h_line())

        # ── Gear graph ───────────────────────────────────────────────────
        self.gear_graph_title = _channel_header(C_GEAR, 'GEAR', '')
        vbox.addWidget(self.gear_graph_title)
        self.gear_graph = ChannelGraph(C_GEAR, 'gear', ylim=(-1, 8))
        vbox.addWidget(self.gear_graph)
        vbox.addWidget(h_line())

        # ── ABS / TC graph ───────────────────────────────────────────────
        self.aids_graph_title = _channel_header(C_ABS, 'ABS / TC', '')
        vbox.addWidget(self.aids_graph_title)
        self.aids_graph = MultiChannelGraph(
            C_ABS, C_TC, 'activity', 'ABS', 'TC', ylim=(0, 10))
        vbox.addWidget(self.aids_graph)

        # ── Math channel graphs placeholder ─────────────────────────────
        self._math_graphs_container = QVBoxLayout()
        vbox.addLayout(self._math_graphs_container)
        self._math_graph_widgets: dict[str, tuple[QWidget, ChannelGraph]] = {}

        # Mirror all chart-widget attributes onto app so legacy render code
        # (self.speed_graph.update_data etc. in _render_telemetry) keeps working
        app.speed_graph_title = self.speed_graph_title
        app.speed_graph = self.speed_graph
        app.pedals_graph_title = self.pedals_graph_title
        app.pedals_graph = self.pedals_graph
        app.steering_graph_title = self.steering_graph_title
        app.steering_graph = self.steering_graph
        app.rpm_graph_title = self.rpm_graph_title
        app.rpm_graph = self.rpm_graph
        app.gear_graph_title = self.gear_graph_title
        app.gear_graph = self.gear_graph
        app.aids_graph_title = self.aids_graph_title
        app.aids_graph = self.aids_graph
        app._math_graphs_container = self._math_graphs_container
        app._math_graph_widgets = self._math_graph_widgets
        app._graphs_splitter = self._graphs_splitter

    def update_tick(self, data: dict | None) -> None:
        # Per-tick graph updates are handled by mirrored attributes on app
        # (self.speed_graph etc.) that are updated directly in _render_telemetry.
        # This stub exists for API consistency with other tab widgets.
        pass
