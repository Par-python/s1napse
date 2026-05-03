"""Sector times panel, sector scrubber, and lap history panel."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QScrollArea, QSlider, QSizePolicy,
)
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

from ..constants import (
    C_SPEED, C_THROTTLE, C_BRAKE, C_RPM, C_STEER, C_DELTA,
    C_PURPLE, C_PURPLE_BG, C_GREEN_BG, C_REF,
    mono, sans,
)
from ..theme import (
    SURFACE as BG1, SURFACE_RAISED as BG2, SURFACE_HOVER as BG3,
    BORDER_SUBTLE as BORDER, BORDER_STRONG as BORDER2,
    TEXT_SECONDARY as TXT, TEXT_MUTED as TXT2, TEXT_PRIMARY as WHITE,
)
from ..utils import h_line


class SectorTimesPanel(QWidget):
    SECTORS = ['S1', 'S2', 'S3']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumWidth(230)
        self.setStyleSheet(f'background: {BG2};')
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        laps_header = QLabel('LAP TIMES')
        laps_header.setFont(sans(8))
        laps_header.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        layout.addWidget(laps_header)

        self.lap_current_label = QLabel('0:00.000')
        self.lap_current_label.setFont(mono(15, bold=True))
        self.lap_current_label.setStyleSheet(f'color: {TXT};')

        self.lap_ref_label = QLabel('\u2014')
        self.lap_ref_label.setFont(mono(10))
        self.lap_ref_label.setStyleSheet(f'color: {TXT2};')

        self.lap_gap_label = QLabel('')
        self.lap_gap_label.setFont(mono(10, bold=True))
        self.lap_gap_label.setStyleSheet(f'color: {TXT2};')

        lap_card = QFrame()
        lap_card.setStyleSheet(f'background: {BG3}; border: 1px solid {BORDER};'
                               f' border-radius: 4px; padding: 6px;')
        lc = QVBoxLayout(lap_card)
        lc.setSpacing(3)
        lc.addWidget(self.lap_current_label)
        lc.addWidget(self.lap_ref_label)
        lc.addWidget(self.lap_gap_label)
        layout.addWidget(lap_card)

        layout.addWidget(h_line())

        sectors_header = QLabel('SECTOR GAPS')
        sectors_header.setFont(sans(8))
        sectors_header.setStyleSheet(f'color: {TXT2}; letter-spacing: 1px;')
        layout.addWidget(sectors_header)

        grid = QGridLayout()
        grid.setSpacing(4)
        for col, txt in enumerate(['', 'REF', 'CUR', '\u0394']):
            lbl = QLabel(txt)
            lbl.setFont(sans(8))
            lbl.setStyleSheet(f'color: {TXT2}; letter-spacing: 0.5px;')
            grid.addWidget(lbl, 0, col)

        self._sec_ref_labels:  dict[str, QLabel] = {}
        self._sec_cur_labels:  dict[str, QLabel] = {}
        self._sec_gap_labels:  dict[str, QLabel] = {}

        for row, s in enumerate(self.SECTORS, 1):
            s_lbl = QLabel(s)
            s_lbl.setFont(mono(9, bold=True))
            s_lbl.setStyleSheet(f'color: {TXT2};')
            grid.addWidget(s_lbl, row, 0)

            ref_lbl = QLabel('\u2014')
            ref_lbl.setFont(mono(9))
            ref_lbl.setStyleSheet(f'color: {TXT2};')
            self._sec_ref_labels[s] = ref_lbl
            grid.addWidget(ref_lbl, row, 1)

            cur_lbl = QLabel('\u2014')
            cur_lbl.setFont(mono(9))
            cur_lbl.setStyleSheet(f'color: {TXT};')
            self._sec_cur_labels[s] = cur_lbl
            grid.addWidget(cur_lbl, row, 2)

            gap_lbl = QLabel('')
            gap_lbl.setFont(mono(9, bold=True))
            self._sec_gap_labels[s] = gap_lbl
            grid.addWidget(gap_lbl, row, 3)

        for d in (self._sec_ref_labels, self._sec_cur_labels):
            for lbl in d.values():
                lbl.setMaximumWidth(52)
                lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        for lbl in self._sec_gap_labels.values():
            lbl.setMaximumWidth(64)
            lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.lap_current_label.setMaximumWidth(210)

        gaps_frame = QFrame()
        gaps_frame.setStyleSheet(f'background: {BG3}; border: 1px solid {BORDER};'
                                 f' border-radius: 4px;')
        gaps_frame.setLayout(grid)
        layout.addWidget(gaps_frame)
        layout.addStretch()

    @staticmethod
    def _fmt(t_s: float) -> str:
        m = int(t_s // 60)
        s = t_s % 60
        return f'{m}:{s:06.3f}'

    def update_current_time(self, current_time_s: float):
        self.lap_current_label.setText(self._fmt(current_time_s))
        self.lap_ref_label.setText('\u2014')
        self.lap_gap_label.setText('')

    def update_laps(self, current_time_s: float, ref_time_s: float,
                    ref_sectors: list, cur_sectors: list):
        self.lap_current_label.setText(self._fmt(current_time_s))
        self.lap_ref_label.setText(f'Ref  {self._fmt(ref_time_s)}')
        self.lap_ref_label.setStyleSheet(f'color: {C_REF};')

        if cur_sectors and ref_sectors:
            cur_total = sum(s for s in cur_sectors if s is not None)
            ref_total = sum(s for s in ref_sectors[:len(cur_sectors)]
                            if s is not None)
            if cur_total > 0 and ref_total > 0:
                gap = cur_total - ref_total
                sign = '+' if gap >= 0 else ''
                col  = C_REF if gap > 0 else C_THROTTLE
                self.lap_gap_label.setText(f'{sign}{gap:.3f}s')
                self.lap_gap_label.setStyleSheet(f'color: {col};')
            else:
                self.lap_gap_label.setText('')
        else:
            self.lap_gap_label.setText('')

        for s, ref_s, cur_s in zip(self.SECTORS, ref_sectors, cur_sectors):
            if ref_s is not None:
                self._sec_ref_labels[s].setText(f'{ref_s:.3f}')
                self._sec_ref_labels[s].setStyleSheet(f'color: {TXT2};')
            else:
                self._sec_ref_labels[s].setText('\u2014')

            if cur_s is not None:
                self._sec_cur_labels[s].setText(f'{cur_s:.3f}')
                self._sec_cur_labels[s].setStyleSheet(f'color: {TXT};')
                if ref_s is not None:
                    delta = cur_s - ref_s
                    sign  = '+' if delta >= 0 else ''
                    col   = C_REF if delta > 0 else C_THROTTLE
                    self._sec_gap_labels[s].setText(f'{sign}{delta:.3f}s')
                    self._sec_gap_labels[s].setStyleSheet(f'color: {col};')
                else:
                    self._sec_gap_labels[s].setText('')
            else:
                self._sec_cur_labels[s].setText('\u2014')
                self._sec_gap_labels[s].setText('')


class SectorScrubWidget(QWidget):
    """Timeline scrubber with sector boundary markers painted above the slider."""

    valueChanged = pyqtSignal(int)

    _SECTOR_COLORS = [C_DELTA, C_STEER, C_RPM]
    _MARK_H = 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total_ms: int = 1
        self._sectors: list = []
        self.setFixedHeight(self._MARK_H + 30)
        self.setStyleSheet(f'background: {BG1}; border-radius: 4px;')

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, 1000)
        self.slider.setSingleStep(100)
        self.slider.setPageStep(1000)
        self.slider.setStyleSheet(
            f'QSlider::groove:horizontal {{'
            f'  height: 6px; background: {BG3}; border-radius: 3px; margin: 0 7px; }}'
            f'QSlider::handle:horizontal {{'
            f'  width: 14px; height: 14px; background: {WHITE}; border-radius: 7px;'
            f'  margin: -4px 0; }}'
            f'QSlider::sub-page:horizontal {{'
            f'  background: {C_SPEED}; border-radius: 3px; margin: 0 7px; }}'
        )
        self.slider.valueChanged.connect(self.valueChanged)
        self._reposition_slider()

    def resizeEvent(self, event):
        self._reposition_slider()
        self.update()

    def _reposition_slider(self):
        self.slider.setGeometry(0, self._MARK_H, self.width(), self.height() - self._MARK_H)

    def set_duration(self, total_ms: int, sectors: list):
        self._total_ms = max(1, total_ms)
        self._sectors = sectors
        self.slider.blockSignals(True)
        self.slider.setRange(0, self._total_ms)
        self.slider.blockSignals(False)
        self.update()

    def set_value(self, ms: int):
        self.slider.blockSignals(True)
        self.slider.setValue(ms)
        self.slider.blockSignals(False)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._sectors or not self._total_ms:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        font = QFont('Consolas', 7)
        font.setBold(True)
        painter.setFont(font)
        for i, (label, ms) in enumerate(self._sectors):
            if not ms:
                continue
            x = int(ms / self._total_ms * w)
            color = self._SECTOR_COLORS[i % len(self._SECTOR_COLORS)]
            qc = QColor(color)
            painter.setPen(QPen(qc, 1))
            painter.drawLine(x, self._MARK_H - 5, x, self._MARK_H + 3)
            painter.setPen(qc)
            text_rect = QRectF(x - 16, 2, 32, self._MARK_H - 7)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.end()


class LapHistoryPanel(QWidget):
    """Session lap list with best-lap (purple) and best-sector (green) highlights."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f'background: {BG2}; border-radius: 4px;')

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 6)
        outer.setSpacing(6)

        hdr_row = QHBoxLayout()
        title = QLabel('SESSION LAPS')
        title.setFont(sans(8))
        title.setStyleSheet(f'color: {TXT2}; letter-spacing: 1.5px;')
        hdr_row.addWidget(title)
        hdr_row.addStretch()

        legend_best = QLabel('\u25a0 BEST LAP')
        legend_best.setFont(sans(7))
        legend_best.setStyleSheet(f'color: {C_PURPLE};')
        legend_sec = QLabel('\u25a0 BEST SECTOR')
        legend_sec.setFont(sans(7))
        legend_sec.setStyleSheet(f'color: {C_THROTTLE};')
        hdr_row.addWidget(legend_best)
        hdr_row.addSpacing(10)
        hdr_row.addWidget(legend_sec)
        outer.addLayout(hdr_row)
        outer.addWidget(h_line())

        col_hdr = QWidget()
        col_hdr.setStyleSheet('background: transparent;')
        col_hdr_layout = QHBoxLayout(col_hdr)
        col_hdr_layout.setContentsMargins(8, 2, 8, 2)
        col_hdr_layout.setSpacing(0)
        for txt, stretch in [('LAP', 0), ('TIME', 2), ('S1', 1), ('S2', 1), ('S3', 1)]:
            l = QLabel(txt)
            l.setFont(sans(7))
            l.setStyleSheet(f'color: {TXT2}; letter-spacing: 0.8px;')
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            col_hdr_layout.addWidget(l, stretch)
        outer.addWidget(col_hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')
        self._rows_widget = QWidget()
        self._rows_widget.setStyleSheet('background: transparent;')
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(2)
        self._rows_layout.addStretch()
        scroll.setWidget(self._rows_widget)
        outer.addWidget(scroll, 1)

        self._empty_label = QLabel('No completed laps yet')
        self._empty_label.setFont(sans(9))
        self._empty_label.setStyleSheet(f'color: {TXT2};')
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._empty_label)

    @staticmethod
    def _fmt_time(t_s: float) -> str:
        m = int(t_s // 60)
        s = t_s % 60
        return f'{m}:{s:06.3f}'

    def refresh(self, session_laps: list):
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not session_laps:
            self._empty_label.setVisible(True)
            return
        self._empty_label.setVisible(False)

        valid_times = [lap.get('total_time_s', 0) for lap in session_laps
                       if lap.get('total_time_s', 0) > 0]
        best_time = min(valid_times) if valid_times else None

        best_sectors = []
        for si in range(3):
            col_times = [lap['sectors'][si] for lap in session_laps
                         if lap.get('sectors') and lap['sectors'][si] is not None]
            best_sectors.append(min(col_times) if col_times else None)

        for lap in reversed(session_laps):
            row = self._make_row(lap, best_time, best_sectors)
            self._rows_layout.insertWidget(0, row)

    def _make_row(self, lap: dict, best_time: float | None,
                  best_sectors: list) -> QWidget:
        lap_time   = lap.get('total_time_s', 0)
        lap_valid  = lap.get('lap_valid', True)
        is_best    = bool(lap_valid and best_time is not None and lap_time > 0
                         and abs(lap_time - best_time) < 0.001)
        sectors    = lap.get('sectors', [None, None, None]) or [None, None, None]

        row = QFrame()
        if not lap_valid:
            row.setStyleSheet(
                f'background: rgba(180,30,30,0.12); border: 1px solid {C_BRAKE};'
                f' border-radius: 3px;')
        elif is_best:
            row.setStyleSheet(
                f'background: {C_PURPLE_BG}; border: 1px solid {C_PURPLE};'
                f' border-radius: 3px;')
        else:
            row.setStyleSheet(
                f'background: {BG3}; border: 1px solid {BORDER};'
                f' border-radius: 3px;')

        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(0)

        def _cell(text: str, color: str = TXT, bold: bool = False,
                  bg: str = '', stretch: int = 1) -> QLabel:
            lbl = QLabel(text)
            lbl.setFont(mono(9, bold=bold))
            style = f'color: {color}; background: transparent;'
            if bg:
                style = (f'color: {color}; background: {bg};'
                         f' border-radius: 2px; padding: 1px 4px;')
            lbl.setStyleSheet(style)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl, stretch)
            return lbl

        lap_num_col = C_PURPLE if is_best else TXT2
        _cell(str(lap.get('lap_number', '?')), color=lap_num_col, stretch=0)
        layout.addSpacing(8)

        if lap_time > 0:
            time_col  = C_PURPLE if is_best else (C_BRAKE if not lap_valid else TXT)
            time_bold = is_best
            _cell(self._fmt_time(lap_time), color=time_col, bold=time_bold, stretch=2)
        else:
            _cell('\u2014', color=TXT2, stretch=2)

        for si, sec_t in enumerate(sectors):
            if sec_t is None:
                _cell('\u2014', color=TXT2, stretch=1)
                continue

            is_best_sec = bool(best_sectors[si] is not None
                               and abs(sec_t - best_sectors[si]) < 0.001)

            if is_best_sec and not lap_valid:
                _cell(f'{sec_t:.3f}', color=C_PURPLE, bold=True, stretch=1)
            elif not lap_valid:
                _cell(f'{sec_t:.3f}', color=C_BRAKE, stretch=1)
            elif is_best and is_best_sec:
                _cell(f'{sec_t:.3f}', color=C_PURPLE, bold=True, stretch=1)
            elif is_best_sec:
                _cell(f'{sec_t:.3f}', color=C_THROTTLE, bold=True,
                      bg=C_GREEN_BG, stretch=1)
            elif is_best:
                _cell(f'{sec_t:.3f}', color=C_PURPLE, stretch=1)
            else:
                _cell(f'{sec_t:.3f}', color=TXT, stretch=1)

        return row
