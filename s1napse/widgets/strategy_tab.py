"""Strategy tab — six live cards driven by StrategyEngine.

See docs/superpowers/specs/2026-04-25-strategy-tab-v1-design.md.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
)

from ..constants import BG, BG2, BG3, BORDER, BORDER2, TXT, TXT2, mono, sans


def _card() -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f'background: {BG2}; border: 1px solid {BORDER}; border-radius: 6px;')
    return f


def _chip_lbl(text: str, font_size: int = 8, bold: bool = True,
              color: str = TXT2, letter_spacing: str = '1px') -> QLabel:
    l = QLabel(text)
    l.setFont(sans(font_size, bold=bold))
    l.setStyleSheet(f'color: {color}; letter-spacing: {letter_spacing};')
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
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')

        inner = QWidget()
        inner.setStyleSheet(f'background: {BG};')
        body = QVBoxLayout(inner)
        body.setContentsMargins(14, 14, 14, 14)
        body.setSpacing(10)

        body.addWidget(self._build_degradation_card())
        body.addWidget(self._build_pit_window_card())
        body.addWidget(self._build_fuel_save_cost_card())
        body.addWidget(self._build_rival_watch_card())
        body.addWidget(self._build_temp_watch_card())
        body.addWidget(self._build_pit_summary_card())
        body.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    # --- Card builders (placeholders for now; filled in Tasks 11-13) ---

    def _build_degradation_card(self) -> QFrame:
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('TYRE DEGRADATION'))
        self._deg_status = QLabel('Need 3 laps to project.')
        self._deg_status.setFont(mono(10))
        self._deg_status.setStyleSheet(f'color: {TXT2};')
        v.addWidget(self._deg_status)
        return c

    def _build_pit_window_card(self) -> QFrame:
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('PIT WINDOW'))
        self._pw_status = QLabel('Complete a lap to estimate.')
        self._pw_status.setFont(mono(10))
        self._pw_status.setStyleSheet(f'color: {TXT2};')
        v.addWidget(self._pw_status)
        return c

    def _build_fuel_save_cost_card(self) -> QFrame:
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('FUEL-SAVE COST'))
        self._fsc_status = QLabel('—')
        self._fsc_status.setFont(mono(10))
        self._fsc_status.setStyleSheet(f'color: {TXT2};')
        v.addWidget(self._fsc_status)
        return c

    def _build_rival_watch_card(self) -> QFrame:
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('RIVAL WATCH (inferred)'))
        self._rw_ahead = QLabel('Ahead: stable')
        self._rw_behind = QLabel('Behind: stable')
        for lbl in (self._rw_ahead, self._rw_behind):
            lbl.setFont(mono(10))
            lbl.setStyleSheet(f'color: {TXT};')
            v.addWidget(lbl)
        sub = QLabel('Inferred from gap delta. May fire on rival crash/spin.')
        sub.setFont(sans(8))
        sub.setStyleSheet(f'color: {TXT2};')
        sub.setWordWrap(True)
        v.addWidget(sub)
        return c

    def _build_temp_watch_card(self) -> QFrame:
        c = _card()
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('WEATHER / TRACK TEMP'))
        self._tw_status = QLabel('—')
        self._tw_status.setFont(mono(10))
        self._tw_status.setStyleSheet(f'color: {TXT2};')
        v.addWidget(self._tw_status)
        return c

    def _build_pit_summary_card(self) -> QFrame:
        c = _card()
        vbox = QVBoxLayout(c)
        vbox.setContentsMargins(18, 12, 18, 12)
        vbox.setSpacing(8)

        hdr_row = QHBoxLayout()
        hdr_row.addWidget(_chip_lbl('PIT STRATEGY'))
        hdr_row.addStretch()
        self._pit_no_data_lbl = _chip_lbl('Complete a lap to calculate',
                                           color=TXT2, bold=False)
        hdr_row.addWidget(self._pit_no_data_lbl)
        vbox.addLayout(hdr_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(0)

        def _pit_stat(title: str, attr: str) -> QVBoxLayout:
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(_chip_lbl(title, font_size=7))
            v = QLabel('—')
            v.setFont(mono(11, bold=True))
            v.setStyleSheet(f'color: {TXT};')
            col.addWidget(v)
            setattr(self, attr, v)
            return col

        stats_row.addLayout(_pit_stat('FUEL LAPS LEFT', '_pit_fuel_laps_lbl'))
        stats_row.addSpacing(28)
        stats_row.addLayout(_pit_stat('TYRE STINT', '_pit_tyre_stint_lbl'))
        stats_row.addSpacing(28)
        stats_row.addLayout(_pit_stat('TYRE CONDITION', '_pit_tyre_cond_lbl'))
        stats_row.addStretch()
        vbox.addLayout(stats_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f'color: {BORDER2}; background: {BORDER2};')
        sep.setFixedHeight(1)
        vbox.addWidget(sep)

        self._pit_rec_lbl = QLabel('—')
        self._pit_rec_lbl.setFont(sans(11, bold=True))
        self._pit_rec_lbl.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        self._pit_rec_lbl.setWordWrap(True)
        vbox.addWidget(self._pit_rec_lbl)

        return c

    # --- Public API ---

    def refresh(self, state) -> None:
        """Re-render all six cards from a StrategyState. Cheap if invisible."""
        if not self.isVisible():
            return

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
                lbl.setStyleSheet('color: #f5a623;')
            else:
                lbl.setStyleSheet(f'color: {TXT};')

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
