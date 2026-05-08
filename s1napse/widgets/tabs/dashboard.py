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
    QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
)

from ... import theme
from ..primitives import Card, Stat
from ..gauges import RevBar, PedalBar, SteeringBar
from ..panels import LapHistoryPanel
from ...constants import C_THROTTLE, C_BRAKE


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

        # Stat cards stacked
        self._speed = Stat(value='—', unit='km/h', size='xl')
        self._gear = Stat(value='—', size='xl')
        self._lap = Stat(value='—', sub='—')
        self._fuel = Stat(value='—', unit='L', sub='—')

        for label, stat in (
            ('Speed', self._speed),
            ('Gear', self._gear),
            ('Last lap', self._lap),
            ('Fuel', self._fuel),
        ):
            c = Card(label=label, dense=True)
            c.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            c.body().addWidget(stat)
            left.addWidget(c, 0)

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

        last_ms = int(getattr(self._app, 'last_lap_time', 0))
        if last_ms > 0:
            m = last_ms // 60000
            s = (last_ms // 1000) % 60
            ms = last_ms % 1000
            self._lap.valueLabel().setText(f'{m}:{s:02d}.{ms:03d}')

        self._fuel.valueLabel().setText(f"{d.get('fuel', 0):.1f}")
