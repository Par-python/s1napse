"""Tyres tab — quad layout primary, surrounding cards for pressure / wear / IMO."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame

from ... import theme
from ..primitives import Card, Stat
from ..tyre_card import TyreCard  # existing per-tyre paint widget

# Positional order matches readers: index 0=FL, 1=FR, 2=RL, 3=RR
_POS_ORDER = ['FL', 'FR', 'RL', 'RR']


class TyresTab(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        row = QHBoxLayout()
        row.setSpacing(12)
        outer.addLayout(row, 1)

        # Left — TyreCard quad inside a single Card
        big = Card(label='Tyres', dense=True)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self._tyre_cards = {}
        for i, pos in enumerate(_POS_ORDER):
            tc = TyreCard(pos)
            self._tyre_cards[pos] = tc
            grid.addWidget(tc, i // 2, i % 2)
        big.body().addLayout(grid)
        row.addWidget(big, 2)

        # Right — pressure, wear, IMO stats
        right = QVBoxLayout()
        right.setSpacing(12)

        pressure = Card(label='Pressure (cold target)', dense=True)
        self._pressure_rows = {}
        for pos in _POS_ORDER:
            r = QHBoxLayout()
            k = QLabel(pos)
            k.setFont(theme.ui_font(11))
            k.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
            v = QLabel('—')
            v.setFont(theme.mono_font(13))
            v.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; background:transparent; border:none;')
            r.addWidget(k)
            r.addStretch(1)
            r.addWidget(v)
            pressure.body().addLayout(r)
            self._pressure_rows[pos] = v
        right.addWidget(pressure)

        wear = Card(label='Wear', dense=True)
        self._wear_stat = Stat(value='—')
        wear.body().addWidget(self._wear_stat)
        right.addWidget(wear)

        self._imo_card = Card(label='IMO temp distribution', dense=True)
        self._imo_rows = {}
        for pos in _POS_ORDER:
            r = QHBoxLayout()
            k = QLabel(pos)
            k.setFont(theme.ui_font(11))
            k.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
            v = QLabel('I —  ·  M —  ·  O —')
            v.setFont(theme.mono_font(11))
            v.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; background:transparent; border:none;')
            r.addWidget(k)
            r.addStretch(1)
            r.addWidget(v)
            self._imo_card.body().addLayout(r)
            self._imo_rows[pos] = v
        # IMO is only fed by iRacing today; hide until the active reader
        # actually populates tyre_imo data.
        self._imo_card.setVisible(False)
        right.addWidget(self._imo_card)

        right.addStretch(1)
        row.addLayout(right, 1)

    def update_tick(self, data: dict | None) -> None:
        """Refresh all tyre widgets from the latest telemetry snapshot.

        Expects the same dict format produced by all readers:
          - tyre_temp:     list[float]  [FL, FR, RL, RR] in °C
          - tyre_pressure: list[float]  [FL, FR, RL, RR] in PSI
          - brake_temp:    list[float]  [FL, FR, RL, RR] in °C
          - tyre_wear:     list[float]  [FL, FR, RL, RR] as 0–1 fractions
          - tyre_imo:      dict  {pos: [inner, middle, outer]} (iRacing only, optional)
        """
        if not data:
            for pos, tc in self._tyre_cards.items():
                tc.update_data(0.0, 0.0, 0.0, 0.0)
            for v in self._pressure_rows.values():
                v.setText('—')
            self._wear_stat.valueLabel().setText('—')
            for v in self._imo_rows.values():
                v.setText('I —  ·  M —  ·  O —')
            self._imo_card.setVisible(False)
            return

        t_temps  = data.get('tyre_temp',     [0.0, 0.0, 0.0, 0.0])
        t_pres   = data.get('tyre_pressure', [0.0, 0.0, 0.0, 0.0])
        t_brake  = data.get('brake_temp',    [0.0, 0.0, 0.0, 0.0])
        t_wear   = data.get('tyre_wear',     [0.0, 0.0, 0.0, 0.0])
        t_imo    = data.get('tyre_imo',      {})

        for i, pos in enumerate(_POS_ORDER):
            temp  = t_temps[i]  if i < len(t_temps)  else 0.0
            pres  = t_pres[i]   if i < len(t_pres)   else 0.0
            brake = t_brake[i]  if i < len(t_brake)  else 0.0
            wear  = t_wear[i]   if i < len(t_wear)   else 0.0
            # wear is stored as 0–1 fraction from readers; TyreCard expects %
            self._tyre_cards[pos].update_data(temp, pres, brake, wear * 100.0)

        # Pressure labels
        for i, pos in enumerate(_POS_ORDER):
            psi = t_pres[i] if i < len(t_pres) else 0.0
            self._pressure_rows[pos].setText(f'{psi:.2f} psi' if psi > 0 else '—')

        # Wear summary
        valid_wear = [w for w in t_wear if w is not None and w > 0]
        if valid_wear:
            avg_wear_pct = sum(valid_wear) / len(valid_wear) * 100.0
            self._wear_stat.valueLabel().setText(f'{avg_wear_pct:.1f}%')
        else:
            self._wear_stat.valueLabel().setText('—')

        # IMO rows — only iRacing populates tyre_imo. Show the card when at
        # least one tyre reports a real IMO triplet; hide it otherwise.
        has_imo = False
        if isinstance(t_imo, dict):
            for triplet in t_imo.values():
                if triplet and len(triplet) >= 3 and any(v > 0 for v in triplet[:3]):
                    has_imo = True
                    break
        self._imo_card.setVisible(has_imo)
        if has_imo:
            for pos, v in self._imo_rows.items():
                imo = t_imo.get(pos) if isinstance(t_imo, dict) else None
                if imo and len(imo) >= 3:
                    v.setText(f'I {imo[0]:.0f}  ·  M {imo[1]:.0f}  ·  O {imo[2]:.0f}')
                else:
                    v.setText('I —  ·  M —  ·  O —')
