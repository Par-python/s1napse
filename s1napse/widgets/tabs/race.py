"""Race tab — merged pace / position / car / strategy view.

This tab is the single live-driving cockpit. It rolls up everything that
used to live across the Race + Strategy tabs:

- Headline strip: position (P4 / 22) + live strategy banner from the
  StrategyEngine (rival pit alert, pit window open, weather change, …).
- Pace column: last lap, lap-trend sparkline (last 12 vs PB), sector splits,
  stint summary.
- Position column: gap to rivals (numbers + GapBar visualizer), per-lap gap
  trend, rival watch (inferred pit detection on either side).
- Car column: live tyre quad with cold/hot tinting, tyre stint label, tyre
  degradation projection from the engine, fuel readout, pit-window range.
- Bottom row: two compact strategy calculators — fuel-save (laps-to-go input
  → required save rate) and undercut/overcut (pit-loss + pace-delta inputs).

Reads from `app._strategy_engine.state` (a @property returning the live
StrategyState). All numbers are formatted defensively — missing data shows
as '—' rather than crashing.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame,
    QSpinBox, QDoubleSpinBox, QSizePolicy,
)

from ... import theme
from ..primitives import Card, Stat, Sparkline, GapBar


_LBL_RESET = 'background:transparent; border:none;'


def _label(text: str, *, font, color: str) -> QLabel:
    """One-liner for a styled QLabel that won't inherit Card borders."""
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


