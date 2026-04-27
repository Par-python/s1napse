"""ABS/TC status badge widget."""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

from ..constants import C_ABS, C_TC, mono, sans
from ..theme import SURFACE_HOVER as BG3, BORDER_SUBTLE as BORDER, TEXT_MUTED as TXT2

_LABEL_COLORS = {
    'ABS': C_ABS,
    'TC':  C_TC,
}


class AidBadge(QWidget):
    """Indicator badge for ABS/TC status (ON/OFF with value)."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = _LABEL_COLORS.get(label, C_ABS)
        self._active = False
        self._text = 'OFF'
        self.setFixedSize(64, 46)

    def set_active(self, active: bool, text: str = ''):
        self._active = active
        self._text = text if active else 'OFF'
        self.update()

    # keep backward-compat alias
    def set_value(self, value: float):
        self.set_active(value > 0.1, f'{value:.0f}')

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        bg = QColor(self._color) if self._active else QColor(BG3)
        if self._active:
            bg.setAlpha(35)
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 4, 4)

        col = QColor(self._color) if self._active else QColor(TXT2)

        painter.setFont(sans(7))
        painter.setPen(col)
        painter.drawText(QRectF(0, 4, w, 14), Qt.AlignmentFlag.AlignCenter, self._label)

        painter.setFont(mono(11, bold=True))
        painter.setPen(col)
        painter.drawText(QRectF(0, 18, w, 22), Qt.AlignmentFlag.AlignCenter, self._text)

        painter.end()
