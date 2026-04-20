"""Live track map widget with throttle/brake heatmap and car position dot."""

from collections import deque

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QRadialGradient,
                         QLinearGradient, QFont, QPixmap, QPainterPath)

from ..constants import N_TRACK_SEG, C_THROTTLE
from ..track_recorder import TRACKS


TRAIL_LEN = 28  # history length of car trail


class TrackMapWidget(QWidget):
    """
    MoTeC-style live track map.

    The track outline is drawn from normalized waypoints.  Each segment is
    coloured according to the throttle / brake value recorded the last time
    the car passed that part of the circuit.
    """

    MIN_DRAW = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(440, 370)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

        self.car_progress = 0.0
        self._throttle_map = [0.0] * N_TRACK_SEG
        self._brake_map = [0.0] * N_TRACK_SEG

        self._world_buckets: dict[int, tuple[float, float]] = {}
        self._raw_min_x = self._raw_max_x = 0.0
        self._raw_min_z = self._raw_max_z = 0.0
        self._bounds_set = False

        self._norm:       list[tuple[float, float]] = []
        self._turns:      list = []
        self._track_name: str = ''

        self._raceline_norm: list[tuple[float, float]] = []
        self._raceline_curv: list[float] = []
        self._raceline_pts:  list[tuple[float, float]] = []
        self._show_raceline: bool = True

        # Real track boundaries (populated only when a TUMFTM CSV exists).
        self._left_norm:  list[tuple[float, float]] = []
        self._right_norm: list[tuple[float, float]] = []
        self._left_pts:   list[tuple[float, float]] = []
        self._right_pts:  list[tuple[float, float]] = []

        self._pts:     list[tuple[float, float]] = []
        self._last_sz: tuple[int, int] = (0, 0)

        self._car_smooth: float = 0.0
        self._shape_locked: bool = False

        self._bg_pixmap: QPixmap | None = None
        self._heatmap_pixmap: QPixmap | None = None
        self._raceline_pixmap: QPixmap | None = None
        self._bg_dirty: bool = True
        self._heatmap_dirty: bool = True
        self._raceline_dirty: bool = True

        # Trail: recent car positions + throttle/brake at each point.
        self._trail: deque = deque(maxlen=TRAIL_LEN)
        self._cur_throttle: float = 0.0
        self._cur_brake:    float = 0.0

        # Responsive sizes, computed per resize in _compute_layout()
        self._pad:   int = 28
        self._w_out: int = 22
        self._w_in:  int = 8
        self._font_name_sz: int = 9
        self._font_turn_num_sz: int = 7
        self._font_turn_name_sz: int = 7
        self._font_sf_sz: int = 7
        self._turn_r: int = 9
        self._car_outer: int = 14
        self._car_inner: int = 5

        # Zoom/pan state (applied as a paint-time transform).
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._drag_anchor: QPointF | None = None
        self._drag_pan: tuple[float, float] = (0.0, 0.0)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------ API

    def set_track(self, key: str):
        """Load a saved-JSON track if available; otherwise reset to live-build mode."""
        td = TRACKS.get(key, {})
        pts = td.get('pts', [])
        if pts:
            self._norm = [tuple(p) for p in pts]
            self._turns = list(td.get('turns', []))
            self._track_name = td.get('name', key)
            self._raceline_norm = [tuple(p) for p in td.get('raceline', [])]
            self._raceline_curv = list(td.get('raceline_curv', []))
            self._left_norm = [tuple(p) for p in td.get('left_edge', [])]
            self._right_norm = [tuple(p) for p in td.get('right_edge', [])]
            self._world_buckets = {}
            self._bounds_set = False
            # Saved track already has its shape — don't let live samples rebuild it.
            self._shape_locked = True
        else:
            self._norm = []
            self._turns = []
            self._track_name = td.get(
                'name', key.replace('_', ' ').title()) if td else ''
            self._raceline_norm = []
            self._raceline_curv = []
            self._left_norm = []
            self._right_norm = []
            self._shape_locked = False
        self._left_pts = []
        self._right_pts = []
        self._raceline_pts = []
        self._pts = []
        self._last_sz = (0, 0)
        self._bg_dirty = True
        self._heatmap_dirty = True
        self._raceline_dirty = True
        self._trail.clear()
        self.reset()

    def set_show_raceline(self, show: bool):
        """Toggle the reference raceline overlay."""
        if show == self._show_raceline:
            return
        self._show_raceline = show
        self.update()

    def reset_track(self, display_name: str = ''):
        """Clear accumulated shape and throttle/brake data."""
        self._world_buckets = {}
        self._raw_min_x = self._raw_max_x = 0.0
        self._raw_min_z = self._raw_max_z = 0.0
        self._bounds_set = False
        self._norm = []
        self._turns = []
        self._track_name = display_name
        self._raceline_norm = []
        self._raceline_curv = []
        self._left_norm = []
        self._right_norm = []
        self._left_pts = []
        self._right_pts = []
        self._shape_locked = False
        self._raceline_pts = []
        self._pts = []
        self._last_sz = (0, 0)
        self._bg_dirty = True
        self._heatmap_dirty = True
        self._raceline_dirty = True
        self._trail.clear()
        self.reset()

    def feed_world_pos(self, pct: float, world_x: float, world_z: float):
        """Add a live world-coord sample."""
        if self._shape_locked:
            return
        if world_x == 0.0 and world_z == 0.0:
            return
        bucket = int(pct * N_TRACK_SEG) % N_TRACK_SEG
        is_new = bucket not in self._world_buckets
        self._world_buckets[bucket] = (world_x, world_z)

        bounds_changed = False
        if not self._bounds_set:
            self._raw_min_x = self._raw_max_x = world_x
            self._raw_min_z = self._raw_max_z = world_z
            self._bounds_set = True
            bounds_changed = True
        else:
            if world_x < self._raw_min_x:
                self._raw_min_x = world_x
                bounds_changed = True
            if world_x > self._raw_max_x:
                self._raw_max_x = world_x
                bounds_changed = True
            if world_z < self._raw_min_z:
                self._raw_min_z = world_z
                bounds_changed = True
            if world_z > self._raw_max_z:
                self._raw_max_z = world_z
                bounds_changed = True

        if (is_new or bounds_changed) and len(self._world_buckets) >= self.MIN_DRAW:
            self._recompute_norm()

    def _recompute_norm(self):
        if not self._world_buckets or not self._bounds_set:
            return
        span_x = self._raw_max_x - self._raw_min_x
        span_z = self._raw_max_z - self._raw_min_z
        span = max(span_x, span_z)
        if span < 1.0:
            return

        scale = 0.90 / span
        offset_x = (1.0 - span_x * scale) / 2.0
        offset_z = (1.0 - span_z * scale) / 2.0

        # Flip Z: ACC world-Z increases northward, Qt screen-Y increases downward.
        self._norm = [
            (round((x - self._raw_min_x) * scale + offset_x, 4),
             round(1.0 - ((z - self._raw_min_z) * scale + offset_z), 4))
            for _, (x, z) in sorted(self._world_buckets.items())
        ]
        self._pts = []
        self._last_sz = (0, 0)
        self._bg_dirty = True
        self._heatmap_dirty = True
        self.update()

    def update_telemetry(self, lap_progress: float, throttle: float, brake: float):
        self.car_progress = max(0.0, min(1.0, lap_progress))
        self._cur_throttle = throttle
        self._cur_brake = brake
        bucket = int(lap_progress * N_TRACK_SEG) % N_TRACK_SEG
        if (self._throttle_map[bucket] != throttle
                or self._brake_map[bucket] != brake):
            self._throttle_map[bucket] = throttle
            self._brake_map[bucket] = brake
            self._heatmap_dirty = True

    def tick_lerp(self):
        """Called by the 60 fps animation timer to smoothly animate the car dot."""
        if not self._norm:
            return
        diff = self.car_progress - self._car_smooth
        if diff > 0.5:
            diff -= 1.0
        elif diff < -0.5:
            diff += 1.0
        if abs(diff) < 1e-5 and self._trail:
            return  # no visible change, skip repaint
        self._car_smooth = (self._car_smooth + diff * 0.35) % 1.0
        self._trail.append(
            (self._car_smooth, self._cur_throttle, self._cur_brake))
        self.update()

    def reset(self):
        self.car_progress = 0.0
        self._car_smooth = 0.0
        self._throttle_map = [0.0] * N_TRACK_SEG
        self._brake_map = [0.0] * N_TRACK_SEG
        self._heatmap_dirty = True
        self._trail.clear()
        self.update()

    # ------------------------------------------------------------ zoom / pan

    _ZOOM_MIN = 1.0
    _ZOOM_MAX = 8.0

    def reset_view(self):
        """Restore default zoom and pan."""
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.update()

    def _set_zoom_at(self, new_zoom: float, anchor: QPointF):
        """Zoom toward a screen-space anchor so the point under the cursor
        stays fixed while scaling."""
        new_zoom = max(self._ZOOM_MIN, min(self._ZOOM_MAX, new_zoom))
        if new_zoom == self._zoom:
            return
        # Solve for new pan so the anchor's pre-transform point is preserved:
        # screen = pan + zoom * world  ⇒  world = (screen - pan) / zoom.
        # After zoom change, want screen' == screen for the same world.
        wx = (anchor.x() - self._pan_x) / self._zoom
        wy = (anchor.y() - self._pan_y) / self._zoom
        self._zoom = new_zoom
        self._pan_x = anchor.x() - wx * new_zoom
        self._pan_y = anchor.y() - wy * new_zoom
        self._clamp_pan()
        self.update()

    def _clamp_pan(self):
        """Keep the scaled content from drifting fully off-screen."""
        w, h = self.width(), self.height()
        # Allow panning up to 80% of the widget dim past each edge so users
        # can push corners to the center, but not scroll into emptiness.
        max_off_x = w * (self._zoom - 1.0) + w * 0.2
        max_off_y = h * (self._zoom - 1.0) + h * 0.2
        min_x = -max_off_x
        max_x = w * 0.2
        min_y = -max_off_y
        max_y = h * 0.2
        if self._zoom <= 1.0:
            self._pan_x = 0.0
            self._pan_y = 0.0
            return
        self._pan_x = max(min_x, min(max_x, self._pan_x))
        self._pan_y = max(min_y, min(max_y, self._pan_y))

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        step = 1.15 if delta > 0 else (1.0 / 1.15)
        self._set_zoom_at(self._zoom * step, event.position())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._zoom > 1.0:
            self._drag_anchor = event.position()
            self._drag_pan = (self._pan_x, self._pan_y)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_anchor is not None:
            dx = event.position().x() - self._drag_anchor.x()
            dy = event.position().y() - self._drag_anchor.y()
            self._pan_x = self._drag_pan[0] + dx
            self._pan_y = self._drag_pan[1] + dy
            self._clamp_pan()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_anchor is not None:
            self._drag_anchor = None
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_view()
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------ layout

    def _compute_layout(self):
        """Derive padding, pen widths, and font sizes from the current widget size."""
        w, h = self.width(), self.height()
        # Scale off the shorter dimension so portrait and landscape both feel right.
        s = min(w, h)
        # Reference size: 370 (the old MinimumSize height). Clamp so extremes stay usable.
        f = max(0.75, min(2.0, s / 370.0))

        self._pad = max(16, int(28 * f))
        self._w_out = max(14, int(22 * f))
        self._w_in = max(5,  int(8 * f))
        self._font_name_sz = max(8,  int(11 * f))
        self._font_turn_num_sz = max(6,  int(7 * f))
        self._font_turn_name_sz = max(6,  int(7 * f))
        self._font_sf_sz = max(6,  int(7 * f))
        self._turn_r = max(7,  int(10 * f))
        self._car_outer = max(10, int(16 * f))
        self._car_inner = max(4,  int(6 * f))

    def _get_pts(self) -> list[tuple[float, float]]:
        sz = (self.width(), self.height())
        if sz == self._last_sz and self._pts:
            return self._pts
        self._compute_layout()
        w, h = sz
        pad = self._pad
        self._pts = [
            (pad + x * (w - 2 * pad),
             pad + y * (h - 2 * pad))
            for x, y in self._norm
        ]
        self._raceline_pts = [
            (pad + x * (w - 2 * pad),
             pad + y * (h - 2 * pad))
            for x, y in self._raceline_norm
        ]
        self._left_pts = [
            (pad + x * (w - 2 * pad),
             pad + y * (h - 2 * pad))
            for x, y in self._left_norm
        ]
        self._right_pts = [
            (pad + x * (w - 2 * pad),
             pad + y * (h - 2 * pad))
            for x, y in self._right_norm
        ]
        self._last_sz = sz
        self._bg_dirty = True
        self._heatmap_dirty = True
        self._raceline_dirty = True
        return self._pts

    # ------------------------------------------------------------ painting

    def _paint_bg_fill(self, p: QPainter, w: int, h: int):
        """Subtle vertical gradient for the panel background."""
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor('#0d0d0d'))
        grad.setColorAt(1.0, QColor('#070707'))
        p.fillRect(0, 0, w, h, QBrush(grad))

    def _build_bg_pixmap(self, pts):
        """Render static layers (surface, edge, S/F, turn labels, track name)
        onto a 2x-DPR supersampled pixmap so the track outline stays crisp."""
        w, h = self.width(), self.height()
        dpr = 2
        pm = QPixmap(w * dpr, h * dpr)
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._paint_bg_fill(p, w, h)

        n = len(pts)
        cap = Qt.PenCapStyle.RoundCap
        join = Qt.PenJoinStyle.RoundJoin

        have_edges = (len(self._left_pts) >= 3
                      and len(self._right_pts) >= 3
                      and len(self._left_pts) == len(self._right_pts))

        if have_edges:
            # --- Real track limits: fill polygon bounded by left + right edges.
            surface = QPainterPath()
            lx0, ly0 = self._left_pts[0]
            surface.moveTo(lx0, ly0)
            for x, y in self._left_pts[1:]:
                surface.lineTo(x, y)
            # Close via reversed right edge.
            for x, y in reversed(self._right_pts):
                surface.lineTo(x, y)
            surface.closeSubpath()

            # Soft drop shadow under the track surface.
            p.save()
            p.translate(0, max(2, int(self._w_out * 0.10)))
            p.fillPath(surface, QBrush(QColor(0, 0, 0, 160)))
            p.restore()

            p.fillPath(surface, QBrush(QColor('#191919')))

            # Stroke the actual track limits (brighter + thicker so they read
            # clearly against the dark background).
            limit_pen = QPen(QColor('#6a6a6a'), max(2.0, self._w_out * 0.22),
                             Qt.PenStyle.SolidLine, cap, join)
            p.setPen(limit_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            ln = len(self._left_pts)
            for i in range(ln):
                p.drawLine(QPointF(*self._left_pts[i]),
                           QPointF(*self._left_pts[(i + 1) % ln]))
            rn = len(self._right_pts)
            for i in range(rn):
                p.drawLine(QPointF(*self._right_pts[i]),
                           QPointF(*self._right_pts[(i + 1) % rn]))

            # Faint centerline hint for depth.
            p.setPen(QPen(QColor(255, 255, 255, 14), max(1, int(self._w_out * 0.04)),
                          Qt.PenStyle.SolidLine, cap, join))
            for i in range(n):
                p.drawLine(QPointF(*pts[i]), QPointF(*pts[(i + 1) % n]))
        else:
            # --- Cosmetic kerb fallback (no TUMFTM data for this track).
            shadow_pen = QPen(QColor(0, 0, 0, 160), self._w_out + 6,
                              Qt.PenStyle.SolidLine, cap, join)
            p.setPen(shadow_pen)
            p.translate(0, max(2, int(self._w_out * 0.12)))
            for i in range(n):
                p.drawLine(QPointF(*pts[i]), QPointF(*pts[(i + 1) % n]))
            p.resetTransform()

            edge_pen = QPen(QColor('#2e2e2e'), self._w_out + 2,
                            Qt.PenStyle.SolidLine, cap, join)
            p.setPen(edge_pen)
            for i in range(n):
                p.drawLine(QPointF(*pts[i]), QPointF(*pts[(i + 1) % n]))

            surface_pen = QPen(QColor('#191919'), self._w_out,
                               Qt.PenStyle.SolidLine, cap, join)
            p.setPen(surface_pen)
            for i in range(n):
                p.drawLine(QPointF(*pts[i]), QPointF(*pts[(i + 1) % n]))

            center_pen = QPen(QColor(255, 255, 255, 10), max(1, int(self._w_out * 0.05)),
                              Qt.PenStyle.SolidLine, cap, join)
            p.setPen(center_pen)
            for i in range(n):
                p.drawLine(QPointF(*pts[i]), QPointF(*pts[(i + 1) % n]))

        # --- Start/finish line (checkered strokes).
        sx, sy = pts[0]
        sf_h = int(self._w_out * 0.6)
        for i, col_hex in enumerate(['#ffffff', '#0a0a0a', '#ffffff']):
            p.setPen(QPen(QColor(col_hex), 2))
            off = (i - 1) * 4
            p.drawLine(QPointF(sx + off, sy - sf_h),
                       QPointF(sx + off, sy + sf_h))
        sf_font = QFont('Segoe UI, Helvetica, Arial', self._font_sf_sz)
        sf_font.setBold(True)
        p.setFont(sf_font)
        p.setPen(QColor('#d0d0d0'))
        p.drawText(int(sx + 8), int(sy - 4), 'S/F')

        # --- Track name header (top-left accent bar + styled text).
        if self._track_name:
            name_font = QFont('Segoe UI, Helvetica, Arial', self._font_name_sz)
            name_font.setBold(True)
            name_font.setLetterSpacing(
                QFont.SpacingType.PercentageSpacing, 110)
            p.setFont(name_font)
            name_y = max(14, self._pad - 4)
            # Accent bar
            p.fillRect(self._pad, name_y - self._font_name_sz, 3, self._font_name_sz + 2,
                       QColor(C_THROTTLE))
            p.setPen(QColor('#c0c0c0'))
            p.drawText(self._pad + 8, name_y, self._track_name.upper())

        # --- Turn labels: tight circle with number, turn name below/above in muted grey.
        num_font = QFont('Segoe UI, Helvetica, Arial', self._font_turn_num_sz)
        num_font.setBold(True)
        name_font2 = QFont('Segoe UI, Helvetica, Arial',
                           self._font_turn_name_sz)
        CR = self._turn_r

        for frac, lbl, tname, ox, oy in self._turns:
            idx = int(frac * n) % n
            lx, ly = pts[idx]
            # Scale the offsets with the responsive factor so labels stay clear of the track.
            sc = CR / 8.0
            cp2 = QPointF(lx + ox * sc, ly + oy * sc)

            # Label background — slightly larger halo so it pops against heatmap.
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(10, 10, 10, 220)))
            p.drawEllipse(cp2, CR + 2, CR + 2)

            p.setPen(QPen(QColor('#888888'), 1.2))
            p.setBrush(QBrush(QColor('#141414')))
            p.drawEllipse(cp2, CR, CR)

            p.setFont(num_font)
            p.setPen(QColor(C_THROTTLE))
            r = QRectF(cp2.x() - CR, cp2.y() - CR, CR * 2, CR * 2)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, lbl)

            if tname:
                p.setFont(name_font2)
                p.setPen(QColor('#707070'))
                ny = int(cp2.y() + (CR + self._font_turn_name_sz +
                         4 if oy >= 0 else -CR - 4))
                tw = int(CR * 8)
                p.drawText(int(cp2.x() - tw / 2), ny - self._font_turn_name_sz,
                           tw, self._font_turn_name_sz + 6,
                           Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                           tname)

        p.end()
        return pm

    def _build_heatmap_pixmap(self, pts):
        """Render colored throttle/brake segments onto a transparent 2x pixmap."""
        w, h = self.width(), self.height()
        dpr = 2
        pm = QPixmap(w * dpr, h * dpr)
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        n = len(pts)
        cap = Qt.PenCapStyle.RoundCap
        join = Qt.PenJoinStyle.RoundJoin

        _SMOOTH_R = 4
        _wsum = sum((_SMOOTH_R + 1 - abs(k))
                    for k in range(-_SMOOTH_R, _SMOOTH_R + 1))
        sthr = [0.0] * N_TRACK_SEG
        sbrk = [0.0] * N_TRACK_SEG
        for i in range(N_TRACK_SEG):
            for k in range(-_SMOOTH_R, _SMOOTH_R + 1):
                wt = (_SMOOTH_R + 1 - abs(k)) / _wsum
                j = (i + k) % N_TRACK_SEG
                sthr[i] += wt * self._throttle_map[j]
                sbrk[i] += wt * self._brake_map[j]

        for i in range(n):
            frac = i / n
            bucket = int(frac * N_TRACK_SEG) % N_TRACK_SEG
            thr = sthr[bucket]
            brk = sbrk[bucket]

            if brk > 15:
                t = min(1.0, brk / 100.0)
                col = QColor(int(180 + 75 * t),
                             int(40 * (1 - t)), int(40 * (1 - t)))
            elif thr > 80:
                col = QColor(0, 232, 120)
            elif thr > 30:
                t = (thr - 30) / 50.0
                col = QColor(int(220 * (1 - t)), int(180 + 52 * t), 40)
            else:
                col = QColor(70, 70, 70)

            hm_w = max(1.0, self._w_in * 0.12)
            p.setPen(QPen(col, hm_w, Qt.PenStyle.SolidLine, cap, join))
            p.drawLine(QPointF(*pts[i]), QPointF(*pts[(i + 1) % n]))

        p.end()
        return pm

    @staticmethod
    def _raceline_color(t: float) -> tuple[int, int, int]:
        """Smooth green -> white -> red along t in [0, 1]."""
        if t <= 0.5:
            u = t / 0.5
            r = int(0 + (245 - 0) * u)
            g = int(232 + (245 - 232) * u)
            b = int(120 + (245 - 120) * u)
        else:
            u = (t - 0.5) / 0.5
            r = int(245 + (255 - 245) * u)
            g = int(245 + (60 - 245) * u)
            b = int(245 + (60 - 245) * u)
        return r, g, b

    def _build_raceline_pixmap(self, pts, curv):
        """Render a thin, HD raceline at 30% opacity with a curvature-based gradient."""
        w, h = self.width(), self.height()
        # Supersample: render at 2x resolution so the thin line stays crisp.
        dpr = 2
        pm = QPixmap(w * dpr, h * dpr)
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        if len(pts) < 2 or len(curv) < 2:
            return pm
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cap = Qt.PenCapStyle.RoundCap
        join = Qt.PenJoinStyle.RoundJoin
        n = len(pts)

        SMOOTH_R = 3
        denom = sum((SMOOTH_R + 1 - abs(k))
                    for k in range(-SMOOTH_R, SMOOTH_R + 1))
        sc = [0.0] * n
        for i in range(n):
            s = 0.0
            for k in range(-SMOOTH_R, SMOOTH_R + 1):
                wt = (SMOOTH_R + 1 - abs(k)) / denom
                s += wt * curv[(i + k) % n]
            sc[i] = s

        # Thin line: ~1.5 logical px, kept sub-pixel-crisp by the 2x pixmap.
        width = max(1.0, self._w_in * 0.18)
        alpha = 76  # 30% of 255

        for i in range(n):
            t_mid = 0.5 * (sc[i] + sc[(i + 1) % n])
            r, g, b = self._raceline_color(t_mid)
            p.setPen(QPen(QColor(r, g, b, alpha), width,
                     Qt.PenStyle.SolidLine, cap, join))
            p.drawLine(QPointF(*pts[i]), QPointF(*pts[(i + 1) % n]))

        p.end()
        return pm

    def _trail_color(self, throttle: float, brake: float) -> tuple[int, int, int]:
        """Throttle-green / brake-red / coast-white trail color."""
        if brake > 15:
            return (235, 30, 30)
        if throttle > 30:
            return (0, 220, 90)
        return (245, 245, 245)

    def paintEvent(self, event):
        painter = QPainter(self)

        pts = self._get_pts()
        n = len(pts)

        if n < 2:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._paint_bg_fill(painter, self.width(), self.height())
            painter.setPen(QColor('#444444'))
            from ..constants import sans as _sans
            painter.setFont(_sans(10))
            filled = len(self._world_buckets)
            if filled > 0:
                pct_done = int(filled / N_TRACK_SEG * 100)
                msg = f'Building track map\u2026  {pct_done}%  ({filled} / {N_TRACK_SEG} segments)'
            else:
                msg = 'Drive a lap to build the track map'
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, msg)
            painter.end()
            return

        if self._bg_dirty or self._bg_pixmap is None:
            self._bg_pixmap = self._build_bg_pixmap(pts)
            self._bg_dirty = False
        if self._heatmap_dirty or self._heatmap_pixmap is None:
            self._heatmap_pixmap = self._build_heatmap_pixmap(pts)
            self._heatmap_dirty = False

        show_raceline = (self._show_raceline
                         and len(self._raceline_pts) >= 2
                         and len(self._raceline_curv) >= 2)
        if show_raceline and (self._raceline_dirty or self._raceline_pixmap is None):
            self._raceline_pixmap = self._build_raceline_pixmap(
                self._raceline_pts, self._raceline_curv)
            self._raceline_dirty = False

        # Apply zoom/pan to all overlays. The panel background fill is baked
        # into _bg_pixmap, so transforming it along with everything else keeps
        # the visual composition consistent.
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(self._pan_x, self._pan_y)
        painter.scale(self._zoom, self._zoom)

        painter.drawPixmap(0, 0, self._bg_pixmap)
        painter.drawPixmap(0, 0, self._heatmap_pixmap)
        if show_raceline and self._raceline_pixmap is not None:
            painter.drawPixmap(0, 0, self._raceline_pixmap)

        _full_lap = (not self._world_buckets
                     or len(self._world_buckets) >= int(N_TRACK_SEG * 0.85))
        if not _full_lap:
            painter.restore()
            painter.end()
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # --- Trail: thin, HD (supersampled) line matching the raceline's
        # visual weight. Draw same-color runs as one solid QPainterPath
        # (no per-segment gradients) so transitions read like the reference:
        # a solid color band, then a crisp handoff to the next state's band.
        trail_list = list(self._trail)
        tn = len(trail_list)
        if tn >= 2:
            w_px, h_px = self.width(), self.height()
            dpr = 2
            tpm = QPixmap(w_px * dpr, h_px * dpr)
            tpm.setDevicePixelRatio(dpr)
            tpm.fill(Qt.GlobalColor.transparent)
            tp = QPainter(tpm)
            tp.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Cosmetic pen (width=0 means "always 1 device-pixel wide"); round
            # caps/joins are what bloat a thin stroke into a visible band, so
            # use flat/bevel to keep the trail a true hairline.
            cap = Qt.PenCapStyle.FlatCap
            join = Qt.PenJoinStyle.BevelJoin
            width = 0  # cosmetic

            coords: list[tuple[float, float, tuple[int, int, int]]] = []
            for s, thr, brk in trail_list:
                lo = int(s * n) % n
                hi = (lo + 1) % n
                f = (s * n) - int(s * n)
                x = pts[lo][0] + f * (pts[hi][0] - pts[lo][0])
                y = pts[lo][1] + f * (pts[hi][1] - pts[lo][1])
                coords.append((x, y, self._trail_color(thr, brk)))

            # Group consecutive samples that share a color into runs.
            # Each run is drawn as one solid-color path, and the first
            # vertex of the next run re-uses the last vertex of the
            # previous run so color changes are exact (no gap, no blur).
            run_color = coords[0][2]
            run_pts: list[QPointF] = [QPointF(coords[0][0], coords[0][1])]

            def flush_run(pts_list: list[QPointF], color: tuple[int, int, int]):
                if len(pts_list) < 2:
                    return
                path = QPainterPath()
                path.moveTo(pts_list[0])
                for p in pts_list[1:]:
                    path.lineTo(p)
                pen = QPen(QColor(*color), width,
                           Qt.PenStyle.SolidLine, cap, join)
                tp.setPen(pen)
                tp.setBrush(Qt.BrushStyle.NoBrush)
                tp.drawPath(path)

            for i in range(1, tn):
                s_prev = trail_list[i - 1][0]
                s_cur = trail_list[i][0]
                x, y, c = coords[i]
                pt = QPointF(x, y)

                # S/F wrap: close out the current run, start fresh.
                if abs(s_cur - s_prev) > 0.5:
                    flush_run(run_pts, run_color)
                    run_color = c
                    run_pts = [pt]
                    continue

                if c == run_color:
                    run_pts.append(pt)
                else:
                    # Color change: include the transition point in the
                    # outgoing run so the two runs share an endpoint,
                    # then start the new run from that same point.
                    run_pts.append(pt)
                    flush_run(run_pts, run_color)
                    run_color = c
                    run_pts = [pt]

            flush_run(run_pts, run_color)
            tp.end()
            painter.drawPixmap(0, 0, tpm)

        # --- Car head dot.
        smooth = self._car_smooth
        lo_idx = int(smooth * n) % n
        hi_idx = (lo_idx + 1) % n
        frac = (smooth * n) - int(smooth * n)
        lx, ly = pts[lo_idx]
        hx, hy = pts[hi_idx]
        cx = lx + frac * (hx - lx)
        cy = ly + frac * (hy - ly)
        cp = QPointF(cx, cy)

        # Glow color matches current state (green throttle / red brake).
        gr, gg, gb = self._trail_color(self._cur_throttle, self._cur_brake)
        grad = QRadialGradient(cp, self._car_outer)
        grad.setColorAt(0.0, QColor(gr, gg, gb, 220))
        grad.setColorAt(0.5, QColor(gr, gg, gb,  90))
        grad.setColorAt(1.0, QColor(gr, gg, gb,   0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(cp, self._car_outer, self._car_outer)

        painter.setBrush(QBrush(QColor(gr, gg, gb)))
        painter.setPen(QPen(QColor('#ffffff'), 1.5))
        painter.drawEllipse(cp, self._car_inner, self._car_inner)

        painter.restore()  # close the zoom/pan transform
        painter.end()
