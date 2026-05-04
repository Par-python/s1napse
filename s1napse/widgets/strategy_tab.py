"""Strategy tab — six live cards driven by StrategyEngine.

See docs/superpowers/specs/2026-04-25-strategy-tab-v1-design.md.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)

from .. import theme
from .primitives import Card, Stat


def _chip_lbl(text: str, font_size: int = 8, bold: bool = True,
              color: str | None = None, letter_spacing: str = '1px') -> QLabel:
    lbl_color = color if color is not None else theme.TEXT_MUTED
    l = QLabel(text)
    l.setFont(theme.ui_font(font_size, bold=bold))
    l.setStyleSheet(f'color: {lbl_color}; letter-spacing: {letter_spacing};')
    return l


class StrategyTab(QWidget):
    """Strategy tab widget. Re-renders cards from a StrategyState snapshot.

    The tab is render-driven: call :meth:`refresh` from the host's render
    timer with the current StrategyState. The widget guards against
    redrawing when invisible (see :meth:`isVisible`).
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        outer.addWidget(self._build_headline_strip())

        body = QHBoxLayout()
        body.setSpacing(12)
        outer.addLayout(body, 1)

        # Column 1 — "Now" (live race state)
        col_now = QVBoxLayout()
        col_now.setSpacing(12)
        col_now.addWidget(self._build_pit_window_card())
        col_now.addWidget(self._build_fuel_save_cost_card())
        col_now.addWidget(self._build_rival_watch_card())
        col_now.addWidget(self._build_temp_watch_card())
        col_now.addStretch(1)
        body.addLayout(col_now, 1)

        # Column 2 — "Plan" (calculators + projections)
        col_plan = QVBoxLayout()
        col_plan.setSpacing(12)
        col_plan.addWidget(self._build_degradation_card())
        col_plan.addWidget(self._build_pit_summary_card())
        col_plan.addWidget(self._build_fuel_save_calculator_card())
        col_plan.addWidget(self._build_undercut_overcut_card())
        col_plan.addStretch(1)
        body.addLayout(col_plan, 1)

    def _build_headline_strip(self) -> QFrame:
        """Top strip — STRATEGY label + live headline message."""
        f = QFrame()
        f.setStyleSheet(
            f'background: {theme.SURFACE}; border: 1px solid {theme.BORDER_SUBTLE}; '
            f'border-radius: {theme.RADIUS["lg"]}px;'
        )
        row = QHBoxLayout(f)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(20)

        title = QLabel('STRATEGY')
        title.setFont(theme.ui_font(20, bold=True))
        title.setStyleSheet(f'color: {theme.TEXT_PRIMARY}; background: transparent; border: none;')
        row.addWidget(title, 0)

        div = QFrame()
        div.setFixedWidth(1)
        div.setStyleSheet(f'background: {theme.BORDER_SUBTLE}; border: none;')
        row.addWidget(div)

        banner = QVBoxLayout()
        banner.setSpacing(2)
        self._headline_label = QLabel('► COLUMNS')
        self._headline_label.setFont(theme.label_font())
        self._headline_label.setStyleSheet(
            f'color: {theme.ACCENT_FG}; background: transparent; border: none; letter-spacing: 0.7px;'
        )
        banner.addWidget(self._headline_label)
        self._headline_msg = QLabel('Live → on the left  ·  Plan → on the right')
        self._headline_msg.setFont(theme.ui_font(13, bold=True))
        self._headline_msg.setStyleSheet(
            f'color: {theme.TEXT_PRIMARY}; background: transparent; border: none;'
        )
        self._headline_msg.setWordWrap(True)
        banner.addWidget(self._headline_msg)
        row.addLayout(banner, 1)
        return f

    # --- Card builders (placeholders for now; filled in Tasks 11-13) ---

    def _build_degradation_card(self) -> Card:
        card = Card(label='TYRE DEGRADATION', dense=True)
        self._deg_stat = Stat(
            value='—',
            sub='Need 3 laps to project.',
        )
        # Keep _deg_status as a hidden label so refresh() setText calls still work
        self._deg_status = self._deg_stat.valueLabel()
        card.body().addWidget(self._deg_stat)
        return card

    def _build_pit_window_card(self) -> Card:
        card = Card(label='PIT WINDOW', dense=True)
        self._pw_stat = Stat(
            value='—',
            sub='Complete a lap to estimate.',
        )
        # Keep _pw_status pointing to the internal value label for refresh() setText calls
        self._pw_status = self._pw_stat.valueLabel()
        card.body().addWidget(self._pw_stat)
        return card

    def _build_fuel_save_cost_card(self) -> Card:
        card = Card(label='FUEL-SAVE COST', dense=True)
        self._fsc_status = QLabel('—')
        self._fsc_status.setFont(theme.mono_font(13))
        self._fsc_status.setStyleSheet(f'color: {theme.TEXT_MUTED};')
        self._fsc_status.setWordWrap(True)
        card.body().addWidget(self._fsc_status)
        return card

    def _build_rival_watch_card(self) -> Card:
        card = Card(label='RIVAL WATCH (inferred)', dense=True)
        self._rw_ahead = QLabel('Ahead: stable')
        self._rw_behind = QLabel('Behind: stable')
        for lbl in (self._rw_ahead, self._rw_behind):
            lbl.setFont(theme.mono_font(13))
            lbl.setStyleSheet(f'color: {theme.TEXT_SECONDARY};')
            card.body().addWidget(lbl)
        sub = QLabel('Inferred from gap delta. May fire on rival crash/spin.')
        sub.setFont(theme.ui_font(8))
        sub.setStyleSheet(f'color: {theme.TEXT_MUTED};')
        sub.setWordWrap(True)
        card.body().addWidget(sub)
        return card

    def _build_temp_watch_card(self) -> Card:
        card = Card(label='WEATHER / TRACK TEMP', dense=True)
        self._tw_status = QLabel('—')
        self._tw_status.setFont(theme.mono_font(13))
        self._tw_status.setStyleSheet(f'color: {theme.TEXT_PRIMARY};')
        self._tw_status.setWordWrap(True)
        card.body().addWidget(self._tw_status)
        return card

    def _build_pit_summary_card(self) -> Card:
        card = Card(label='PIT STRATEGY', dense=True)

        # "no data" sub-label in header row — inject via a horizontal helper
        no_data_row = QHBoxLayout()
        no_data_row.setContentsMargins(0, 0, 0, 0)
        self._pit_no_data_lbl = _chip_lbl('Complete a lap to calculate',
                                           color=theme.TEXT_MUTED, bold=False)
        no_data_row.addStretch()
        no_data_row.addWidget(self._pit_no_data_lbl)
        card.body().addLayout(no_data_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(0)

        def _pit_stat(title: str, attr: str) -> QVBoxLayout:
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(_chip_lbl(title, font_size=7))
            v = QLabel('—')
            v.setFont(theme.mono_font(theme.FONT_NUMERIC_LG, bold=True))
            v.setStyleSheet(f'color: {theme.TEXT_PRIMARY};')
            col.addWidget(v)
            setattr(self, attr, v)
            return col

        stats_row.addLayout(_pit_stat('FUEL LAPS LEFT', '_pit_fuel_laps_lbl'))
        stats_row.addSpacing(28)
        stats_row.addLayout(_pit_stat('TYRE STINT', '_pit_tyre_stint_lbl'))
        stats_row.addSpacing(28)
        stats_row.addLayout(_pit_stat('TYRE CONDITION', '_pit_tyre_cond_lbl'))
        stats_row.addStretch()
        card.body().addLayout(stats_row)

        self._pit_rec_lbl = QLabel('—')
        self._pit_rec_lbl.setFont(theme.ui_font(11, bold=True))
        self._pit_rec_lbl.setStyleSheet(
            f'color: {theme.TEXT_MUTED}; letter-spacing: 1px;')
        self._pit_rec_lbl.setWordWrap(True)
        card.body().addWidget(self._pit_rec_lbl)

        return card

    def _build_fuel_save_calculator_card(self) -> Card:
        from PyQt6.QtWidgets import QSpinBox
        card = Card(label='FUEL SAVE CALCULATOR', dense=True)

        row = QHBoxLayout()
        row.addWidget(_chip_lbl('LAPS TO GO', font_size=8, bold=False,
                                color=theme.TEXT_SECONDARY))
        self._fs_laps_spin = QSpinBox()
        self._fs_laps_spin.setRange(1, 99)
        self._fs_laps_spin.setValue(10)
        row.addWidget(self._fs_laps_spin)
        row.addStretch()
        card.body().addLayout(row)

        self._fs_result_lbl = QLabel('—')
        self._fs_result_lbl.setFont(theme.mono_font(13, bold=True))
        self._fs_result_lbl.setStyleSheet(f'color: {theme.TEXT_PRIMARY};')
        self._fs_result_lbl.setWordWrap(True)
        card.body().addWidget(self._fs_result_lbl)
        return card

    def _build_undercut_overcut_card(self) -> Card:
        from PyQt6.QtWidgets import QDoubleSpinBox
        card = Card(label='UNDERCUT / OVERCUT', dense=True)

        inputs_row = QHBoxLayout()
        inputs_row.setSpacing(20)

        def _spin_col(label: str, attr: str, default: float, min_val: float,
                      max_val: float, step: float, decimals: int) -> QVBoxLayout:
            col = QVBoxLayout()
            col.addWidget(_chip_lbl(label, font_size=7))
            spin = QDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(default)
            spin.setSingleStep(step)
            spin.setDecimals(decimals)
            spin.setFixedWidth(90)
            col.addWidget(spin)
            setattr(self, attr, spin)
            return col

        inputs_row.addLayout(
            _spin_col('PIT LOSS (s)', '_uco_pit_loss_spin', 22.0, 10.0, 60.0, 0.5, 1))
        inputs_row.addLayout(
            _spin_col('PACE DELTA (s/lap)', '_uco_pace_delta_spin', 0.8, 0.0, 5.0, 0.1, 1))
        inputs_row.addStretch()
        card.body().addLayout(inputs_row)

        self._uco_undercut_lbl = QLabel('UNDERCUT: —')
        self._uco_undercut_lbl.setFont(theme.mono_font(13, bold=True))
        self._uco_undercut_lbl.setStyleSheet(f'color: {theme.TEXT_PRIMARY};')
        self._uco_overcut_lbl = QLabel('OVERCUT: —')
        self._uco_overcut_lbl.setFont(theme.mono_font(13, bold=True))
        self._uco_overcut_lbl.setStyleSheet(f'color: {theme.TEXT_PRIMARY};')
        card.body().addWidget(self._uco_undercut_lbl)
        card.body().addWidget(self._uco_overcut_lbl)
        return card

    # --- Public API ---

    def has_alert(self) -> bool:
        return False

    def refresh(self, state) -> None:
        """Re-render all cards from a StrategyState. Cheap if invisible."""
        if not self.isVisible():
            return

        # Update headline strip from state
        headline = state.headline()
        if headline is not None:
            # Headline.text carries the full callout string; severity drives colour.
            severity = (headline.severity or '').lower()
            if severity == 'red':
                color = theme.BAD
            elif severity == 'amber':
                color = theme.WARN
            elif severity == 'green':
                color = theme.GOOD
            else:
                color = theme.ACCENT_FG
            self._headline_label.setText(f'► {headline.severity.upper()}')
            self._headline_label.setStyleSheet(
                f'color: {color}; background: transparent; border: none; letter-spacing: 0.7px;'
            )
            self._headline_msg.setText(headline.text)
        else:
            self._headline_label.setText('► COLUMNS')
            self._headline_label.setStyleSheet(
                f'color: {theme.ACCENT_FG}; background: transparent; border: none; letter-spacing: 0.7px;'
            )
            self._headline_msg.setText('Live → on the left  ·  Plan → on the right')

        # Card 1 — degradation
        if state.deg_slope_s_per_lap is None:
            self._deg_status.setText('Need 3 laps to project.')
        else:
            r2 = state.deg_r_squared or 0.0
            pips = '●●●' if r2 >= 0.9 else ('●●○' if r2 >= 0.7 else '●○○')
            self._deg_status.setText(
                f'Baseline {state.deg_baseline_s:.3f}s   '
                f'Deg {state.deg_slope_s_per_lap:+.3f}s/lap   '
                f'EOS {state.deg_projected_end_pace_s:.3f}s   '
                f'Fit {pips}'
            )

        # Card 2 — pit window
        if (state.pit_window_open_lap is None
                and state.pit_window_close_lap is None):
            self._pw_status.setText('Complete a lap to estimate.')
        else:
            open_str = (str(state.pit_window_open_lap)
                        if state.pit_window_open_lap is not None else '—')
            close_str = (str(state.pit_window_close_lap)
                         if state.pit_window_close_lap is not None else '—')
            self._pw_status.setText(
                f'Window opens lap {open_str}   closes lap {close_str}   '
                f'(currently lap {state.current_lap_count})'
            )

        # Card 3 — fuel-save cost (estimate per L/lap saved)
        cost = state.fuel_save_cost_s_per_lap_per_l
        self._fsc_status.setText(
            f'Estimated cost: ~{cost:.2f}s/lap per 1 L/lap saved   '
            f'(industry rule of thumb; varies by car/track)'
        )

        # Card 4 — rival watch
        import time as _time
        now = _time.monotonic()

        def _rival_str(prefix: str, gap_ms: int, pitted_at: float | None) -> str:
            gap_s = abs(gap_ms) / 1000.0
            if pitted_at is not None and (now - pitted_at) <= 30.0:
                age = int(now - pitted_at)
                return f'{prefix}: PITTED LIKELY ({age}s ago, gap {gap_s:.1f}s)'
            return f'{prefix}: stable (gap {gap_s:.1f}s)'

        self._rw_ahead.setText(_rival_str(
            'Ahead', state.last_gap_ahead_ms, state.rival_ahead_pitted_at))
        self._rw_behind.setText(_rival_str(
            'Behind', state.last_gap_behind_ms, state.rival_behind_pitted_at))

        # Color the labels amber when pit alert is active
        for lbl, pitted_at in (
            (self._rw_ahead, state.rival_ahead_pitted_at),
            (self._rw_behind, state.rival_behind_pitted_at),
        ):
            if pitted_at is not None and (now - pitted_at) <= 30.0:
                lbl.setStyleSheet(f'color: {theme.WARN};')
            else:
                lbl.setStyleSheet(f'color: {theme.TEXT_SECONDARY};')

        # Card 5 — weather/track-temp watch
        if state.track_temp_c is None:
            self._tw_status.setText('No track-temp data.')
        else:
            air_str = (f' (air {state.air_temp_c:.1f}°C)'
                       if state.air_temp_c is not None else '')
            if state.track_temp_at_stint_start_c is None:
                self._tw_status.setText(
                    f'Track {state.track_temp_c:.1f}°C{air_str}')
            else:
                delta = state.track_temp_c - state.track_temp_at_stint_start_c
                if abs(delta) <= 5.0:
                    note = 'stable'
                elif delta < 0:
                    note = f'cooling {abs(delta):.0f}°C — expect more tyre life'
                else:
                    note = f'heating {delta:.0f}°C — expect more degradation'
                self._tw_status.setText(
                    f'Track {state.track_temp_c:.1f}°C{air_str} · {note}'
                )
