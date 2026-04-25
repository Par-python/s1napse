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
        v = QVBoxLayout(c)
        v.setContentsMargins(18, 12, 18, 12)
        v.addWidget(_chip_lbl('PIT STRATEGY (relocated)'))
        self._ps_status = QLabel('Pit-strategy summary will move here in Task 14.')
        self._ps_status.setFont(mono(10))
        self._ps_status.setStyleSheet(f'color: {TXT2};')
        v.addWidget(self._ps_status)
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
