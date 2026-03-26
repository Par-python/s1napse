"""Live track map widget with throttle/brake heatmap and car position dot."""

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QRadialGradient, QFont

from ..constants import BG, BG3, BORDER, BORDER2, TXT2, WHITE, N_TRACK_SEG
from ..track_recorder import TRACKS


class TrackMapWidget(QWidget):
    """
    MoTeC-style live track map.

    The track outline is drawn from normalized waypoints.  Each segment is
    coloured according to the throttle / brake value recorded the last time
    the car passed that part of the circuit.
    """

    PAD   = 28
    W_OUT = 22
    W_IN  =  8
    MIN_DRAW = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(440, 370)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.car_progress  = 0.0
        self._throttle_map = [0.0] * N_TRACK_SEG
        self._brake_map    = [0.0] * N_TRACK_SEG

        self._world_buckets: dict[int, tuple[float, float]] = {}
        self._raw_min_x = self._raw_max_x = 0.0
        self._raw_min_z = self._raw_max_z = 0.0
        self._bounds_set = False

        self._norm:       list[tuple[float, float]] = []
        self._turns:      list = []
        self._track_name: str  = ''

        self._pts:     list[tuple[float, float]] = []
        self._last_sz: tuple[int, int]            = (0, 0)

        self._car_smooth: float = 0.0
        self._shape_locked: bool = False

    # ------------------------------------------------------------------ API

    def set_track(self, key: str):
        """Load a saved-JSON track if available; otherwise reset to live-build mode."""
        td  = TRACKS.get(key, {})
        pts = td.get('pts', [])
        if pts:
            self._norm       = [tuple(p) for p in pts]
            self._turns      = list(td.get('turns', []))
            self._track_name = td.get('name', key)
            self._world_buckets = {}
            self._bounds_set    = False
        else:
            self._norm       = []
            self._turns      = []
            self._track_name = td.get('name', key.replace('_', ' ').title()) if td else ''
        self._pts     = []
        self._last_sz = (0, 0)
        self.reset()

    def reset_track(self, display_name: str = ''):
        """Clear accumulated shape and throttle/brake data."""
        self._world_buckets = {}
        self._raw_min_x = self._raw_max_x = 0.0
        self._raw_min_z = self._raw_max_z = 0.0
        self._bounds_set = False
        self._norm       = []
        self._turns      = []
        self._track_name = display_name
        self._pts        = []
        self._last_sz    = (0, 0)
        self.reset()

    def feed_world_pos(self, pct: float, world_x: float, world_z: float):
        """Add a live world-coord sample."""
        if self._shape_locked:
            return
        if world_x == 0.0 and world_z == 0.0:
            return
        bucket     = int(pct * N_TRACK_SEG) % N_TRACK_SEG
        is_new     = bucket not in self._world_buckets
        self._world_buckets[bucket] = (world_x, world_z)

        bounds_changed = False
        if not self._bounds_set:
            self._raw_min_x = self._raw_max_x = world_x
            self._raw_min_z = self._raw_max_z = world_z
            self._bounds_set = True
            bounds_changed = True
        else:
            if world_x < self._raw_min_x: self._raw_min_x = world_x; bounds_changed = True
            if world_x > self._raw_max_x: self._raw_max_x = world_x; bounds_changed = True
            if world_z < self._raw_min_z: self._raw_min_z = world_z; bounds_changed = True
            if world_z > self._raw_max_z: self._raw_max_z = world_z; bounds_changed = True

        if (is_new or bounds_changed) and len(self._world_buckets) >= self.MIN_DRAW:
            self._recompute_norm()

    def _recompute_norm(self):
        if not self._world_buckets or not self._bounds_set:
            return
        span_x = self._raw_max_x - self._raw_min_x
        span_z = self._raw_max_z - self._raw_min_z
        span   = max(span_x, span_z)
        if span < 1.0:
            return

        scale    = 0.90 / span
        offset_x = (1.0 - span_x * scale) / 2.0
        offset_z = (1.0 - span_z * scale) / 2.0

        self._norm = [
            (round((x - self._raw_min_x) * scale + offset_x, 4),
             round((z - self._raw_min_z) * scale + offset_z, 4))
            for _, (x, z) in sorted(self._world_buckets.items())
        ]
        self._pts     = []
        self._last_sz = (0, 0)
        self.update()

    def update_telemetry(self, lap_progress: float, throttle: float, brake: float):
        self.car_progress = max(0.0, min(1.0, lap_progress))
        bucket = int(lap_progress * N_TRACK_SEG) % N_TRACK_SEG
        self._throttle_map[bucket] = throttle
        self._brake_map[bucket]    = brake

    def tick_lerp(self):
        """Called by the 60 fps animation timer to smoothly animate the car dot."""
        if not self._norm:
            return
        diff = self.car_progress - self._car_smooth
        if diff > 0.5:
            diff -= 1.0
        elif diff < -0.5:
            diff += 1.0
        self._car_smooth = (self._car_smooth + diff * 0.20) % 1.0
        self.update()

    def reset(self):
        self.car_progress  = 0.0
        self._car_smooth   = 0.0
        self._throttle_map = [0.0] * N_TRACK_SEG
        self._brake_map    = [0.0] * N_TRACK_SEG
        self.update()

    def _get_pts(self) -> list[tuple[float, float]]:
        sz = (self.width(), self.height())
        if sz == self._last_sz and self._pts:
            return self._pts
        w, h = sz
        pad  = self.PAD
        self._pts = [
            (pad + x * (w - 2 * pad),
             pad + y * (h - 2 * pad))
            for x, y in self._norm
        ]
        self._last_sz = sz
        return self._pts

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BG))

        pts = self._get_pts()
        n   = len(pts)

        if n < 2:
            painter.setPen(QColor('#333333'))
            from ..constants import sans as _sans
            painter.setFont(_sans(9))
            filled = len(self._world_buckets)
            if filled > 0:
                pct_done = int(filled / N_TRACK_SEG * 100)
                msg = f'Building track map\u2026  {pct_done}%  ({filled} / {N_TRACK_SEG} segments)'
            else:
                msg = 'Drive a lap to build the track map'
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)
            painter.end()
            return

        cap  = Qt.PenCapStyle.RoundCap
        join = Qt.PenJoinStyle.RoundJoin

        surface_pen = QPen(QColor('#1e1e1e'), self.W_OUT, Qt.PenStyle.SolidLine, cap, join)
        painter.setPen(surface_pen)
        for i in range(n):
            p1 = QPointF(*pts[i])
            p2 = QPointF(*pts[(i + 1) % n])
            painter.drawLine(p1, p2)

        edge_pen = QPen(QColor('#303030'), self.W_OUT + 2, Qt.PenStyle.SolidLine, cap, join)
        painter.setPen(edge_pen)
        for i in range(n):
            p1 = QPointF(*pts[i])
            p2 = QPointF(*pts[(i + 1) % n])
            painter.drawLine(p1, p2)
        painter.setPen(surface_pen)
        for i in range(n):
            p1 = QPointF(*pts[i])
            p2 = QPointF(*pts[(i + 1) % n])
            painter.drawLine(p1, p2)

        _SMOOTH_R = 4
        _wsum = sum((_SMOOTH_R + 1 - abs(k)) for k in range(-_SMOOTH_R, _SMOOTH_R + 1))
        sthr = [0.0] * N_TRACK_SEG
        sbrk = [0.0] * N_TRACK_SEG
        for i in range(N_TRACK_SEG):
            for k in range(-_SMOOTH_R, _SMOOTH_R + 1):
                w = (_SMOOTH_R + 1 - abs(k)) / _wsum
                j = (i + k) % N_TRACK_SEG
                sthr[i] += w * self._throttle_map[j]
                sbrk[i] += w * self._brake_map[j]

        for i in range(n):
            frac   = i / n
            bucket = int(frac * N_TRACK_SEG) % N_TRACK_SEG
            thr    = sthr[bucket]
            brk    = sbrk[bucket]

            if brk > 15:
                t   = min(1.0, brk / 100.0)
                col = QColor(int(180 + 75 * t), int(40 * (1 - t)), int(40 * (1 - t)))
            elif thr > 80:
                col = QColor(0, 232, 120)
            elif thr > 30:
                t   = (thr - 30) / 50.0
                col = QColor(int(220 * (1 - t)), int(180 + 52 * t), 40)
            else:
                col = QColor(70, 70, 70)

            p1 = QPointF(*pts[i])
            p2 = QPointF(*pts[(i + 1) % n])
            painter.setPen(QPen(col, self.W_IN, Qt.PenStyle.SolidLine, cap, join))
            painter.drawLine(p1, p2)

        sx, sy = pts[0]
        for i, col_hex in enumerate(['#ffffff', '#000000', '#ffffff']):
            painter.setPen(QPen(QColor(col_hex), 2))
            off = (i - 1) * 4
            painter.drawLine(QPointF(sx + off, sy - 10), QPointF(sx + off, sy + 10))
        sf_font = QFont()
        sf_font.setPointSize(6)
        sf_font.setBold(True)
        painter.setFont(sf_font)
        painter.setPen(QColor('#cccccc'))
        painter.drawText(int(sx + 8), int(sy - 4), 'S/F')

        name_font = QFont()
        name_font.setPointSize(7)
        painter.setFont(name_font)
        painter.setPen(QColor('#444444'))
        painter.drawText(self.PAD, self.PAD - 6, self._track_name)

        num_font = QFont()
        num_font.setPointSize(6)
        num_font.setBold(True)
        name_font2 = QFont()
        name_font2.setPointSize(6)
        CR = 8

        for frac, lbl, tname, ox, oy in self._turns:
            idx = int(frac * n) % n
            lx, ly = pts[idx]
            cp2 = QPointF(lx + ox, ly + oy)

            painter.setPen(QPen(QColor('#c0c0c0'), 1.2))
            painter.setBrush(QBrush(QColor('#1a1a1a')))
            painter.drawEllipse(cp2, CR, CR)

            painter.setFont(num_font)
            painter.setPen(QColor('#e8e8e8'))
            r = QRectF(cp2.x() - CR, cp2.y() - CR, CR * 2, CR * 2)
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, lbl)

            if tname:
                painter.setFont(name_font2)
                painter.setPen(QColor('#555555'))
                ny = int(cp2.y() + (CR + 9 if oy >= 0 else -CR - 3))
                painter.drawText(int(cp2.x() - 20), ny, tname)

        _full_lap = (not self._world_buckets
                     or len(self._world_buckets) >= int(N_TRACK_SEG * 0.85))
        if _full_lap:
            smooth = self._car_smooth
            lo_idx = int(smooth * n) % n
            hi_idx = (lo_idx + 1) % n
            frac   = (smooth * n) - int(smooth * n)
            lx, ly = pts[lo_idx]
            hx, hy = pts[hi_idx]
            cx = lx + frac * (hx - lx)
            cy = ly + frac * (hy - ly)
            cp = QPointF(cx, cy)

            grad = QRadialGradient(cp, 14)
            grad.setColorAt(0.0, QColor(255, 60, 60, 210))
            grad.setColorAt(0.5, QColor(255, 60, 60,  80))
            grad.setColorAt(1.0, QColor(255, 60, 60,   0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(cp, 14, 14)

            painter.setBrush(QBrush(QColor('#ff3c3c')))
            painter.setPen(QPen(QColor('#ffffff'), 1.5))
            painter.drawEllipse(cp, 5, 5)

        painter.end()
