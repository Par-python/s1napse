"""Always-visible top strip — brand + live source pill + session context."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QBrush
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget, QSizePolicy

from .. import theme


class _BrandDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(139, 92, 246, 60)))
        p.drawEllipse(0, 0, 10, 10)
        p.setBrush(QBrush(QColor(theme.ACCENT)))
        p.drawEllipse(2, 2, 6, 6)
        p.end()


class _LiveDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(8, 8)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(34, 197, 94, 80)))
        p.drawEllipse(0, 0, 8, 8)
        p.setBrush(QBrush(QColor(theme.GOOD)))
        p.drawEllipse(2, 2, 4, 4)
        p.end()


class TitleBar(QFrame):
    """Top strip — brand on the left, source pill in the middle, session context on the right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(
            f'background:{theme.BG}; border:none; '
            f'border-bottom:1px solid {theme.BORDER_SUBTLE};'
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(14)

        # Brand
        brand = QHBoxLayout()
        brand.setSpacing(8)
        brand.setContentsMargins(0, 0, 0, 0)
        brand.addWidget(_BrandDot())
        brand_lbl = QLabel('S1NAPSE')
        brand_lbl.setFont(theme.ui_font(13, bold=True))
        brand_lbl.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; background:transparent;')
        brand.addWidget(brand_lbl)
        row.addLayout(brand)
        self._brand_lbl = brand_lbl

        # Source pill
        self._pill_box = QFrame()
        self._pill_box.setStyleSheet(
            f'background:{theme.SURFACE_RAISED}; border:1px solid {theme.BORDER_STRONG};'
            f'border-radius:999px;'
        )
        pill_l = QHBoxLayout(self._pill_box)
        pill_l.setContentsMargins(10, 4, 10, 4)
        pill_l.setSpacing(6)
        self._live_dot = _LiveDot()
        self._live = False  # tracks logical live state independent of Qt visibility
        pill_l.addWidget(self._live_dot)
        self._source_lbl = QLabel('')
        self._source_lbl.setFont(theme.mono_font(10))
        self._source_lbl.setStyleSheet(f'color:{theme.TEXT_SECONDARY}; background:transparent; border:none;')
        pill_l.addWidget(self._source_lbl)
        self._pill_box.setVisible(False)
        row.addWidget(self._pill_box)

        row.addStretch(1)

        self._trailing = QHBoxLayout()
        self._trailing.setContentsMargins(0, 0, 0, 0)
        self._trailing.setSpacing(8)
        row.addLayout(self._trailing)

        # Session context
        self._lap = QLabel('')
        self._stint = QLabel('')
        self._last = QLabel('')
        for lbl, color in (
            (self._lap, theme.TEXT_MUTED),
            (self._stint, theme.TEXT_MUTED),
            (self._last, theme.TEXT_PRIMARY),
        ):
            lbl.setFont(theme.mono_font(11))
            lbl.setStyleSheet(f'color:{color}; background:transparent; border:none;')
            row.addWidget(lbl)

    def addTrailing(self, w) -> None:
        """Insert a widget into the right-side toolbar slot."""
        self._trailing.addWidget(w)

    def brand(self) -> str:
        return self._brand_lbl.text()

    def sourceText(self) -> str:
        return self._source_lbl.text()

    def isLive(self) -> bool:
        # Use the logical flag rather than Qt's isVisible(), which returns False
        # for widgets whose top-level window has never been shown.
        return self._live and bool(self._source_lbl.text())

    def setSource(self, text: str, *, live: bool = True) -> None:
        self._live = live and bool(text)
        self._source_lbl.setText(text)
        self._live_dot.setVisible(live)
        self._pill_box.setVisible(bool(text))

    def setSession(self, *, lap: str = '', stint: str = '', last_lap: str = '') -> None:
        # Store text verbatim. No "Lap " prefix — keeps the API symmetric
        # with the test's assertion `sessionLap().text() == '8 / —'`.
        self._lap.setText(lap)
        self._stint.setText(stint)
        self._last.setText(last_lap)

    def sessionLap(self) -> QLabel:     return self._lap
    def sessionStint(self) -> QLabel:   return self._stint
    def sessionLastLap(self) -> QLabel: return self._last
