"""Session tab — stats bar, full lap history table, per-lap JSON export, CSV export.

Roomy bucket (dense=False). The layout is lifted verbatim from
``TelemetryApp._build_session_tab`` / ``_refresh_session_tab`` in app.py.
Per-lap mini-sparklines are NOT in scope for this task (deferred).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QPushButton, QScrollArea, QSizePolicy,
    QToolButton, QMenu,
)

from ...constants import C_PURPLE, C_PURPLE_BG, C_THROTTLE, C_BRAKE, mono, sans
from ...theme import (
    SURFACE_RAISED, SURFACE_HOVER, BORDER_SUBTLE, BORDER_STRONG,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
)
from ...utils import h_line

# Legacy shorthand aliases (mirrors app.py module-level block)
BG2     = SURFACE_RAISED
BG3     = SURFACE_HOVER
BORDER  = BORDER_SUBTLE
BORDER2 = BORDER_STRONG
TXT     = TEXT_SECONDARY
TXT2    = TEXT_MUTED
WHITE   = TEXT_PRIMARY


class SessionTab(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # ── Stats bar ─────────────────────────────────────────────────────
        self._sess_stats_card = QFrame()
        self._sess_stats_card.setStyleSheet(
            f'background: {BG2}; border: 1px solid {BORDER}; border-radius: 6px;')
        stats_row = QHBoxLayout(self._sess_stats_card)
        stats_row.setContentsMargins(18, 10, 18, 10)
        stats_row.setSpacing(0)

        def _stat_chip(label_text, value_text, color=TXT):
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = QLabel(label_text)
            lbl.setFont(sans(7, bold=True))
            lbl.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
            val = QLabel(value_text)
            val.setFont(mono(11, bold=True))
            val.setStyleSheet(f'color: {color};')
            col.addWidget(lbl)
            col.addWidget(val)
            return col, val

        sep_v = lambda: (lambda f: (f.setFrameShape(QFrame.Shape.VLine),
                                    f.setStyleSheet(f'color: {BORDER2};'),
                                    f.setFixedWidth(1),
                                    f)[-1])(QFrame())

        c1, self._sess_lbl_count = _stat_chip('LAPS', '0', TXT)
        c2, self._sess_lbl_best  = _stat_chip('BEST LAP', '—:——.———', C_PURPLE)
        c3, self._sess_lbl_avg   = _stat_chip('AVG LAP', '—:——.———', TXT)
        c4, self._sess_lbl_gap   = _stat_chip('BEST → AVG', '—', TXT2)

        for i, (col, _) in enumerate([(c1, None), (c2, None),
                                       (c3, None), (c4, None)]):
            stats_row.addLayout(col)
            if i < 3:
                stats_row.addSpacing(28)
                stats_row.addWidget(sep_v())
                stats_row.addSpacing(28)
        stats_row.addStretch()

        _action_btn_style = (
            f'QToolButton {{ background: {BG3}; color: {TXT};'
            f' border: 1px solid {BORDER2}; border-radius: 4px;'
            f' padding: 8px 18px; letter-spacing: 1px; }}'
            f'QToolButton::menu-indicator {{ image: none; width: 0px; }}'
            f'QToolButton:hover {{ border-color: {C_PURPLE}; }}'
        )
        _menu_style = (
            f'QMenu {{ background: {BG2}; color: {TXT};'
            f' border: 1px solid {BORDER2}; padding: 4px; }}'
            f'QMenu::item {{ padding: 6px 16px; }}'
            f'QMenu::item:selected {{ background: {BG3}; color: {WHITE}; }}'
        )

        # Import session button — load every lap from a session JSON
        import_btn = QToolButton()
        import_btn.setText('⤒  IMPORT')
        import_btn.setFont(sans(8, bold=True))
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        import_btn.setStyleSheet(_action_btn_style)
        import_btn.setToolTip('Load every lap from a previously exported session JSON')
        import_btn.clicked.connect(self._app._import_replay_session_json)
        stats_row.addWidget(import_btn)
        stats_row.addSpacing(8)

        # Export menu (CSV or JSON for the whole session)
        export_btn = QToolButton()
        export_btn.setText('⤓  EXPORT')
        export_btn.setFont(sans(8, bold=True))
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        export_btn.setStyleSheet(_action_btn_style)
        menu = QMenu(export_btn)
        menu.setStyleSheet(_menu_style)
        menu.addAction('Export as CSV', self._app._export_csv)
        menu.addAction('Export as JSON', self._app._export_session_to_json)
        export_btn.setMenu(menu)
        stats_row.addWidget(export_btn)

        outer.addWidget(self._sess_stats_card)

        # ── Column headers ─────────────────────────────────────────────────
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet('background: transparent;')
        hdr_layout = QHBoxLayout(hdr_frame)
        hdr_layout.setContentsMargins(10, 4, 10, 4)
        hdr_layout.setSpacing(0)
        for txt, stretch, align, min_w in [
            ('#',        0, Qt.AlignmentFlag.AlignCenter, 32),
            ('LAP TIME', 2, Qt.AlignmentFlag.AlignCenter, 80),
            ('S1',       1, Qt.AlignmentFlag.AlignCenter, 50),
            ('S2',       1, Qt.AlignmentFlag.AlignCenter, 50),
            ('S3',       1, Qt.AlignmentFlag.AlignCenter, 50),
            ('SAMPLES',  1, Qt.AlignmentFlag.AlignCenter, 70),
            ('VALID',    0, Qt.AlignmentFlag.AlignCenter, 56),
            ('',         0, Qt.AlignmentFlag.AlignCenter, 36),
        ]:
            l = QLabel(txt)
            l.setFont(sans(7, bold=True))
            l.setStyleSheet(f'color: {TXT2}; letter-spacing: 0.8px;')
            l.setAlignment(align)
            l.setMinimumWidth(min_w)
            l.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            hdr_layout.addWidget(l, stretch)
        outer.addWidget(hdr_frame)
        outer.addWidget(h_line())

        # ── Scrollable rows ────────────────────────────────────────────────
        self._sess_rows_widget = QWidget()
        self._sess_rows_widget.setStyleSheet('background: transparent;')
        self._sess_rows_layout = QVBoxLayout(self._sess_rows_widget)
        self._sess_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._sess_rows_layout.setSpacing(3)
        self._sess_rows_layout.addStretch()

        sess_scroll = QScrollArea()
        sess_scroll.setWidgetResizable(True)
        sess_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sess_scroll.setWidget(self._sess_rows_widget)
        sess_scroll.setStyleSheet(
            'QScrollArea { border: none; background: transparent; }')
        outer.addWidget(sess_scroll, stretch=1)

        # Empty-state label lives outside the rows layout so the clear loop
        # never deletes it.
        self._sess_empty_lbl = QLabel('No completed laps yet.')
        self._sess_empty_lbl.setFont(sans(10))
        self._sess_empty_lbl.setStyleSheet(f'color: {TXT2};')
        self._sess_empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._sess_empty_lbl)

        # Mirror session attributes onto app so the existing lap-completion
        # handler (_refresh_session_tab) keeps targeting these widgets.
        self._app._sess_stats_card  = self._sess_stats_card
        self._app._sess_lbl_count   = self._sess_lbl_count
        self._app._sess_lbl_best    = self._sess_lbl_best
        self._app._sess_lbl_avg     = self._sess_lbl_avg
        self._app._sess_lbl_gap     = self._sess_lbl_gap
        self._app._sess_rows_widget = self._sess_rows_widget
        self._app._sess_rows_layout = self._sess_rows_layout
        self._app._sess_empty_lbl   = self._sess_empty_lbl

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Rebuild all rows from app.session_laps (delegated to app handler)."""
        self._app._refresh_session_tab()

    def update_tick(self, data: dict | None) -> None:
        # Session history updates only on lap completion, not per-tick.
        pass
