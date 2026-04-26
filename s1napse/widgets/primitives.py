"""Reusable visual primitives. Every card/stat/pill in the app comes from here."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFontMetrics
from PyQt6.QtWidgets import QFrame, QLabel, QHBoxLayout, QVBoxLayout, QWidget, QSizePolicy

from .. import theme


_PILL_TONES = {
    'neutral': (theme.SURFACE_RAISED, theme.BORDER_STRONG, theme.TEXT_SECONDARY),
    'violet':  ('#1d1631', 'rgba(139,92,246,0.32)', '#b4a0ff'),
    'good':    ('#102a1c', 'rgba(34,197,94,0.32)',  '#5fe39a'),
    'warn':    ('#2a200d', 'rgba(245,158,11,0.32)', '#fbbf24'),
    'bad':     ('#2a1313', 'rgba(239,68,68,0.32)',  '#fca5a5'),
}


class Pill(QLabel):
    """Small status pill — tabular mono text, colored by tone."""

    def __init__(self, text: str = '', *, tone: str = 'neutral', parent=None):
        if tone not in _PILL_TONES:
            raise ValueError(f'invalid tone {tone!r}, expected one of {sorted(_PILL_TONES)}')
        super().__init__(text, parent)
        self._tone = tone
        self.setFont(theme.mono_font(9))
        bg, border, fg = _PILL_TONES[tone]
        self.setStyleSheet(
            f'background:{bg}; color:{fg}; border:1px solid {border};'
            f'border-radius:{theme.RADIUS["sm"]}px; padding:2px 7px;'
            f'letter-spacing:0.3px;'
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def tone(self) -> str:
        return self._tone
