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


_CARD_VARIANTS = {
    'normal': (theme.SURFACE, theme.BORDER_SUBTLE),
    'warn':   (theme.SURFACE, f'{theme.WARN}59'),   # hex + ~35 % alpha
    'bad':    (theme.SURFACE, f'{theme.BAD}59'),
}


class Card(QFrame):
    """Bordered surface container with optional header (label + pill).

    Layout:
        [ label   …   pill ]   <- header (only if label or pill given)
        [        body        ]

    `dense=True` tightens padding/spacing for live tabs.
    """

    def __init__(self, *, label: str | None = None, pill: Pill | None = None,
                 variant: str = 'normal', dense: bool = False, parent=None):
        if variant not in _CARD_VARIANTS:
            raise ValueError(f'invalid variant {variant!r}')
        super().__init__(parent)
        self._variant = variant
        self._dense = dense
        bg, border = _CARD_VARIANTS[variant]
        self.setStyleSheet(
            f'background:{bg}; border:1px solid {border};'
            f'border-radius:{theme.RADIUS["lg"]}px;'
        )

        outer = QVBoxLayout(self)
        pad = 12 if dense else 16
        outer.setContentsMargins(pad, pad, pad, pad)
        outer.setSpacing(8 if dense else 10)
        self._outer = outer

        # --- Header (lazy) ---------------------------------------------
        self._header_label: QLabel | None = None
        self._header_pill: Pill | None = None
        if label is not None or pill is not None:
            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            header.setSpacing(8)
            if label is not None:
                lab = QLabel(label)
                lab.setFont(theme.label_font())
                lab.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
                header.addWidget(lab)
                self._header_label = lab
            header.addStretch(1)
            if pill is not None:
                header.addWidget(pill)
                self._header_pill = pill
            outer.addLayout(header)

        # --- Body container --------------------------------------------
        self._body = QVBoxLayout()
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(6 if dense else 8)
        outer.addLayout(self._body)

    def variant(self) -> str:
        return self._variant

    def dense(self) -> bool:
        return self._dense

    def headerLabel(self) -> QLabel | None:
        return self._header_label

    def headerPill(self) -> Pill | None:
        return self._header_pill

    def contentLayout(self) -> QVBoxLayout:
        """Outer layout — used by tests for padding inspection."""
        return self._outer

    def body(self) -> QVBoxLayout:
        """Public layout for adding widgets/sub-layouts inside the card."""
        return self._body
