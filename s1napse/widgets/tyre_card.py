"""TyreCard widget and colour interpolation helpers."""

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

from ..constants import (
    C_THROTTLE, C_BRAKE, C_RPM,
    mono, sans,
)
from ..theme import (
    SURFACE_RAISED as BG2, SURFACE_HOVER as BG3,
    BORDER_SUBTLE as BORDER, BORDER_STRONG as BORDER2,
    TEXT_SECONDARY as TXT, TEXT_MUTED as TXT2, TEXT_PRIMARY as WHITE,
)


def _lerp_color(keypoints: list, value: float) -> QColor:
    """Linear-interpolate between (value, '#rrggbb') keypoints."""
    if value <= keypoints[0][0]:
        c = keypoints[0][1]
    elif value >= keypoints[-1][0]:
        c = keypoints[-1][1]
    else:
        c = keypoints[-1][1]
        for i in range(len(keypoints) - 1):
            v0, c0 = keypoints[i]
            v1, c1 = keypoints[i + 1]
            if v0 <= value <= v1:
                t = (value - v0) / (v1 - v0)
                r = int(int(c0[1:3], 16) + t * (int(c1[1:3], 16) - int(c0[1:3], 16)))
                g = int(int(c0[3:5], 16) + t * (int(c1[3:5], 16) - int(c0[3:5], 16)))
                b = int(int(c0[5:7], 16) + t * (int(c1[5:7], 16) - int(c0[5:7], 16)))
                return QColor(r, g, b)
    return QColor(int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))


_TYRE_TEMP_KP = [
    (0,   '#1e3a5f'),
    (40,  '#1d4ed8'),
    (70,  '#38bdf8'),
    (85,  '#22c55e'),
    (105, '#22c55e'),
    (120, '#f59e0b'),
    (140, '#ef4444'),
]

_BRAKE_TEMP_KP = [
    (0,   '#374151'),
    (150, '#ca8a04'),
    (400, '#f97316'),
    (750, '#ef4444'),
    (1000,'#7f1d1d'),
]


