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


_DELTA_STATES = {
    'good':    theme.GOOD,
    'bad':     theme.BAD,
    'warn':    theme.WARN,
    'neutral': theme.TEXT_MUTED,
}


class Stat(QWidget):
    """Number-forward display: big value (mono), optional unit, optional delta, optional sub.

    Use *inside* a Card.body() — Stat doesn't paint a border itself.
    """

    def __init__(self, *, value: str, unit: str | None = None,
                 delta: str | None = None, delta_state: str = 'neutral',
                 sub: str | None = None,
                 size: str = 'lg',  # 'lg' | 'xl'
                 parent=None):
        if delta is not None and delta_state not in _DELTA_STATES:
            raise ValueError(f'invalid delta_state {delta_state!r}')
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        size_pt = theme.FONT_DISPLAY if size == 'xl' else theme.FONT_NUMERIC_LG
        v = QLabel(value)
        v.setFont(theme.mono_font(size_pt))
        v.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; background:transparent; border:none;')
        row.addWidget(v, 0, Qt.AlignmentFlag.AlignBaseline)
        self._value = v

        self._unit: QLabel | None = None
        if unit:
            u = QLabel(unit)
            u.setFont(theme.ui_font(theme.FONT_BODY_ROOMY))
            u.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
            row.addWidget(u, 0, Qt.AlignmentFlag.AlignBaseline)
            self._unit = u

        self._delta: QLabel | None = None
        if delta is not None:
            d = QLabel(delta)
            d.setFont(theme.mono_font(theme.FONT_NUMERIC_MD))
            d.setStyleSheet(
                f'color:{_DELTA_STATES[delta_state]}; background:transparent; border:none;'
            )
            row.addWidget(d, 0, Qt.AlignmentFlag.AlignBaseline)
            self._delta = d

        row.addStretch(1)
        outer.addLayout(row)

        if sub:
            s = QLabel(sub)
            s.setFont(theme.mono_font(theme.FONT_BODY_DENSE))
            s.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
            outer.addWidget(s)

    def valueLabel(self) -> QLabel:
        return self._value

    def unitLabel(self) -> QLabel | None:
        return self._unit

    def deltaLabel(self) -> QLabel | None:
        return self._delta


class Sparkline(QWidget):
    """Minimal trend line. Optional dashed reference line (e.g. PB)."""

    def __init__(self, *, points: list[float] | None = None,
                 ref_value: float | None = None,
                 accent: str | None = None, parent=None):
        super().__init__(parent)
        self._pts = list(points or [])
        self._ref = ref_value
        self._accent = accent or theme.ACCENT
        self.setMinimumHeight(28)
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def points(self) -> list[float]:
        return list(self._pts)

    def refValue(self) -> float | None:
        return self._ref

    def setPoints(self, pts: list[float], ref_value: float | None = None) -> None:
        self._pts = list(pts)
        if ref_value is not None:
            self._ref = ref_value
        self.update()

    def paintEvent(self, _ev):
        if not self._pts:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        pad_x, pad_y = 2.0, 4.0
        ys = self._pts
        lo = min(ys)
        hi = max(ys)
        if self._ref is not None:
            lo = min(lo, self._ref)
            hi = max(hi, self._ref)
        if hi == lo:
            hi = lo + 1.0
        sx = (w - 2 * pad_x) / max(1, len(ys) - 1)

        def y_to_px(v):
            return pad_y + (1.0 - (v - lo) / (hi - lo)) * (h - 2 * pad_y)

        # Reference line
        if self._ref is not None:
            pen = QPen(QColor(theme.ACCENT))
            pen.setWidthF(1.0)
            pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            ry = y_to_px(self._ref)
            p.drawLine(int(pad_x), int(ry), int(w - pad_x), int(ry))

        # Trend line
        pen = QPen(QColor(self._accent))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        prev = None
        for i, v in enumerate(ys):
            x = pad_x + i * sx
            y = y_to_px(v)
            if prev is not None:
                p.drawLine(int(prev[0]), int(prev[1]), int(x), int(y))
            prev = (x, y)

        # End-cap dot
        if prev is not None:
            p.setBrush(QBrush(QColor(self._accent)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(prev[0]) - 2, int(prev[1]) - 2, 4, 4)
        p.end()


class GapBar(QWidget):
    """±range_s axis with markers for ahead/behind rivals and the user.

    gap_ahead is negative (rival ahead), gap_behind is positive.
    """

    def __init__(self, *, gap_ahead: float = 0.0, gap_behind: float = 0.0,
                 range_s: float = 3.0, parent=None):
        super().__init__(parent)
        self._range = range_s
        self._ga = max(-range_s, min(range_s, gap_ahead))
        self._gb = max(-range_s, min(range_s, gap_behind))
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def range_s(self) -> float:
        return self._range

    def gap_ahead(self) -> float:
        return self._ga

    def gap_behind(self) -> float:
        return self._gb

    def setGaps(self, gap_ahead: float, gap_behind: float) -> None:
        self._ga = max(-self._range, min(self._range, gap_ahead))
        self._gb = max(-self._range, min(self._range, gap_behind))
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        cy = h // 2

        # Track line
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(theme.BORDER_SUBTLE)))
        p.drawRoundedRect(0, cy - 1, w, 2, 1, 1)

        def t_to_x(t: float) -> int:
            # -range -> 0, +range -> w, 0 -> w/2
            return int((t + self._range) / (2 * self._range) * w)

        # Self marker (violet bar)
        sx = w // 2
        p.setBrush(QBrush(QColor(theme.ACCENT)))
        p.drawRoundedRect(sx - 5, cy - 7, 10, 14, 2, 2)

        # Ahead marker
        if self._ga != 0.0:
            ax = t_to_x(self._ga)
            p.setBrush(QBrush(QColor(theme.TEXT_FAINT)))
            p.drawRoundedRect(ax - 3, cy - 4, 6, 8, 1, 1)

        # Behind marker
        if self._gb != 0.0:
            bx = t_to_x(self._gb)
            p.setBrush(QBrush(QColor(theme.TEXT_FAINT)))
            p.drawRoundedRect(bx - 3, cy - 4, 6, 8, 1, 1)

        p.end()
