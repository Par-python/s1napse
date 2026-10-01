"""Always-visible top strip — brand + live source pill + session context."""

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QColor, QPainter, QBrush
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import theme


class _BrandDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        halo = QColor(theme.ACCENT); halo.setAlpha(40)
        p.setBrush(QBrush(halo))
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
        halo = QColor(theme.GOOD); halo.setAlpha(80)
        p.setBrush(QBrush(halo))
        p.drawEllipse(0, 0, 8, 8)
        p.setBrush(QBrush(QColor(theme.GOOD)))
        p.drawEllipse(2, 2, 4, 4)
        p.end()


class TitleBar(QFrame):
    """Top strip: wordmark and status pill on the left, session context on the right.

    Connection controls live in a popover opened from the status pill so the
    bar itself stays quiet. Widgets that must stay reachable while driving
    (the manual LAP button) go in via addPersistent().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setObjectName('TitleBar')
        self.setStyleSheet(
            f'#TitleBar {{ background:{theme.BG}; border:none;'
            f' border-bottom:1px solid {theme.BORDER_SUBTLE}; }}'
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(20, 0, 20, 0)
        row.setSpacing(16)

        brand_lbl = QLabel('S1napse')
        bf = theme.ui_font(15, bold=True)
        bf.setLetterSpacing(bf.SpacingType.AbsoluteSpacing, -0.3)
        brand_lbl.setFont(bf)
        brand_lbl.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; background:transparent;')
        row.addWidget(brand_lbl)
        self._brand_lbl = brand_lbl

        # Status pill: always visible, opens the source popover.
        self._pill = QPushButton()
        self._pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pill.setObjectName('SourcePill')
        self._pill.setStyleSheet(
            f'#SourcePill {{ background:{theme.SURFACE}; border:1px solid {theme.BORDER_SUBTLE};'
            f' border-radius:15px; padding:0; min-height:30px; }}'
            f'#SourcePill:hover {{ border-color:{theme.BORDER_STRONG}; }}'
        )
        pill_l = QHBoxLayout(self._pill)
        pill_l.setContentsMargins(12, 0, 14, 0)
        pill_l.setSpacing(8)
        self._live_dot = _LiveDot()
        self._live_dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        pill_l.addWidget(self._live_dot)
        self._source_lbl = QLabel('')
        self._source_lbl.setFont(theme.ui_font(theme.FONT_BODY))
        self._source_lbl.setStyleSheet(f'color:{theme.TEXT_SECONDARY}; background:transparent; border:none;')
        self._source_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        pill_l.addWidget(self._source_lbl)
        chevron = QLabel('\u25be')
        chevron.setStyleSheet(f'color:{theme.TEXT_FAINT}; background:transparent; border:none;')
        chevron.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        pill_l.addWidget(chevron)
        self._pill.clicked.connect(self.showPopover)
        row.addWidget(self._pill)

        row.addStretch(1)

        self._persistent = QHBoxLayout()
        self._persistent.setContentsMargins(0, 0, 0, 0)
        self._persistent.setSpacing(8)
        row.addLayout(self._persistent)

        # Session context
        self._lap = QLabel('')
        self._stint = QLabel('')
        self._last = QLabel('')
        for lbl, color, size in (
            (self._lap, theme.TEXT_MUTED, theme.FONT_BODY),
            (self._stint, theme.TEXT_MUTED, theme.FONT_BODY),
            (self._last, theme.TEXT_PRIMARY, theme.FONT_BODY + 1),
        ):
            lbl.setFont(theme.mono_font(size))
            lbl.setStyleSheet(f'color:{color}; background:transparent; border:none;')
            row.addWidget(lbl)

        # Popover with the connection controls.
        self._popover = QFrame(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._popover.setObjectName('SourcePopover')
        self._popover.setStyleSheet(
            f'#SourcePopover {{ background:{theme.SURFACE}; border:1px solid {theme.BORDER_SUBTLE};'
            f' border-radius:{theme.RADIUS["lg"]}px; }}'
        )
        pop_l = QVBoxLayout(self._popover)
        pop_l.setContentsMargins(16, 14, 16, 16)
        pop_l.setSpacing(10)
        hdr = QLabel('Data source')
        hdr.setFont(theme.label_font())
        hdr.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
        pop_l.addWidget(hdr)
        self._trailing = QHBoxLayout()
        self._trailing.setContentsMargins(0, 0, 0, 0)
        self._trailing.setSpacing(8)
        pop_l.addLayout(self._trailing)

        self._source_text = ''
        self._live = False
        self.setSource('', live=False)

    # -- controls ---------------------------------------------------------
    def addTrailing(self, w) -> None:
        """Add a connection control to the source popover."""
        self._trailing.addWidget(w)

    def addPersistent(self, w) -> None:
        """Add a widget that stays visible in the bar (e.g. the manual LAP button)."""
        self._persistent.addWidget(w)

    def showPopover(self) -> None:
        self._popover.adjustSize()
        self._popover.move(self._pill.mapToGlobal(QPoint(0, self._pill.height() + 6)))
        self._popover.show()

    def sourceButton(self) -> QPushButton: return self._pill
    def popover(self) -> QFrame:            return self._popover

    # -- state ------------------------------------------------------------
    def brand(self) -> str:
        return self._brand_lbl.text()

    def sourceText(self) -> str:
        return self._source_text

    def isLive(self) -> bool:
        return self._live and bool(self._source_text)

    def setSource(self, text: str, *, live: bool = True) -> None:
        self._source_text = text
        self._live = live and bool(text)
        shown = text if text else 'Not connected'
        self._source_lbl.setText(shown)
        self._pill.setAccessibleName(shown)
        self._live_dot.setVisible(self._live)

    def setSession(self, *, lap: str = '', stint: str = '', last_lap: str = '') -> None:
        self._lap.setText(lap)
        self._stint.setText(stint)
        self._last.setText(last_lap)

    def sessionLap(self) -> QLabel:     return self._lap
    def sessionStint(self) -> QLabel:   return self._stint
    def sessionLastLap(self) -> QLabel: return self._last
