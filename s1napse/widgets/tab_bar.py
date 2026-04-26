"""Custom QTabBar with per-tab live-state dot indicators."""

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QColor, QBrush
from PyQt6.QtWidgets import QTabBar

from .. import theme


class LiveTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._live_indices: set[int] = set()

    def setLive(self, index: int, live: bool) -> None:
        if live: self._live_indices.add(index)
        else:    self._live_indices.discard(index)
        self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self._live_indices:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        for idx in self._live_indices:
            r: QRect = self.tabRect(idx)
            cx = r.right() - 8
            cy = r.top() + 10
            # halo
            p.setBrush(QBrush(QColor(34, 197, 94, 80)))
            p.drawEllipse(cx - 4, cy - 4, 8, 8)
            p.setBrush(QBrush(QColor(theme.GOOD)))
            p.drawEllipse(cx - 2, cy - 2, 4, 4)
        p.end()
