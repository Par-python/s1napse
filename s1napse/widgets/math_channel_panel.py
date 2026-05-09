"""Math Channel Manager side panel.

Displays the list of math channels (user-defined + built-in), a status bar
with eval timing, and hosts the inline formula editor for add/edit/view.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QCheckBox, QMessageBox, QSizePolicy,
)

from ..constants import (
    C_SPEED, mono, sans,
)
from ..theme import (
    BG, SURFACE_RAISED as BG2, SURFACE_HOVER as BG3,
    BORDER_SUBTLE as BORDER, BORDER_STRONG as BORDER2,
    TEXT_SECONDARY as TXT, TEXT_MUTED as TXT2, TEXT_PRIMARY as WHITE,
)
from .math_formula_editor import FormulaEditorWidget


# ---------------------------------------------------------------------------
# Channel row widget
# ---------------------------------------------------------------------------

class _ChannelRow(QFrame):
    """One row in the channel list."""

    toggled = pyqtSignal(str, bool)       # name, visible
    edit_requested = pyqtSignal(str)       # name
    duplicate_requested = pyqtSignal(str)  # name
    delete_requested = pyqtSignal(str)     # name

    def __init__(self, name: str, formula: str, unit: str, color: str,
                 value: float, visible: bool, built_in: bool,
                 description: str, parent=None):
        super().__init__(parent)
        self.channel_name = name
        self._built_in = built_in
        # Scope the styled box to this row so child widgets don't inherit
        # the BG2 fill (which painted as a black rectangle behind every label).
        self.setObjectName('ChannelRow')
        self.setStyleSheet(
            f'#ChannelRow {{ background: {BG2}; border: 1px solid {BORDER};'
            f' border-radius: 6px; }}'
            f'#ChannelRow QLabel {{ background: transparent; border: none; }}'
            f'#ChannelRow QCheckBox {{ background: transparent; border: none; }}'
        )
        self.setFixedHeight(68)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(3)

        # Top row: checkbox + color + name + value + unit
        top = QHBoxLayout()
        top.setSpacing(8)

        self._vis_cb = QCheckBox()
        self._vis_cb.setChecked(visible)
        self._vis_cb.setToolTip('Show on graphs')
        self._vis_cb.toggled.connect(lambda v: self.toggled.emit(name, v))
        top.addWidget(self._vis_cb)

        swatch = QLabel('\u25cf')
        swatch.setFont(sans(13))
        swatch.setStyleSheet(f'color: {color};')
        swatch.setFixedWidth(14)
        top.addWidget(swatch)

        name_lbl = QLabel(name)
        name_lbl.setFont(sans(10, bold=True))
        name_lbl.setStyleSheet(f'color: {WHITE}; letter-spacing: 0.4px;')
        top.addWidget(name_lbl)

        top.addStretch()

        self._val_label = QLabel(f'{value:.3f}')
        self._val_label.setFont(mono(11, bold=True))
        self._val_label.setStyleSheet(f'color: {WHITE};')
        self._val_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self._val_label)

        unit_lbl = QLabel(unit)
        unit_lbl.setFont(sans(8))
        unit_lbl.setStyleSheet(f'color: {TXT2};')
        unit_lbl.setFixedWidth(32)
        unit_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(unit_lbl)

        layout.addLayout(top)

        # Bottom row: formula + action buttons
        bot = QHBoxLayout()
        bot.setSpacing(6)

        formula_lbl = QLabel(formula)
        formula_lbl.setFont(mono(9))
        formula_lbl.setStyleSheet(f'color: {TXT2};')
        formula_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        bot.addWidget(formula_lbl, stretch=1)

        btn_style = (
            f'QPushButton {{ background: transparent; color: {TXT2};'
            f' border: none; font-size: 10px; padding: 2px 6px;'
            f' letter-spacing: 0.3px; }}'
            f'QPushButton:hover {{ color: {WHITE}; }}'
        )

        if built_in:
            view_btn = QPushButton('View')
            view_btn.setStyleSheet(btn_style)
            view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            view_btn.clicked.connect(lambda: self.edit_requested.emit(name))
            bot.addWidget(view_btn)
        else:
            edit_btn = QPushButton('Edit')
            edit_btn.setStyleSheet(btn_style)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.clicked.connect(lambda: self.edit_requested.emit(name))
            bot.addWidget(edit_btn)

        dup_btn = QPushButton('Dup')
        dup_btn.setStyleSheet(btn_style)
        dup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        dup_btn.clicked.connect(lambda: self.duplicate_requested.emit(name))
        bot.addWidget(dup_btn)

        if not built_in:
            del_btn = QPushButton('Del')
            del_btn.setStyleSheet(
                f'QPushButton {{ background: transparent; color: {TXT2}; '
                f'border: none; font-size: 9px; padding: 2px 6px; }}'
                f'QPushButton:hover {{ color: #ff3232; }}'
            )
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(lambda: self.delete_requested.emit(name))
            bot.addWidget(del_btn)

        layout.addLayout(bot)

        if description:
            self.setToolTip(description)

    def set_value(self, val: float) -> None:
        self._val_label.setText(f'{val:.3f}')


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

class MathChannelPanel(QWidget):
    """Side panel for the Math Channel Manager.

    Signals
    -------
    visibility_changed(str, bool)
        Channel name, new visibility.  The app should update graph display.
    channels_changed()
        Emitted after add/edit/delete so the app can refresh graph selectors.
    """

    visibility_changed = pyqtSignal(str, bool)
    channels_changed = pyqtSignal()

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._rows: dict[str, _ChannelRow] = {}
        self._mode = 'list'  # 'list' | 'editor'

        self.setFixedWidth(340)
        self.setStyleSheet(f'background: {BG};')

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(8, 8, 8, 8)
        self._root_layout.setSpacing(6)

        # -- Header --
        hdr = QHBoxLayout()
        title = QLabel('MATH CHANNELS')
        title.setFont(sans(9, bold=True))
        title.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        hdr.addWidget(title)
        hdr.addStretch()
        close_btn = QPushButton('\u2715')
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            f'QPushButton {{ background: transparent; color: {TXT2}; border: none; font-size: 14px; }}'
            f'QPushButton:hover {{ color: {WHITE}; }}'
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        hdr.addWidget(close_btn)
        self._root_layout.addLayout(hdr)

        # -- Stacked: list view & editor view --
        self._list_widget = QWidget()
        self._editor_widget = FormulaEditorWidget(engine)

        self._build_list_view()
        self._root_layout.addWidget(self._list_widget)
        self._root_layout.addWidget(self._editor_widget)
        self._editor_widget.hide()

        self._editor_widget.saved.connect(self._on_editor_saved)
        self._editor_widget.cancelled.connect(self._show_list)

        # -- Status bar --
        self._status = QLabel()
        self._status.setFont(sans(8))
        self._status.setStyleSheet(f'color: {TXT2};')
        self._root_layout.addWidget(self._status)

        # Refresh timer (live values + status)
        self._refresh_timer = QTimer()
        self._refresh_timer.setInterval(250)
        self._refresh_timer.timeout.connect(self._refresh_values)

    # ------------------------------------------------------------------
    # List view
    # ------------------------------------------------------------------

    def _build_list_view(self):
        layout = QVBoxLayout(self._list_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Add button
        add_btn = QPushButton('+ Add Channel')
        add_btn.setFont(sans(10, bold=True))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(
            f'QPushButton {{ background: {BG3}; color: {C_SPEED}; '
            f'border: 1px solid {C_SPEED}44; border-radius: 4px; padding: 7px; }}'
            f'QPushButton:hover {{ border-color: {C_SPEED}; background: #0d2a3a; }}'
        )
        add_btn.clicked.connect(self._on_add_new)
        layout.addWidget(add_btn)

        # Scrollable channel list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')

        self._list_container = QWidget()
        self._list_container.setStyleSheet(f'background: {BG};')
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_container)
        layout.addWidget(scroll)

    def rebuild_list(self) -> None:
        """Rebuild the channel list from the engine state."""
        # Clear existing rows
        for row in self._rows.values():
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()

        # Remove all items from layout (labels, stretches, rows)
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        channels = self._engine.get_all_channels()
        user_channels = [c for c in channels if not c.built_in]
        builtin_channels = [c for c in channels if c.built_in]
        vals = self._engine._last_values

        if user_channels:
            lbl = QLabel('YOUR CHANNELS')
            lbl.setFont(sans(8, bold=True))
            lbl.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
            self._list_layout.addWidget(lbl)
            for ch in user_channels:
                row = self._make_row(ch, vals.get(ch.name, 0.0))
                self._list_layout.addWidget(row)
                self._rows[ch.name] = row

        if builtin_channels:
            lbl2 = QLabel('BUILT-IN')
            lbl2.setFont(sans(8, bold=True))
            lbl2.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px; margin-top: 8px;')
            self._list_layout.addWidget(lbl2)
            for ch in builtin_channels:
                row = self._make_row(ch, vals.get(ch.name, 0.0))
                self._list_layout.addWidget(row)
                self._rows[ch.name] = row

        self._list_layout.addStretch()

    def _make_row(self, ch, value: float) -> _ChannelRow:
        row = _ChannelRow(
            name=ch.name, formula=ch.formula, unit=ch.unit,
            color=ch.color, value=value, visible=ch.visible,
            built_in=ch.built_in, description=ch.description,
        )
        row.toggled.connect(self._on_visibility_toggle)
        row.edit_requested.connect(self._on_edit)
        row.duplicate_requested.connect(self._on_duplicate)
        row.delete_requested.connect(self._on_delete)
        return row

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_add_new(self) -> None:
        self._editor_widget.reset()
        self._show_editor()

    def _on_edit(self, name: str) -> None:
        ch = self._engine.channels.get(name)
        if ch is None:
            return
        self._editor_widget.reset()
        self._editor_widget.load_channel(
            name=ch.name, formula=ch.formula, unit=ch.unit,
            color=ch.color, description=ch.description,
            read_only=ch.built_in,
        )
        self._show_editor()

    def _on_duplicate(self, name: str) -> None:
        ch = self._engine.channels.get(name)
        if ch is None:
            return
        # Find a unique copy name
        base = f'{name}_copy'
        copy_name = base
        i = 2
        while copy_name in self._engine.channels or copy_name in self._engine._raw_channel_names:
            copy_name = f'{base}{i}'
            i += 1
        self._editor_widget.reset()
        self._editor_widget.load_channel(
            name='', formula=ch.formula, unit=ch.unit,
            color=ch.color, description=ch.description,
            read_only=False,
        )
        # Pre-fill name suggestion (user can change it)
        self._editor_widget._name_input.setText(copy_name)
        self._editor_widget._name_input.setReadOnly(False)
        self._editor_widget._editing_name = None
        self._show_editor()

    def _on_delete(self, name: str) -> None:
        ok, err = self._engine.remove_channel(name)
        if not ok:
            QMessageBox.warning(self, 'Cannot Delete', err)
            return
        self._engine.save_to_json(self._save_path)
        self.rebuild_list()
        self.channels_changed.emit()

    def _on_visibility_toggle(self, name: str, visible: bool) -> None:
        self._engine.edit_channel(name, new_visible=visible)
        self._engine.save_to_json(self._save_path)
        self.visibility_changed.emit(name, visible)

    def _on_editor_saved(self, data: dict) -> None:
        name = data['name']
        if self._editor_widget._editing_name:
            # Editing existing
            ok, err = self._engine.edit_channel(
                name,
                new_formula=data['formula'],
                new_unit=data['unit'],
                new_color=data['color'],
                new_visible=data.get('visible', True),
            )
        else:
            # Adding new
            ok, err = self._engine.add_channel(
                name=name,
                formula=data['formula'],
                unit=data['unit'],
                color=data['color'],
                description=data['description'],
                visible=data.get('visible', True),
            )

        if not ok:
            QMessageBox.warning(self, 'Error', err)
            return

        self._engine.save_to_json(self._save_path)
        self._show_list()
        self.rebuild_list()
        self.channels_changed.emit()

    # ------------------------------------------------------------------
    # View switching
    # ------------------------------------------------------------------

    def _show_editor(self) -> None:
        self._mode = 'editor'
        self._list_widget.hide()
        self._editor_widget.show()
        self._editor_widget.start_preview()

    def _show_list(self) -> None:
        self._mode = 'list'
        self._editor_widget.stop_preview()
        self._editor_widget.hide()
        self._list_widget.show()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def _save_path(self) -> str:
        """Path to the math_channels.json persistence file."""
        import sys
        from pathlib import Path
        if getattr(sys, 'frozen', False):
            return str(Path(sys.executable).parent / 'math_channels.json')
        return str(Path(__file__).resolve().parent.parent.parent / 'math_channels.json')

    def initialize(self) -> None:
        """Load presets + user channels and build the list."""
        from ..coaching.math_presets import register_presets
        register_presets(self._engine)
        self._engine.load_from_json(self._save_path)
        self.rebuild_list()

    def start(self) -> None:
        self._refresh_timer.start()

    def stop(self) -> None:
        self._refresh_timer.stop()

    # ------------------------------------------------------------------
    # Live refresh
    # ------------------------------------------------------------------

    def _refresh_values(self) -> None:
        if not self.isVisible() or self._mode != 'list':
            return
        vals = self._engine._last_values
        for name, row in self._rows.items():
            if name in vals:
                row.set_value(vals[name])

        n = len(self._engine.channels)
        ms = self._engine.last_eval_ms
        self._status.setText(f'{n} channels \u2022 eval: {ms:.1f} ms / tick')