class RaceTab(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app
        self._gt_lap = -1
        self._gt_ga_at_lap_start = 0
        self._gt_gb_at_lap_start = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        outer.addWidget(self._build_headline())

        body = QHBoxLayout()
        body.setSpacing(12)
        outer.addLayout(body, 1)

        body.addLayout(self._build_pace_column(), 1)
        body.addLayout(self._build_position_column(), 1)
        body.addLayout(self._build_car_column(), 1)

        # Bottom row — strategy calculators (full-width)
        outer.addLayout(self._build_calculators_row(), 0)

    # ---------------------------------------------------------------------
    # Headline
    # ---------------------------------------------------------------------
    def _build_headline(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f'background:{theme.SURFACE}; border:1px solid {theme.BORDER_SUBTLE};'
            f'border-radius:{theme.RADIUS["lg"]}px;'
        )
        f.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(f)
        row.setContentsMargins(18, 12, 18, 12)
        row.setSpacing(20)

        # Big position
        self._pos_num = _label('—', font=theme.mono_font(36, bold=True),
                               color=theme.TEXT_PRIMARY)
        self._pos_of = _label('/ —', font=theme.mono_font(13),
                              color=theme.TEXT_MUTED)
        pos_box = QHBoxLayout()
        pos_box.setSpacing(8)
        pos_box.addWidget(self._pos_num)
        pos_box.addWidget(self._pos_of, 0, Qt.AlignmentFlag.AlignBottom)
        row.addLayout(pos_box, 0)

        div = QFrame()
        div.setFixedWidth(1)
        div.setStyleSheet(f'background:{theme.BORDER_SUBTLE}; border:none;')
        row.addWidget(div)

        # Banner column
        banner = QVBoxLayout()
        banner.setSpacing(2)
        self._banner_label = _label('► STRATEGY', font=theme.label_font(),
                                    color=theme.ACCENT_FG)
        banner.addWidget(self._banner_label)
        self._banner_msg = _label('Awaiting live data…',
                                  font=theme.ui_font(13, bold=True),
                                  color=theme.TEXT_PRIMARY)
        self._banner_msg.setWordWrap(True)
        banner.addWidget(self._banner_msg)
        row.addLayout(banner, 1)
        return f

    # ---------------------------------------------------------------------
    # Pace column
    # ---------------------------------------------------------------------
    def _build_pace_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(12)

        # Last lap card
        last_card = Card(label='Last lap', dense=True)
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
        col.addWidget(last_card)

        # Sectors card — uppercase keys (left), big mono values (right)
        sectors_card = Card(label='Sectors (last)', dense=True)
        self._sector_rows = []
        for label_text in ('S1', 'S2', 'S3'):
            r = QHBoxLayout()
            r.setContentsMargins(0, 0, 0, 0)
            r.setSpacing(8)
            k = _label(label_text, font=theme.label_font(), color=theme.TEXT_MUTED)
            v = _label(
                '—', font=theme.mono_font(theme.FONT_NUMERIC_LG, bold=True),
                color=theme.TEXT_PRIMARY,
            )
            r.addWidget(k, 0, Qt.AlignmentFlag.AlignBaseline)
            r.addStretch(1)
            r.addWidget(v, 0, Qt.AlignmentFlag.AlignBaseline)
            sectors_card.body().addLayout(r)
            self._sector_rows.append(v)
        col.addWidget(sectors_card)

        # Stint card — same key/value rhythm as Sectors
        stint_card = Card(label='Stint', dense=True)
        self._stint_rows = {}
        for k_text in ('Lap', 'Stint avg', 'Best stint'):
            r = QHBoxLayout()
            r.setContentsMargins(0, 0, 0, 0)
            r.setSpacing(8)
            kl = _label(k_text.upper(), font=theme.label_font(), color=theme.TEXT_MUTED)
            v = _label(
                '—', font=theme.mono_font(theme.FONT_NUMERIC_MD, bold=True),
                color=theme.TEXT_PRIMARY,
            )
            r.addWidget(kl, 0, Qt.AlignmentFlag.AlignBaseline)
            r.addStretch(1)
            r.addWidget(v, 0, Qt.AlignmentFlag.AlignBaseline)
            stint_card.body().addLayout(r)
            self._stint_rows[k_text] = v
        col.addWidget(stint_card)

        col.addStretch(1)
        return col

    # ---------------------------------------------------------------------
    # Position column
    # ---------------------------------------------------------------------
    def _build_position_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(12)

        # Gap card
        gaps_card = Card(label='Gap to rivals', dense=True)
        head_row = QHBoxLayout()
        self._gap_ahead_lbl = _label(
            '—', font=theme.mono_font(theme.FONT_NUMERIC_LG, bold=True),
            color=theme.TEXT_PRIMARY,
        )
        self._gap_behind_lbl = _label(
            '—', font=theme.mono_font(theme.FONT_NUMERIC_LG, bold=True),
            color=theme.TEXT_PRIMARY,
        )
        head_row.addWidget(self._gap_ahead_lbl)
        head_row.addStretch(1)
        head_row.addWidget(self._gap_behind_lbl)
        gaps_card.body().addLayout(head_row)
        self._gap_bar = GapBar()
        gaps_card.body().addWidget(self._gap_bar)
        self._gap_trend = _label(
            '—', font=theme.mono_font(11), color=theme.TEXT_MUTED,
        )
        gaps_card.body().addWidget(self._gap_trend)
        col.addWidget(gaps_card)

        # Rival watch (prose — ui_font, not mono)
        rival_card = Card(label='Rival watch', dense=True)
        self._rw_ahead = _label(
            'Ahead: —', font=theme.ui_font(12), color=theme.TEXT_SECONDARY,
        )
        self._rw_behind = _label(
            'Behind: —', font=theme.ui_font(12), color=theme.TEXT_SECONDARY,
        )
        self._rw_ahead.setWordWrap(True)
        self._rw_behind.setWordWrap(True)
        rival_card.body().addWidget(self._rw_ahead)
        rival_card.body().addWidget(self._rw_behind)
        col.addWidget(rival_card)

        # Weather watch (prose with one mono temperature reading)
        weather_card = Card(label='Weather / track temp', dense=True)
        self._weather_lbl = _label(
            '—', font=theme.ui_font(12), color=theme.TEXT_PRIMARY,
        )
        self._weather_lbl.setWordWrap(True)
        weather_card.body().addWidget(self._weather_lbl)
        col.addWidget(weather_card)

        col.addStretch(1)
        return col

    # ---------------------------------------------------------------------
    # Car column
    # ---------------------------------------------------------------------
    def _build_car_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(12)

        # Tyres card with quad
        self._tyre_card = Card(label='Tyres · — laps on set', dense=True)
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self._tyre_labels = {}
        for i, tyre_pos in enumerate(('FL', 'FR', 'RL', 'RR')):
            cell = QFrame()
            cell.setStyleSheet(
                f'background:{theme.SURFACE_RAISED}; border:1px solid {theme.BORDER_SUBTLE};'
                f'border-radius:{theme.RADIUS["md"]}px;'
            )
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(10, 8, 10, 8)
            k = _label(tyre_pos, font=theme.label_font(), color=theme.TEXT_MUTED)
            v = _label('—', font=theme.mono_font(14, bold=True), color=theme.TEXT_PRIMARY)
            cl.addWidget(k); cl.addStretch(1); cl.addWidget(v)
            row, colp = i // 2, i % 2
            grid.addWidget(cell, row, colp)
            self._tyre_labels[tyre_pos] = (cell, v)
        self._tyre_card.body().addLayout(grid)
        self._tyre_deg_lbl = _label(
            'Deg —  ·  fit needs ≥3 laps',
            font=theme.mono_font(11), color=theme.TEXT_MUTED,
        )
        self._tyre_card.body().addWidget(self._tyre_deg_lbl)
        col.addWidget(self._tyre_card)

        # Fuel card
        fuel_card = Card(label='Fuel', dense=True)
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
        col.addWidget(fuel_card)

        # Pit window card — big number, prose sub
        pit_card = Card(label='Pit window', dense=True)
        self._pit_window_lbl = _label(
            '—', font=theme.mono_font(theme.FONT_DISPLAY, bold=True),
            color=theme.TEXT_PRIMARY,
        )
        pit_card.body().addWidget(self._pit_window_lbl)
        self._pit_sub = _label(
            'Complete a lap to estimate.',
            font=theme.ui_font(11), color=theme.TEXT_MUTED,
        )
        self._pit_sub.setWordWrap(True)
        pit_card.body().addWidget(self._pit_sub)
        col.addWidget(pit_card)

        col.addStretch(1)
        return col

    # ---------------------------------------------------------------------
    # Calculators row (bottom)
    # ---------------------------------------------------------------------
    def _build_calculators_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        # Fuel save calculator
        fs_card = Card(label='Fuel save calculator', dense=True)
        fs_input_row = QHBoxLayout()
        fs_input_row.addWidget(_label('LAPS TO GO', font=theme.label_font(),
                                      color=theme.TEXT_MUTED))
        self._fs_laps_spin = QSpinBox()
        self._fs_laps_spin.setRange(1, 99)
        self._fs_laps_spin.setValue(10)
        self._fs_laps_spin.setFixedWidth(70)
        fs_input_row.addWidget(self._fs_laps_spin)
        fs_input_row.addStretch(1)
        fs_card.body().addLayout(fs_input_row)
        self._fs_result_lbl = _label(
            '—', font=theme.mono_font(theme.FONT_NUMERIC_MD, bold=True),
            color=theme.TEXT_PRIMARY,
        )
        self._fs_result_lbl.setWordWrap(True)
        fs_card.body().addSpacing(4)
        fs_card.body().addWidget(self._fs_result_lbl)
        row.addWidget(fs_card, 1)

        # Undercut/overcut calculator
        uco_card = Card(label='Undercut / overcut', dense=True)
        uco_inputs = QHBoxLayout()
        uco_inputs.setSpacing(20)

        def _spin_col(label_text, attr, default, mn, mx, step, decimals, width=80):
            c = QVBoxLayout()
            c.setSpacing(2)
            c.addWidget(_label(label_text, font=theme.label_font(),
                               color=theme.TEXT_MUTED))
            spin = QDoubleSpinBox()
            spin.setRange(mn, mx)
            spin.setValue(default)
            spin.setSingleStep(step)
            spin.setDecimals(decimals)
            spin.setFixedWidth(width)
            c.addWidget(spin)
            setattr(self, attr, spin)
            return c

        uco_inputs.addLayout(_spin_col('PIT LOSS (s)', '_uco_pit_loss_spin',
                                        22.0, 10.0, 60.0, 0.5, 1))
        uco_inputs.addLayout(_spin_col('PACE Δ (s/lap)', '_uco_pace_delta_spin',
                                        0.8, 0.0, 5.0, 0.1, 1))
        uco_inputs.addStretch(1)
        uco_card.body().addLayout(uco_inputs)
        uco_card.body().addSpacing(4)
        self._uco_undercut_lbl = _label(
            'UNDERCUT: —', font=theme.ui_font(12, bold=True),
            color=theme.TEXT_SECONDARY,
        )
        self._uco_undercut_lbl.setWordWrap(True)
        self._uco_overcut_lbl = _label(
            'OVERCUT: —', font=theme.ui_font(12, bold=True),
            color=theme.TEXT_SECONDARY,
        )
        self._uco_overcut_lbl.setWordWrap(True)
        uco_card.body().addWidget(self._uco_undercut_lbl)
        uco_card.body().addWidget(self._uco_overcut_lbl)
        row.addWidget(uco_card, 1)

        return row

    # ---------------------------------------------------------------------
    # Public API for back-compat with strategy_tab consumers
    # ---------------------------------------------------------------------
    def has_alert(self) -> bool:
        """Return True when a high-priority strategy alert is active."""
        engine = getattr(self._app, '_strategy_engine', None)
        if engine is None:
            return False
        try:
            h = engine.state.headline()
            return h is not None and (h.severity or '').lower() in ('red', 'amber')
        except Exception:
            return False

    # ---------------------------------------------------------------------
    # Per-tick update
    # ---------------------------------------------------------------------
    def update_tick(self, data: dict | None) -> None:
        app = self._app
        d = data or {}

        # ── Position ─────────────────────────────────────────────────────
        pos = d.get('position', 0) or 0
        total = d.get('num_cars', 0) or 0
        if pos:
            self._pos_num.setText(f'P{int(pos)}')
        if total:
            self._pos_of.setText(f'/ {int(total)}')

        # ── Strategy state (engine) ──────────────────────────────────────
        engine = getattr(app, '_strategy_engine', None)
        st_state = None
        if engine is not None:
            try:
                # `state` is a @property → returns StrategyState directly.
                st_state = engine.state
            except Exception:
                st_state = None

        # ── Headline banner ──────────────────────────────────────────────
        if st_state is not None:
            try:
                headline = st_state.headline()
            except Exception:
                headline = None
            if headline is not None:
                severity = (headline.severity or '').lower()
                if severity == 'red':
                    color = theme.BAD
                elif severity == 'amber':
                    color = theme.WARN
                elif severity == 'green':
                    color = theme.GOOD
                else:
                    color = theme.ACCENT_FG
                self._banner_label.setText(f'► {headline.severity.upper()}')
                self._banner_label.setStyleSheet(
                    f'color:{color}; {_LBL_RESET} letter-spacing:0.7px;'
                )
                self._banner_msg.setText(headline.text)
            else:
                self._banner_label.setText('► STRATEGY')
                self._banner_label.setStyleSheet(
                    f'color:{theme.ACCENT_FG}; {_LBL_RESET} letter-spacing:0.7px;'
                )
                self._banner_msg.setText('Holding pace.')

        # ── Last lap (from app.last_lap_time, ms) ────────────────────────
        last_ms = int(getattr(app, 'last_lap_time', 0) or 0)
        if last_ms > 0:
            mm = last_ms // 60000
            ss = (last_ms // 1000) % 60
            ms = last_ms % 1000
            self._last_lap_value.setText(f'{mm}:{ss:02d}.{ms:03d}')

        laps = getattr(app, 'session_laps', []) or []
        # Lap times are stored as float seconds in 'total_time_s'.
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

        # ── Sectors (already in seconds — _compute_sector_times returns s) ──
        if laps:
            last_lap = laps[-1]
            sectors = last_lap.get('sectors') or []
            for i, sector_lbl in enumerate(self._sector_rows):
                s_val = sectors[i] if i < len(sectors) else None
                if s_val is None or s_val <= 0:
                    sector_lbl.setText('—')
                else:
                    sector_lbl.setText(_fmt_lap_time(float(s_val)))

            # Stint
            self._stint_rows['Lap'].setText(str(len(laps)))
            if lap_times_s:
                avg_s = sum(lap_times_s) / len(lap_times_s)
                self._stint_rows['Stint avg'].setText(_fmt_lap_time(avg_s))
                self._stint_rows['Best stint'].setText(_fmt_lap_time(min(lap_times_s)))

        # ── Gaps ─────────────────────────────────────────────────────────
        ga_ms = d.get('gap_ahead', 0) or 0
        gb_ms = d.get('gap_behind', 0) or 0
        ga = ga_ms / 1000.0
        gb = gb_ms / 1000.0
        self._gap_bar.setGaps(-abs(ga), +abs(gb))
        self._gap_ahead_lbl.setText(f'-{abs(ga):.2f}s' if ga_ms else '—')
        self._gap_behind_lbl.setText(f'+{abs(gb):.2f}s' if gb_ms else '—')

        cur_lap = int(getattr(app, 'current_lap_count', 0) or 0)
        if self._gt_lap != cur_lap:
            self._gt_lap = cur_lap
            self._gt_ga_at_lap_start = ga_ms
            self._gt_gb_at_lap_start = gb_ms
        ga_delta_s = (ga_ms - self._gt_ga_at_lap_start) / 1000.0
        if abs(ga_delta_s) >= 0.05:
            verb = 'closing' if ga_delta_s < 0 else 'opening'
            self._gap_trend.setText(f'{verb} {abs(ga_delta_s):+.2f}s this lap')
        else:
            self._gap_trend.setText('stable')

        # ── Rival watch (from engine) ────────────────────────────────────
        if st_state is not None:
            import time as _time
            now = _time.monotonic()

            def _rival_str(prefix, gap_ms_val, pitted_at):
                gap_s = abs(gap_ms_val) / 1000.0
                if pitted_at is not None and (now - pitted_at) <= 30.0:
                    age = int(now - pitted_at)
                    return f'{prefix}: PITTED LIKELY ({age}s ago, gap {gap_s:.1f}s)'
                return f'{prefix}: stable (gap {gap_s:.1f}s)'

            self._rw_ahead.setText(_rival_str(
                'Ahead', st_state.last_gap_ahead_ms, st_state.rival_ahead_pitted_at,
            ))
            self._rw_behind.setText(_rival_str(
                'Behind', st_state.last_gap_behind_ms, st_state.rival_behind_pitted_at,
            ))
            for lbl, pitted_at in (
                (self._rw_ahead, st_state.rival_ahead_pitted_at),
                (self._rw_behind, st_state.rival_behind_pitted_at),
            ):
                if pitted_at is not None and (now - pitted_at) <= 30.0:
                    lbl.setStyleSheet(f'color:{theme.WARN}; {_LBL_RESET}')
                else:
                    lbl.setStyleSheet(f'color:{theme.TEXT_SECONDARY}; {_LBL_RESET}')

            # Weather watch
            if st_state.track_temp_c is None:
                self._weather_lbl.setText('No track-temp data.')
            else:
                air_str = (f' (air {st_state.air_temp_c:.1f}°C)'
                           if st_state.air_temp_c is not None else '')
                if st_state.track_temp_at_stint_start_c is None:
                    self._weather_lbl.setText(
                        f'Track {st_state.track_temp_c:.1f}°C{air_str}')
                else:
                    delta = st_state.track_temp_c - st_state.track_temp_at_stint_start_c
                    if abs(delta) <= 5.0:
                        note = 'stable'
                    elif delta < 0:
                        note = f'cooling {abs(delta):.0f}°C — more tyre life'
                    else:
                        note = f'heating {delta:.0f}°C — more degradation'
                    self._weather_lbl.setText(
                        f'Track {st_state.track_temp_c:.1f}°C{air_str} · {note}')

        # ── Tyres (live) ─────────────────────────────────────────────────
        # tyre_temp emitted by readers as list[FL,FR,RL,RR] in °C
        temps = d.get('tyre_temp') or [None] * 4
        for i, tyre_pos in enumerate(('FL', 'FR', 'RL', 'RR')):
            cell, v = self._tyre_labels[tyre_pos]
            t = temps[i] if i < len(temps) else None
            if t is None:
                v.setText('—')
                v.setStyleSheet(f'color:{theme.TEXT_PRIMARY}; {_LBL_RESET}')
                cell.setStyleSheet(
                    f'background:{theme.SURFACE_RAISED}; border:1px solid {theme.BORDER_SUBTLE};'
                    f'border-radius:{theme.RADIUS["md"]}px;'
                )
                continue
            v.setText(f'{t:.1f}')
            tone_color = theme.TEXT_PRIMARY
            border = theme.BORDER_SUBTLE
            if t > 105:
                tone_color = theme.BAD
                border = theme.BAD_BORDER
            elif t < 70:
                tone_color = theme.INFO
                border = 'rgba(34,211,238,0.30)'
            v.setStyleSheet(f'color:{tone_color}; {_LBL_RESET}')
            cell.setStyleSheet(
                f'background:{theme.SURFACE_RAISED}; border:1px solid {border};'
                f'border-radius:{theme.RADIUS["md"]}px;'
            )

        # Tyre stint label
        stint_laps = int(getattr(app, '_tyre_stint_laps', 0) or 0)
        header_lbl = self._tyre_card.headerLabel()
        if header_lbl is not None:
            stint_word = 'lap' if stint_laps == 1 else 'laps'
            header_lbl.setText(f'TYRES · {stint_laps} {stint_word} on set')

        # Tyre degradation (from engine)
        if st_state is not None:
            slope = st_state.deg_slope_s_per_lap
            if slope is None:
                self._tyre_deg_lbl.setText('Deg —  ·  fit needs ≥3 laps')
                self._tyre_deg_lbl.setStyleSheet(
                    f'color:{theme.TEXT_MUTED}; {_LBL_RESET}'
                )
            elif slope > 0:
                life = max(0, int(1.5 / slope) - stint_laps)
                deg_color = theme.GOOD if slope < 0.05 else (
                    theme.WARN if slope < 0.15 else theme.BAD
                )
                self._tyre_deg_lbl.setText(
                    f'Deg {slope:+.3f} s/lap  ·  life ~{life} laps')
                self._tyre_deg_lbl.setStyleSheet(
                    f'color:{deg_color}; {_LBL_RESET}'
                )
            else:
                self._tyre_deg_lbl.setText(f'Deg {slope:+.3f} s/lap  ·  stable')
                self._tyre_deg_lbl.setStyleSheet(
                    f'color:{theme.GOOD}; {_LBL_RESET}'
                )

        # ── Fuel ─────────────────────────────────────────────────────────
        fuel_l = float(d.get('fuel', 0.0) or 0.0)
        self._fuel_value.setText(f'{fuel_l:.1f}')

        # Fuel sub-line: laps left / pace
        if st_state is not None and st_state.fuel_laps_left is not None:
            self._fuel_sub.setText(f'{st_state.fuel_laps_left:.1f} laps left')
        else:
            self._fuel_sub.setText('—')

        # ── Pit window ────────────────────────────────────────────────────
        if st_state is not None:
            open_lap = st_state.pit_window_open_lap
            close_lap = st_state.pit_window_close_lap
            current = st_state.current_lap_count or 0
            if open_lap is not None and close_lap is not None:
                if close_lap >= open_lap:
                    self._pit_window_lbl.setText(f'L {open_lap}–{close_lap}')
                else:
                    self._pit_window_lbl.setText(f'L {open_lap}+')
                if open_lap <= current <= close_lap:
                    self._pit_sub.setText(f'WINDOW OPEN · now L{current}')
                    self._pit_sub.setStyleSheet(
                        f'color:{theme.WARN}; {_LBL_RESET}'
                    )
                elif current < open_lap:
                    self._pit_sub.setText(f'opens in {open_lap - current} lap(s) · now L{current}')
                    self._pit_sub.setStyleSheet(
                        f'color:{theme.TEXT_MUTED}; {_LBL_RESET}'
                    )
                else:
                    self._pit_sub.setText(f'PAST WINDOW · pit ASAP · now L{current}')
                    self._pit_sub.setStyleSheet(
                        f'color:{theme.BAD}; {_LBL_RESET}'
                    )
            elif open_lap is not None:
                self._pit_window_lbl.setText(f'L {open_lap}+')
                self._pit_sub.setText(f'now L{current}')
                self._pit_sub.setStyleSheet(
                    f'color:{theme.TEXT_MUTED}; {_LBL_RESET}'
                )
            else:
                self._pit_window_lbl.setText('—')
                self._pit_sub.setText('Complete a lap to estimate.')
                self._pit_sub.setStyleSheet(
                    f'color:{theme.TEXT_MUTED}; {_LBL_RESET}'
                )
