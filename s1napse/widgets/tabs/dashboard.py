"""Dashboard tab — selective gauges + summary card grid.

Gauges keep their place because they're visual by nature.
Numeric values move into Stat-cards.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout

from ... import theme
from ..primitives import Card, Stat
from ..gauges import RevBar, PedalBar, SteeringBar
from ..panels import LapHistoryPanel
from ...constants import C_THROTTLE, C_BRAKE


class DashboardTab(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        # Gauges row
        gauges = Card(label='Inputs', dense=True)
        row = QHBoxLayout()
        row.setSpacing(16)

        self._rev = RevBar()
        self._throttle = PedalBar(C_THROTTLE, 'THR')
        self._brake = PedalBar(C_BRAKE, 'BRK')
        self._steer = SteeringBar()

        for w in (self._rev, self._throttle, self._brake, self._steer):
            row.addWidget(w)
        gauges.body().addLayout(row)
        outer.addWidget(gauges)

        # 2x2 Stat grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        outer.addLayout(grid, 1)

        self._speed = Stat(value='—', unit='km/h', size='xl')
        self._gear = Stat(value='—', size='xl')
        self._lap = Stat(value='—', sub='—')
        self._fuel = Stat(value='—', unit='L', sub='—')

        for i, (label, stat) in enumerate([
            ('Speed', self._speed),
            ('Gear', self._gear),
            ('Last lap', self._lap),
            ('Fuel', self._fuel),
        ]):
            c = Card(label=label, dense=True)
            c.body().addWidget(stat)
            grid.addWidget(c, i // 2, i % 2)

        # Lap history panel — recent laps table
        self.lap_history = LapHistoryPanel()
        outer.addWidget(self.lap_history, stretch=1)

        # Mirror onto app so existing references work (bridge pattern)
        app.lap_history = self.lap_history

        outer.addStretch(0)

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
