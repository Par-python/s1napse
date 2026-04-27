"""Race tab — pace / position / car columns + headline strip.

Layout follows docs/superpowers/specs/2026-04-26-ui-revamp-design.md, the
approved Race-tab v1 mockup.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame,
)

from ... import theme
from ..primitives import Card, Pill, Stat, Sparkline, GapBar


class RaceTab(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        self._headline = self._build_headline()
        outer.addWidget(self._headline)

        body = QHBoxLayout()
        body.setSpacing(12)
        outer.addLayout(body, 1)

        body.addLayout(self._build_pace_column(), 1)
        body.addLayout(self._build_position_column(), 1)
        body.addLayout(self._build_car_column(), 1)

    # ---- Headline ----------------------------------------------------
    def _build_headline(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f'background:{theme.SURFACE}; border:1px solid {theme.BORDER_SUBTLE};'
            f'border-radius:{theme.RADIUS["lg"]}px;'
        )
        row = QHBoxLayout(f)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(20)

        self._pos_num = QLabel('—')
        self._pos_num.setFont(theme.mono_font(36, bold=True))
        self._pos_num.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; background:transparent; border:none;')
        self._pos_of = QLabel('/ —')
        self._pos_of.setFont(theme.mono_font(13))
        self._pos_of.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
        pos_box = QHBoxLayout()
        pos_box.setSpacing(8)
        pos_box.addWidget(self._pos_num)
        pos_box.addWidget(self._pos_of, 0, Qt.AlignmentFlag.AlignBottom)
        row.addLayout(pos_box, 0)

        div = QFrame()
        div.setFixedWidth(1)
        div.setStyleSheet(f'background:{theme.BORDER_SUBTLE}; border:none;')
        row.addWidget(div)

        banner = QVBoxLayout()
        banner.setSpacing(2)
        self._banner_label = QLabel('► STRATEGY')
        self._banner_label.setFont(theme.label_font())
        self._banner_label.setStyleSheet(
            f'color:{theme.ACCENT_FG}; background:transparent; border:none; letter-spacing:0.7px;'
        )
        banner.addWidget(self._banner_label)
        self._banner_msg = QLabel('Awaiting live data…')
        self._banner_msg.setFont(theme.ui_font(13, bold=True))
        self._banner_msg.setStyleSheet(
            f'color:{theme.TEXT_PRIMARY}; background:transparent; border:none;'
        )
        self._banner_msg.setWordWrap(True)
        banner.addWidget(self._banner_msg)
        row.addLayout(banner, 1)
        return f

    # ---- Pace column -------------------------------------------------
    def _build_pace_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(12)

        last_card = Card(label='Last lap', dense=True)
        self._last_lap_stat = Stat(value='—', delta=None, sub='')
        last_card.body().addWidget(self._last_lap_stat)
        self._last_lap_spark = Sparkline()
        last_card.body().addWidget(self._last_lap_spark)
        col.addWidget(last_card)

        sectors_card = Card(label='Sectors (last)', dense=True)
        self._sector_rows = []
        for label in ('S1', 'S2', 'S3'):
            r = QHBoxLayout()
            r.setContentsMargins(0, 0, 0, 0)
            k = QLabel(label)
            k.setFont(theme.ui_font(11))
            k.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
            v = QLabel('—')
            v.setFont(theme.mono_font(12))
            v.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; background:transparent; border:none;')
            r.addWidget(k); r.addStretch(1); r.addWidget(v)
            sectors_card.body().addLayout(r)
            self._sector_rows.append(v)
        col.addWidget(sectors_card)

        col.addStretch(1)
        return col

    # ---- Position column --------------------------------------------
    def _build_position_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(12)

        gaps_card = Card(label='Gap to rivals', dense=True)
        head_row = QHBoxLayout()
        self._gap_ahead_lbl = QLabel('P— —.—')
        self._gap_behind_lbl = QLabel('P— +—.—')
        for lbl in (self._gap_ahead_lbl, self._gap_behind_lbl):
            lbl.setFont(theme.mono_font(theme.FONT_NUMERIC_LG))
            lbl.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; background:transparent; border:none;')
        head_row.addWidget(self._gap_ahead_lbl)
        head_row.addStretch(1)
        head_row.addWidget(self._gap_behind_lbl)
        gaps_card.body().addLayout(head_row)
        self._gap_bar = GapBar()
        gaps_card.body().addWidget(self._gap_bar)
        self._gap_trend = QLabel('—')
        self._gap_trend.setFont(theme.mono_font(11))
        self._gap_trend.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
        gaps_card.body().addWidget(self._gap_trend)
        col.addWidget(gaps_card)

        pit_card = Card(label='Pit window', dense=True)
        self._pit_window_lbl = QLabel('—')
        self._pit_window_lbl.setFont(theme.mono_font(theme.FONT_NUMERIC_LG))
        self._pit_window_lbl.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; background:transparent; border:none;')
        pit_card.body().addWidget(self._pit_window_lbl)
        col.addWidget(pit_card)

        col.addStretch(1)
        return col

    # ---- Car column --------------------------------------------------
    def _build_car_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(12)

        tyre_card = Card(label='Tyres · — laps on set', dense=True)
        self._tyre_card = tyre_card
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self._tyre_labels = {}
        for i, tyre_pos in enumerate(['FL', 'FR', 'RL', 'RR']):
            cell = QFrame()
            cell.setStyleSheet(
                f'background:{theme.SURFACE_RAISED}; border:1px solid {theme.BORDER_SUBTLE};'
                f'border-radius:{theme.RADIUS["md"]}px;'
            )
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(10, 8, 10, 8)
            k = QLabel(tyre_pos)
            k.setFont(theme.label_font())
            k.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
            v = QLabel('—')
            v.setFont(theme.mono_font(14))
            v.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; background:transparent; border:none;')
            cl.addWidget(k); cl.addStretch(1); cl.addWidget(v)
            row = i // 2; colp = i % 2
            grid.addWidget(cell, row, colp)
            self._tyre_labels[tyre_pos] = (cell, v)
        tyre_card.body().addLayout(grid)
        self._tyre_deg_lbl = QLabel('Deg —  ·  life ~— laps')
        self._tyre_deg_lbl.setFont(theme.mono_font(11))
        self._tyre_deg_lbl.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
        tyre_card.body().addWidget(self._tyre_deg_lbl)
        col.addWidget(tyre_card)

        fuel_card = Card(label='Fuel', dense=True)
        self._fuel_stat = Stat(value='—', unit='L', sub='—')
        fuel_card.body().addWidget(self._fuel_stat)
        col.addWidget(fuel_card)

        stint_card = Card(label='Stint', dense=True)
        self._stint_rows = {}
        for k in ('Lap', 'Stint avg', 'Best stint'):
            r = QHBoxLayout()
            kl = QLabel(k)
            kl.setFont(theme.ui_font(11))
            kl.setStyleSheet(f'color:{theme.TEXT_MUTED}; background:transparent; border:none;')
            v = QLabel('—')
            v.setFont(theme.mono_font(12))
            v.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; background:transparent; border:none;')
            r.addWidget(kl); r.addStretch(1); r.addWidget(v)
            stint_card.body().addLayout(r)
            self._stint_rows[k] = v
        col.addWidget(stint_card)

        col.addStretch(1)
        return col

    # ---- Per-tick update --------------------------------------------
    def update_tick(self, data: dict | None) -> None:
        app = self._app

        pos = (data or {}).get('position', 0)
        total = (data or {}).get('num_cars', 0)
        if pos:
            self._pos_num.setText(f'P{int(pos)}')
        if total:
            self._pos_of.setText(f'/ {int(total)}')

        st = getattr(app, '_strategy_engine', None)
        headline = st.headline() if (st is not None and hasattr(st, 'headline')) else None
        if headline is not None:
            self._banner_label.setText(f'► {headline.label.upper()}')
            self._banner_msg.setText(headline.message)
        else:
            self._banner_label.setText('► STRATEGY')
            self._banner_msg.setText('Holding pace.')

        last_ms = int(getattr(app, 'last_lap_time', 0))
        if last_ms > 0:
            mm = last_ms // 60000
            ss = (last_ms // 1000) % 60
            ms = last_ms % 1000
            self._last_lap_stat.valueLabel().setText(f'{mm}:{ss:02d}.{ms:03d}')

        laps = getattr(app, 'session_laps', []) or []
        pts = [l.get('time_ms', 0) / 1000.0 for l in laps[-12:] if l.get('time_ms', 0) > 0]
        pb = min(pts) if pts else None
        self._last_lap_spark.setPoints(pts, ref_value=pb)

        ga = (data or {}).get('gap_ahead_ms', 0) / 1000.0
        gb = (data or {}).get('gap_behind_ms', 0) / 1000.0
        self._gap_bar.setGaps(-abs(ga), +abs(gb))

        temps = (data or {}).get('tyre_temps', {}) or {}
        for tyre_pos in ('FL', 'FR', 'RL', 'RR'):
            cell, v = self._tyre_labels[tyre_pos]
            t = temps.get(tyre_pos)
            if t is None:
                v.setText('—')
                continue
            v.setText(f'{t:.1f}')
            tone_color = theme.TEXT_PRIMARY
            border = theme.BORDER_SUBTLE
            if   t > 105: tone_color = theme.BAD;  border = 'rgba(239,68,68,0.40)'
            elif t < 70:  tone_color = theme.INFO; border = 'rgba(34,211,238,0.30)'
            v.setStyleSheet(f'color:{tone_color}; background:transparent; border:none;')
            cell.setStyleSheet(
                f'background:{theme.SURFACE_RAISED}; border:1px solid {border};'
                f'border-radius:{theme.RADIUS["md"]}px;'
            )

        fuel_l = (data or {}).get('fuel', 0.0)
        self._fuel_stat.valueLabel().setText(f'{fuel_l:.1f}')
