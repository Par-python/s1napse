"""Formula editor widget with syntax highlighting, autocomplete, and live preview.

This is the core editing experience for math channels.  It is owned by
``MathChannelPanel`` and never used as a standalone top-level window.
"""

from __future__ import annotations

import re
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect, QSize
from PyQt6.QtGui import (
    QColor, QFont, QSyntaxHighlighter, QTextCharFormat,
    QPainter, QPen, QKeyEvent,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QFrame, QListWidget, QListWidgetItem,
    QColorDialog, QSizePolicy,
)

from ..constants import (
    C_SPEED, mono, sans,
)
from ..theme import (
    BG, SURFACE_RAISED as BG2, SURFACE_HOVER as BG3,
    BORDER_SUBTLE as BORDER, BORDER_STRONG as BORDER2,
    TEXT_SECONDARY as TXT, TEXT_MUTED as TXT2, TEXT_PRIMARY as WHITE,
)
from ..coaching.math_functions import ALL_FUNCTION_NAMES, FUNCTION_REGISTRY, STATEFUL_FUNCTIONS, CONSTANTS


# ---------------------------------------------------------------------------
# Syntax highlighter
# ---------------------------------------------------------------------------

_FUNC_NAMES = sorted(ALL_FUNCTION_NAMES)
_CONST_NAMES = sorted(CONSTANTS.keys()) + ['dt']

# Build regex patterns for highlighting
_NUM_RE = re.compile(r'\b\d+(\.\d+)?\b')
_OP_RE = re.compile(r'[+\-*/%()\^,<>=!]')
_NAME_RE = re.compile(r'\b[a-z_][a-z0-9_]*\b')


class FormulaHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for math channel formulas."""

    def __init__(self, parent=None, *, known_channels: set[str] | None = None):
        super().__init__(parent)
        self.known_channels: set[str] = known_channels or set()

        # Formats
        self.fmt_function = QTextCharFormat()
        self.fmt_function.setForeground(QColor('#6C9EFF'))
        self.fmt_function.setFontWeight(QFont.Weight.Bold)

        self.fmt_channel = QTextCharFormat()
        self.fmt_channel.setForeground(QColor('#4ECDC4'))

        self.fmt_number = QTextCharFormat()
        self.fmt_number.setForeground(QColor('#FFB347'))

        self.fmt_constant = QTextCharFormat()
        self.fmt_constant.setForeground(QColor('#C49CDE'))
        self.fmt_constant.setFontItalic(True)

        self.fmt_unknown = QTextCharFormat()
        self.fmt_unknown.setForeground(QColor('#FF6B6B'))
        self.fmt_unknown.setFontUnderline(True)

        self.fmt_keyword = QTextCharFormat()
        self.fmt_keyword.setForeground(QColor('#C586C0'))
        self.fmt_keyword.setFontWeight(QFont.Weight.Bold)

    def set_known_channels(self, names: set[str]) -> None:
        self.known_channels = names
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        # Numbers
        for m in _NUM_RE.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_number)

        # Names (must come after numbers so names override partial matches)
        for m in _NAME_RE.finditer(text):
            name = m.group()
            if name in ('if', 'else', 'and', 'or', 'not'):
                fmt = self.fmt_keyword
            elif name in ALL_FUNCTION_NAMES:
                fmt = self.fmt_function
            elif name in _CONST_NAMES:
                fmt = self.fmt_constant
            elif name in self.known_channels:
                fmt = self.fmt_channel
            else:
                fmt = self.fmt_unknown
            self.setFormat(m.start(), m.end() - m.start(), fmt)


# ---------------------------------------------------------------------------
# Autocomplete popup
# ---------------------------------------------------------------------------

class _AutocompletePopup(QFrame):
    """Lightweight popup listing matching completions."""

    item_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(f"""
            QFrame {{
                background: {BG2};
                border: 1px solid {BORDER2};
                border-radius: 4px;
            }}
            QListWidget {{
                background: transparent;
                border: none;
                color: {TXT};
                font-family: Consolas;
                font-size: 11px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 3px 8px;
            }}
            QListWidget::item:selected {{
                background: {BG3};
                color: {WHITE};
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self._list = QListWidget()
        self._list.itemActivated.connect(self._on_activate)
        lay.addWidget(self._list)
        self.setMaximumHeight(220)

    def populate(self, items: list[tuple[str, str]]) -> None:
        """Fill with (name, category) tuples."""
        self._list.clear()
        for name, cat in items:
            item = QListWidgetItem(f'{name}  \u2014  {cat}')
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)

    def move_selection(self, delta: int) -> None:
        row = self._list.currentRow() + delta
        row = max(0, min(row, self._list.count() - 1))
        self._list.setCurrentRow(row)

    def accept_current(self) -> None:
        item = self._list.currentItem()
        if item:
            self.item_selected.emit(item.data(Qt.ItemDataRole.UserRole))
        self.hide()

    def _on_activate(self, item: QListWidgetItem) -> None:
        self.item_selected.emit(item.data(Qt.ItemDataRole.UserRole))
        self.hide()


# ---------------------------------------------------------------------------
# Color swatch button
# ---------------------------------------------------------------------------

_PALETTE = [
    '#FF6B35', '#4ECDC4', '#FFE66D', '#FF6B6B', '#45B7D1',
    '#96CEB4', '#FFEAA7', '#DFE6E9', '#A8E6CF', '#88D8B0',
    '#D4776B', '#FDCB6E', '#C586C0', '#6C9EFF', '#C49CDE',
    '#E0E0E0',
]


class _ColorSwatch(QPushButton):
    """Small clickable color swatch."""

    color_changed = pyqtSignal(str)

    def __init__(self, initial: str = '#FFFFFF', parent=None):
        super().__init__(parent)
        self._color = initial
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()
        self.clicked.connect(self._pick)

    @property
    def color(self) -> str:
        return self._color

    @color.setter
    def color(self, val: str) -> None:
        self._color = val
        self._update_style()

    def _update_style(self):
        self.setStyleSheet(
            f'background: {self._color}; border: 1px solid {BORDER2}; border-radius: 4px;'
        )

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, 'Channel Color')
        if c.isValid():
            self._color = c.name()
            self._update_style()
            self.color_changed.emit(self._color)