class TyreCard(QWidget):
    """Single-tyre temperature + pressure + brake temp display."""

    _STATUS = [
        (40,  'FROZEN',   '#60a5fa'),
        (70,  'COLD',     '#38bdf8'),
        (85,  'BUILDING', '#a3e635'),
        (105, 'OPTIMAL',  '#22c55e'),
        (120, 'HOT',      '#f59e0b'),
        (9999,'OVERHEAT', '#ef4444'),
    ]

    def __init__(self, position: str, parent=None):
        super().__init__(parent)
        self.position = position
        self.temp     = 0.0
        self.pressure = 0.0
        self.brake_t  = 0.0
        self.wear_pct = 0.0
        self.setMinimumSize(180, 234)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def update_data(self, temp: float, pressure: float, brake_t: float,
                    wear_pct: float = 0.0):
        self.temp     = temp
        self.pressure = pressure
        self.brake_t  = brake_t
        self.wear_pct = wear_pct
        self.update()

    def status(self) -> tuple:
        for thresh, label, color in self._STATUS:
            if self.temp <= thresh:
                return label, color
        return 'OVERHEAT', '#ef4444'

    @staticmethod
    def status_for(temp: float) -> tuple:
        for thresh, label, color in TyreCard._STATUS:
            if temp <= thresh:
                return label, color
        return 'OVERHEAT', '#ef4444'

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        temp_col  = _lerp_color(_TYRE_TEMP_KP,  self.temp)
        brake_col = _lerp_color(_BRAKE_TEMP_KP, self.brake_t)
        status_txt, status_hex = self.status()
        status_col = QColor(status_hex)
        has_data   = self.temp > 0.5

        MARGIN  = 14
        HDR_H   = 26
        FOOT_H  = 84
        tyre_y  = HDR_H
        tyre_h  = h - HDR_H - FOOT_H
        tyre_rect = QRectF(MARGIN, tyre_y, w - 2 * MARGIN, tyre_h)

        painter.fillRect(0, 0, w, h, QColor(BG2))

        glow = QColor(temp_col) if has_data else QColor(BG3)
        glow.setAlpha(18)
        painter.fillRect(0, 0, w, h, glow)

        body_fill = QColor(temp_col) if has_data else QColor(BG3)
        body_fill.setAlpha(40)
        painter.setBrush(QBrush(body_fill))
        border_col = QColor(temp_col) if has_data else QColor(BORDER)
        painter.setPen(QPen(border_col, 2))
        painter.drawRoundedRect(tyre_rect, 10, 10)

        if has_data:
            painter.setFont(mono(30, bold=True))
            painter.setPen(temp_col)
            num_rect = QRectF(tyre_rect.x(), tyre_rect.y() + 10,
                              tyre_rect.width(), tyre_rect.height() * 0.60)
            painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter,
                             f'{self.temp:.0f}')
            painter.setFont(sans(9))
            painter.setPen(QColor(TXT2))
            unit_rect = QRectF(tyre_rect.x(),
                               tyre_rect.y() + tyre_rect.height() * 0.62,
                               tyre_rect.width(), 20)
            painter.drawText(unit_rect, Qt.AlignmentFlag.AlignCenter, '\u00b0C')
        else:
            painter.setFont(mono(18))
            painter.setPen(QColor(TXT2))
            painter.drawText(tyre_rect, Qt.AlignmentFlag.AlignCenter, 'NO DATA')

        painter.setFont(sans(8))
        painter.setPen(QColor(TXT2))
        painter.drawText(QRectF(MARGIN, 4, 40, HDR_H - 4),
                         Qt.AlignmentFlag.AlignVCenter, self.position)

        if has_data:
            badge_w, badge_h_px = 68, 17
            badge_rect = QRectF(w - badge_w - MARGIN, 5, badge_w, badge_h_px)
            bg = QColor(status_col)
            bg.setAlpha(35)
            painter.setBrush(QBrush(bg))
            painter.setPen(QPen(status_col, 1))
            painter.drawRoundedRect(badge_rect, 4, 4)
            painter.setFont(sans(6))
            painter.setPen(status_col)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, status_txt)

        foot_y = float(h - FOOT_H)

        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawLine(MARGIN, int(foot_y), w - MARGIN, int(foot_y))

        p_y = foot_y + 6
        painter.setFont(sans(7))
        painter.setPen(QColor(TXT2))
        painter.drawText(QRectF(MARGIN, p_y, 32, 18),
                         Qt.AlignmentFlag.AlignVCenter, 'PSI')
        painter.setFont(mono(11, bold=True))
        painter.setPen(QColor(WHITE))
        pres_txt = f'{self.pressure:.1f}' if self.pressure > 0 else '\u2014'
        painter.drawText(QRectF(MARGIN + 30, p_y, w - MARGIN * 2 - 30, 18),
                         Qt.AlignmentFlag.AlignVCenter, pres_txt)

        bar_y   = foot_y + 28
        bar_w   = float(w - 2 * MARGIN)
        bar_h_px = 8

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(BG3)))
        painter.drawRoundedRect(QRectF(MARGIN, bar_y, bar_w, bar_h_px), 3, 3)

        ratio = min(1.0, self.brake_t / 1000.0)
        if ratio > 0:
            painter.setBrush(QBrush(brake_col))
            painter.drawRoundedRect(QRectF(MARGIN, bar_y, bar_w * ratio, bar_h_px), 3, 3)

        lbl_y = bar_y + bar_h_px + 3
        painter.setFont(sans(6))
        painter.setPen(QColor(TXT2))
        painter.drawText(QRectF(MARGIN, lbl_y, 36, 14),
                         Qt.AlignmentFlag.AlignVCenter, 'BRAKE')
        painter.setFont(mono(7))
        painter.setPen(brake_col if self.brake_t > 0 else QColor(TXT2))
        brk_txt = f'{self.brake_t:.0f}\u00b0C' if self.brake_t > 0 else '\u2014'
        painter.drawText(QRectF(MARGIN + 38, lbl_y, bar_w - 38, 14),
                         Qt.AlignmentFlag.AlignVCenter, brk_txt)

        wear_bar_y = foot_y + 55
        w_pct = max(0.0, min(100.0, self.wear_pct))
        if w_pct <= 30:
            wear_col = QColor(C_THROTTLE)
        elif w_pct <= 60:
            wear_col = QColor(C_RPM)
        else:
            wear_col = QColor(C_BRAKE)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(BG3)))
        painter.drawRoundedRect(QRectF(MARGIN, wear_bar_y, bar_w, 5), 2, 2)
        if w_pct > 0:
            painter.setBrush(QBrush(wear_col))
            painter.drawRoundedRect(
                QRectF(MARGIN, wear_bar_y, bar_w * w_pct / 100, 5), 2, 2)

        wear_lbl_y = wear_bar_y + 7
        painter.setFont(sans(6))
        painter.setPen(QColor(TXT2))
        painter.drawText(QRectF(MARGIN, wear_lbl_y, 36, 14),
                         Qt.AlignmentFlag.AlignVCenter, 'WEAR')
        painter.setFont(mono(7))
        painter.setPen(wear_col if w_pct > 0 else QColor(TXT2))
        wear_txt = f'{w_pct:.0f}%' if has_data else '\u2014'
        painter.drawText(QRectF(MARGIN + 38, wear_lbl_y, bar_w - 38, 14),
                         Qt.AlignmentFlag.AlignVCenter, wear_txt)

        painter.end()
