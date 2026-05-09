"""Dashboard tab — 30/70 horizontal split.

Layout:
  - LEFT (~30%) : gauges card on top, then 4 stat cards stacked
                  (Speed / Gear / Last lap / Fuel).
  - RIGHT (~70%): LapHistoryPanel, full vertical height — the
                  session lap table is now visible at a glance
                  while driving.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
)

from ... import theme
from ..primitives import Card, Stat, Sparkline
from ..gauges import RevBar, PedalBar, SteeringBar
from ..panels import LapHistoryPanel
from ...constants import C_THROTTLE, C_BRAKE


_LBL_RESET = 'background:transparent; border:none;'


def _label(text: str, *, font, color: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(font)
    lbl.setStyleSheet(f'color:{color}; {_LBL_RESET}')
    return lbl


def _fmt_lap_time(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return '—'
    mm = int(seconds // 60)
    rest = seconds - mm * 60
    return f'{mm}:{rest:06.3f}' if mm else f'{rest:.3f}'


class DashboardTab(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        # ── LEFT column (~30%) — gauges + stacked stat cards ────────────
        left = QVBoxLayout()
        left.setSpacing(12)

        # Gauges card on top
        gauges = Card(label='Inputs', dense=True)
        gauges.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        gauges_row = QHBoxLayout()
        gauges_row.setSpacing(12)

        self._rev = RevBar()
        self._throttle = PedalBar(C_THROTTLE, 'THR')
        self._brake = PedalBar(C_BRAKE, 'BRK')
        self._steer = SteeringBar()

        for w in (self._rev, self._throttle, self._brake, self._steer):
            gauges_row.addWidget(w)
        gauges.body().addLayout(gauges_row)
        left.addWidget(gauges, 0)

        # Stat cards stacked — Speed and Gear stay as quick-glance Stat;
        # Last lap + Fuel match the Race tab layout (PB sub, sparkline, etc.).
        self._speed = Stat(value='—', unit='km/h', size='xl')
        self._gear = Stat(value='—', size='xl')

        for label, stat in (
            ('Speed', self._speed),
            ('Gear', self._gear),
        ):
            c = Card(label=label, dense=True)
            c.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            c.body().addWidget(stat)
            left.addWidget(c, 0)

        # Last lap card (mirrors Race tab)
        last_card = Card(label='Laps trend', dense=True)
        last_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._last_lap_value = _label(
            '—', font=theme.mono_font(theme.FONT_NUMERIC_LG, bold=True),
            color=theme.TEXT_PRIMARY,
        )
        last_card.body().addWidget(self._last_lap_value)
        self._last_lap_sub = _label(
            '—', font=theme.mono_font(11), color=theme.TEXT_MUTED,
        )
        last_card.body().addWidget(self._last_lap_sub)
        self._last_lap_spark = Sparkline()
        last_card.body().addWidget(self._last_lap_spark)
        left.addWidget(last_card, 0)

        # Fuel card (mirrors Race tab)
        fuel_card = Card(label='Fuel', dense=True)
        fuel_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        fuel_row = QHBoxLayout()
        self._fuel_value = _label(
            '—', font=theme.mono_font(theme.FONT_NUMERIC_LG, bold=True),
            color=theme.TEXT_PRIMARY,
        )
        self._fuel_unit = _label('L', font=theme.ui_font(12), color=theme.TEXT_MUTED)
        fuel_row.addWidget(self._fuel_value)
        fuel_row.addWidget(self._fuel_unit, 0, Qt.AlignmentFlag.AlignBottom)
        fuel_row.addStretch(1)
        fuel_card.body().addLayout(fuel_row)
        self._fuel_sub = _label(
            '—', font=theme.ui_font(11), color=theme.TEXT_MUTED,
        )
        self._fuel_sub.setWordWrap(True)
        fuel_card.body().addWidget(self._fuel_sub)
        left.addWidget(fuel_card, 0)

        left.addStretch(1)

        # Wrap left column so we can stretch-control it
        left_container = QWidget()
        left_container.setLayout(left)
        outer.addWidget(left_container, 3)  # 30% via stretch ratio 3:7

        # ── RIGHT column (~70%) — Session laps ──────────────────────────
        laps_card = Card(label='Session laps', dense=False)
        self.lap_history = LapHistoryPanel()
        laps_card.body().addWidget(self.lap_history)
        outer.addWidget(laps_card, 7)

        # Mirror onto app so existing references work (bridge pattern)
        app.lap_history = self.lap_history

    def update_tick(self, data: dict | None) -> None:
        d = data or {}

        rpm = d.get('rpm', 0)
        max_rpm = d.get('max_rpm', 8000)
        self._rev.set_value(rpm, max_rpm)

        self._throttle.set_value(d.get('throttle', 0))
        self._brake.set_value(d.get('brake', 0))

        self._steer.set_angle(d.get('steer_angle', 0.0))
        self._steer.tick_lerp()

        # Stats
        self._speed.valueLabel().setText(f"{d.get('speed', 0):.0f}")

        gear = d.get('gear', 1)
        if gear == 0:
            gear_text = 'R'
        elif gear == 1:
            gear_text = 'N'
        else:
            gear_text = str(gear - 1)
        self._gear.valueLabel().setText(gear_text)

        # Last lap (mirrors RaceTab): big m:ss.mmm, PB sub-line, mini-spark.
        app = self._app
        last_ms = int(getattr(app, 'last_lap_time', 0) or 0)
        if last_ms > 0:
            mm = last_ms // 60000
            ss = (last_ms // 1000) % 60
            ms = last_ms % 1000
            self._last_lap_value.setText(f'{mm}:{ss:02d}.{ms:03d}')

        laps = getattr(app, 'session_laps', []) or []
        lap_times_s = [
            float(l.get('total_time_s', 0) or 0)
            for l in laps if (l.get('total_time_s', 0) or 0) > 0
        ]
        if lap_times_s:
            pb_s = min(lap_times_s)
            self._last_lap_sub.setText(f'PB {_fmt_lap_time(pb_s)}')
            self._last_lap_spark.setPoints(lap_times_s[-12:], ref_value=pb_s)
        else:
            self._last_lap_sub.setText('—')
            self._last_lap_spark.setPoints([])

        # Fuel (mirrors RaceTab): big litres, "X laps left" sub when available.
        fuel_l = float(d.get('fuel', 0.0) or 0.0)
        self._fuel_value.setText(f'{fuel_l:.1f}')
        st_state = None
        engine = getattr(app, '_strategy_engine', None)
        if engine is not None:
            st_state = getattr(engine, 'state', None)
        if st_state is not None and getattr(st_state, 'fuel_laps_left', None) is not None:
            self._fuel_sub.setText(f'{st_state.fuel_laps_left:.1f} laps left')
        else:
            self._fuel_sub.setText('—')