# ---------------------------------------------------------------------------
# Formula editor widget
# ---------------------------------------------------------------------------

class FormulaEditorWidget(QWidget):
    """Inline formula editor with syntax highlighting, autocomplete, and live preview.

    Signals
    -------
    saved(dict)
        Emitted when the user clicks Save. Payload is a dict with keys:
        ``name``, ``formula``, ``unit``, ``color``, ``description``, ``visible``.
    cancelled()
        Emitted when the user clicks Cancel.
    """

    saved = pyqtSignal(dict)
    cancelled = pyqtSignal()

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._editing_name: str | None = None  # set when editing existing channel
        self._is_valid = False

        self._build_ui()
        self._connect_signals()
        self._autocomplete_popup = _AutocompletePopup(self)
        self._autocomplete_popup.item_selected.connect(self._insert_completion)
        self._autocomplete_popup.hide()

        self._validation_timer = QTimer()
        self._validation_timer.setSingleShot(True)
        self._validation_timer.setInterval(200)
        self._validation_timer.timeout.connect(self._validate)

        self._preview_timer = QTimer()
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._update_preview)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel('FORMULA EDITOR')
        title.setFont(sans(9, bold=True))
        title.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        layout.addWidget(title)

        # Name row
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        lbl = QLabel('Name')
        lbl.setFont(sans(10))
        lbl.setFixedWidth(60)
        name_row.addWidget(lbl)
        self._name_input = QLineEdit()
        self._name_input.setFont(mono(11))
        self._name_input.setPlaceholderText('my_channel')
        self._name_input.setMaxLength(40)
        name_row.addWidget(self._name_input)
        self._name_status = QLabel()
        self._name_status.setFixedWidth(20)
        name_row.addWidget(self._name_status)
        layout.addLayout(name_row)

        # Formula editor
        formula_lbl = QLabel('Formula')
        formula_lbl.setFont(sans(10))
        layout.addWidget(formula_lbl)
        self._formula_edit = QPlainTextEdit()
        self._formula_edit.setFont(mono(11))
        self._formula_edit.setFixedHeight(70)
        self._formula_edit.setPlaceholderText('speed * 3.6  or  avg(tyre_temp_fl, tyre_temp_fr)')
        self._formula_edit.setStyleSheet(
            f'background: {BG3}; color: {TXT}; border: 1px solid {BORDER2}; '
            f'border-radius: 3px; padding: 4px;'
        )
        self._formula_edit.setTabChangesFocus(True)
        self._highlighter = FormulaHighlighter(
            self._formula_edit.document(),
            known_channels=set(self._engine.get_available_names()),
        )
        layout.addWidget(self._formula_edit)

        # Validation feedback
        self._validation_label = QLabel()
        self._validation_label.setFont(sans(9))
        self._validation_label.setWordWrap(True)
        self._validation_label.setStyleSheet(f'color: {TXT2};')
        layout.addWidget(self._validation_label)

        # Live preview
        self._preview_label = QLabel()
        self._preview_label.setFont(mono(10))
        self._preview_label.setStyleSheet(f'color: {TXT2};')
        layout.addWidget(self._preview_label)

        # Unit + color row
        meta_row = QHBoxLayout()
        meta_row.setSpacing(6)
        lbl2 = QLabel('Unit')
        lbl2.setFont(sans(10))
        lbl2.setFixedWidth(30)
        meta_row.addWidget(lbl2)
        self._unit_input = QLineEdit()
        self._unit_input.setFont(mono(10))
        self._unit_input.setPlaceholderText('\u00b0C, %, km/h, G ...')
        self._unit_input.setFixedWidth(100)
        meta_row.addWidget(self._unit_input)

        meta_row.addSpacing(12)
        lbl3 = QLabel('Color')
        lbl3.setFont(sans(10))
        lbl3.setFixedWidth(36)
        meta_row.addWidget(lbl3)
        self._color_swatch = _ColorSwatch('#4ECDC4')
        meta_row.addWidget(self._color_swatch)
        meta_row.addStretch()
        layout.addLayout(meta_row)

        # Description
        desc_row = QHBoxLayout()
        desc_row.setSpacing(6)
        lbl4 = QLabel('Desc')
        lbl4.setFont(sans(10))
        lbl4.setFixedWidth(30)
        desc_row.addWidget(lbl4)
        self._desc_input = QLineEdit()
        self._desc_input.setFont(sans(10))
        self._desc_input.setPlaceholderText('Optional description')
        desc_row.addWidget(self._desc_input)
        layout.addLayout(desc_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()
        self._cancel_btn = QPushButton('Cancel')
        self._cancel_btn.setFixedWidth(80)
        btn_row.addWidget(self._cancel_btn)
        self._save_btn = QPushButton('Save')
        self._save_btn.setFixedWidth(80)
        self._save_btn.setEnabled(False)
        self._save_btn.setStyleSheet(
            f'QPushButton {{ background: #1a3a2a; color: #00e87a; '
            f'border: 1px solid #00e87a; border-radius: 3px; padding: 5px 12px; }}'
            f'QPushButton:disabled {{ background: {BG3}; color: {TXT2}; border-color: {BORDER2}; }}'
            f'QPushButton:hover {{ background: #1f4a35; }}'
        )
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

    def _connect_signals(self):
        self._name_input.textChanged.connect(self._on_name_changed)
        self._formula_edit.textChanged.connect(self._on_formula_changed)
        self._formula_edit.installEventFilter(self)
        self._save_btn.clicked.connect(self._on_save)
        self._cancel_btn.clicked.connect(self.cancelled.emit)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_channel(self, name: str, formula: str, unit: str, color: str,
                     description: str, read_only: bool = False) -> None:
        """Populate editor with existing channel data for editing."""
        self._editing_name = name
        self._name_input.setText(name)
        self._name_input.setReadOnly(True)
        self._name_input.setStyleSheet(
            f'background: {BG2}; color: {TXT2};' if read_only else '')
        self._formula_edit.setPlainText(formula)
        self._formula_edit.setReadOnly(read_only)
        self._unit_input.setText(unit)
        self._color_swatch.color = color
        self._desc_input.setText(description)
        if read_only:
            self._save_btn.hide()
            self._cancel_btn.setText('Close')
        self._validate()

    def reset(self) -> None:
        """Clear all fields for a new channel."""
        self._editing_name = None
        self._name_input.clear()
        self._name_input.setReadOnly(False)
        self._name_input.setStyleSheet('')
        self._formula_edit.clear()
        self._formula_edit.setReadOnly(False)
        self._unit_input.clear()
        self._color_swatch.color = _PALETTE[0]
        self._desc_input.clear()
        self._save_btn.show()
        self._cancel_btn.setText('Cancel')
        self._save_btn.setEnabled(False)
        self._validation_label.clear()
        self._preview_label.clear()
        self._is_valid = False
        self._name_input.setFocus()

    def start_preview(self) -> None:
        self._preview_timer.start()
        self._highlighter.set_known_channels(
            set(self._engine.get_available_names()))

    def stop_preview(self) -> None:
        self._preview_timer.stop()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _on_name_changed(self, _text: str) -> None:
        self._validation_timer.start()

    def _on_formula_changed(self) -> None:
        self._validation_timer.start()
        self._try_autocomplete()

    def _validate(self) -> None:
        name = self._name_input.text().strip()
        formula = self._formula_edit.toPlainText().strip()

        # Name validation (skip when editing existing — name is locked)
        name_ok = True
        if not self._editing_name:
            if not name:
                self._name_status.setText('')
                name_ok = False
            else:
                err = self._engine._validate_name(name)
                if err:
                    self._name_status.setText('\u274c')
                    self._name_status.setToolTip(err)
                    name_ok = False
                else:
                    self._name_status.setText('\u2705')
                    self._name_status.setToolTip('')

        # Formula validation
        if not formula:
            self._validation_label.setText('')
            self._is_valid = False
            self._save_btn.setEnabled(False)
            return

        exclude = self._editing_name or (name if name_ok else None)
        ok, msg, deps = self._engine.validate_formula(formula, exclude_name=exclude)

        if ok:
            dep_text = ', '.join(deps) if deps else 'none'
            self._validation_label.setText(
                f'<span style="color:#00e87a">\u2714</span> '
                f'<span style="color:{TXT2}">Uses: {dep_text}</span>'
            )
            self._is_valid = True
        else:
            self._validation_label.setText(
                f'<span style="color:#ff3232">\u2718 {msg}</span>'
            )
            self._is_valid = False

        self._save_btn.setEnabled(self._is_valid and name_ok)

    def _update_preview(self) -> None:
        if not self._is_valid:
            self._preview_label.clear()
            return
        # Show last computed values for referenced channels
        vals = self._engine._last_values
        if vals:
            # If editing an existing channel, show its current value
            if self._editing_name and self._editing_name in vals:
                v = vals[self._editing_name]
                unit = self._unit_input.text().strip()
                self._preview_label.setText(f'Current: {v:.4f} {unit}')
            else:
                self._preview_label.setText(f'{len(vals)} channels active')
        else:
            self._preview_label.setText('Waiting for telemetry...')

    # ------------------------------------------------------------------
    # Autocomplete
    # ------------------------------------------------------------------

    def _try_autocomplete(self) -> None:
        cursor = self._formula_edit.textCursor()
        text = self._formula_edit.toPlainText()
        pos = cursor.position()

        # Extract partial word at cursor
        start = pos
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == '_'):
            start -= 1
        partial = text[start:pos]

        if len(partial) < 2:
            self._autocomplete_popup.hide()
            return

        matches: list[tuple[str, str]] = []
        lower = partial.lower()

        # Functions
        for fn in sorted(ALL_FUNCTION_NAMES):
            if fn.startswith(lower):
                if fn in FUNCTION_REGISTRY:
                    _, mn, mx = FUNCTION_REGISTRY[fn]
                    sig = f'{fn}({", ".join(["..."] * mn)})'
                elif fn in STATEFUL_FUNCTIONS:
                    sig = f'{fn}(channel, ...)'
                else:
                    sig = fn
                matches.append((fn, f'Function: {sig}'))

        # Constants
        for c in _CONST_NAMES:
            if c.startswith(lower):
                matches.append((c, 'Constant'))

        # Channels
        for ch in sorted(self._engine.get_available_names()):
            if ch.startswith(lower) and ch not in ALL_FUNCTION_NAMES and ch not in _CONST_NAMES:
                matches.append((ch, 'Channel'))

        if not matches:
            self._autocomplete_popup.hide()
            return

        self._autocomplete_popup.populate(matches[:15])

        # Position popup below cursor
        rect = self._formula_edit.cursorRect(cursor)
        global_pos = self._formula_edit.mapToGlobal(rect.bottomLeft())
        self._autocomplete_popup.move(global_pos)
        self._autocomplete_popup.setFixedWidth(
            max(300, self._formula_edit.width()))
        self._autocomplete_popup.show()

    def _insert_completion(self, text: str) -> None:
        cursor = self._formula_edit.textCursor()
        doc_text = self._formula_edit.toPlainText()
        pos = cursor.position()

        # Find start of partial word
        start = pos
        while start > 0 and (doc_text[start - 1].isalnum() or doc_text[start - 1] == '_'):
            start -= 1

        cursor.setPosition(start)
        cursor.setPosition(pos, cursor.MoveMode.KeepAnchor)
        cursor.insertText(text)
        self._formula_edit.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # Key event filter (autocomplete navigation)
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if obj is self._formula_edit and isinstance(event, QKeyEvent):
            if self._autocomplete_popup.isVisible():
                if event.key() == Qt.Key.Key_Down:
                    self._autocomplete_popup.move_selection(1)
                    return True
                if event.key() == Qt.Key.Key_Up:
                    self._autocomplete_popup.move_selection(-1)
                    return True
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Tab):
                    self._autocomplete_popup.accept_current()
                    return True
                if event.key() == Qt.Key.Key_Escape:
                    self._autocomplete_popup.hide()
                    return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        if not self._is_valid:
            return
        self.saved.emit({
            'name': self._name_input.text().strip(),
            'formula': self._formula_edit.toPlainText().strip(),
            'unit': self._unit_input.text().strip(),
            'color': self._color_swatch.color,
            'description': self._desc_input.text().strip(),
            'visible': True,
        })
