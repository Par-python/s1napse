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

        engine = getattr(app, '_strategy_engine', None)
        st_state = None
        if engine is not None and hasattr(engine, 'state'):
            try:
                st_state = engine.state()
            except Exception:
                st_state = None
        headline = st_state.headline() if st_state is not None else None
        if headline is not None:
            self._banner_label.setText(f'► {headline.severity.upper()}')
            self._banner_msg.setText(headline.text)
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

        # Sectors — last completed lap
        if laps:
            last_lap = laps[-1]
            sectors = last_lap.get('sectors') or []
            for i, sector_lbl in enumerate(self._sector_rows):
                s = sectors[i] if i < len(sectors) else None
                if s is None or s <= 0:
                    sector_lbl.setText('—')
                else:
                    s_total = s / 1000.0
                    mm = int(s_total // 60)
                    rest = s_total - mm * 60
                    sector_lbl.setText(f'{mm}:{rest:06.3f}' if mm else f'{rest:.3f}')

            # Stint rows — Lap N, stint avg, best stint
            self._stint_rows['Lap'].setText(str(len(laps)))
            valid_pts = [t for t in pts if t > 0]
            if valid_pts:
                avg_s = sum(valid_pts) / len(valid_pts)
                best_s = min(valid_pts)
                def _fmt(t):
                    mm = int(t // 60); rest = t - mm * 60
                    return f'{mm}:{rest:06.3f}' if mm else f'{rest:.3f}'
                self._stint_rows['Stint avg'].setText(_fmt(avg_s))
                self._stint_rows['Best stint'].setText(_fmt(best_s))

        ga_ms = (data or {}).get('gap_ahead', 0) or 0
        gb_ms = (data or {}).get('gap_behind', 0) or 0
        ga = ga_ms / 1000.0
        gb = gb_ms / 1000.0
        self._gap_bar.setGaps(-abs(ga), +abs(gb))

        if ga_ms:
            self._gap_ahead_lbl.setText(f'-{abs(ga):.2f}s')
        else:
            self._gap_ahead_lbl.setText('—')
        if gb_ms:
            self._gap_behind_lbl.setText(f'+{abs(gb):.2f}s')
        else:
            self._gap_behind_lbl.setText('—')

        # Gap trend per lap — compare to gap at start of current lap
        cur_lap = int(getattr(app, 'current_lap_count', 0) or 0)
        prev_lap = getattr(self, '_gt_lap', None)
        if prev_lap != cur_lap:
            self._gt_lap = cur_lap
            self._gt_ga_at_lap_start = ga_ms
            self._gt_gb_at_lap_start = gb_ms
        ga_delta = (ga_ms - getattr(self, '_gt_ga_at_lap_start', ga_ms)) / 1000.0
        if abs(ga_delta) >= 0.05:
            verb = 'closing' if ga_delta > 0 else 'opening'
            self._gap_trend.setText(f'{verb} {abs(ga_delta):+.2f}s this lap')
        else:
            self._gap_trend.setText('stable')

        temps = (data or {}).get('tyre_temp') or [None, None, None, None]
        for i, tyre_pos in enumerate(('FL', 'FR', 'RL', 'RR')):
            cell, v = self._tyre_labels[tyre_pos]
            t = temps[i] if i < len(temps) else None
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

        # Tyres-on-set label — driven by app._tyre_stint_laps (resets on pit exit)
        stint_laps = int(getattr(app, '_tyre_stint_laps', 0) or 0)
        if self._tyre_card.headerLabel() is not None:
            stint_word = 'lap' if stint_laps == 1 else 'laps'
            self._tyre_card.headerLabel().setText(f'TYRES · {stint_laps} {stint_word} on set')

        # Pit window + degradation — pulled from StrategyEngine state.
        # ACC has no live "tyre degradation" telemetry; the engine infers it
        # via linear regression over recent lap times. Needs >=3 laps.
        if st_state is not None:
            open_lap = getattr(st_state, 'pit_window_open_lap', None)
            close_lap = getattr(st_state, 'pit_window_close_lap', None)
            current = getattr(st_state, 'current_lap_count', 0) or 0
            if open_lap is not None and close_lap is not None:
                self._pit_window_lbl.setText(f'L {open_lap}–{close_lap}  · now L{current}')
            elif open_lap is not None:
                self._pit_window_lbl.setText(f'L {open_lap}+ · now L{current}')
            else:
                self._pit_window_lbl.setText('—')

            slope = getattr(st_state, 'deg_slope_s_per_lap', None)
            if slope is None:
                self._tyre_deg_lbl.setText('Deg —  ·  fit needs ≥3 laps')
            else:
                # Estimate remaining life: laps until +1.5s lost (cliff heuristic)
                if slope > 0:
                    life = max(0, int(1.5 / slope) - stint_laps)
                    self._tyre_deg_lbl.setText(
                        f'Deg {slope:+.3f} s/lap  ·  life ~{life} laps'
                    )
                else:
                    self._tyre_deg_lbl.setText(f'Deg {slope:+.3f} s/lap  ·  stable')
        else:
            self._pit_window_lbl.setText('—')
            self._tyre_deg_lbl.setText('Deg —  ·  fit needs ≥3 laps')
