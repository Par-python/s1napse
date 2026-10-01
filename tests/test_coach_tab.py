
import pytest
from PyQt6.QtWidgets import QApplication

from s1napse.coaching.models import Corner, CornerPerformance, LapReport
from s1napse.widgets.tabs.coach import CoachTab


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def _perf(cid: int, grade: str, delta: float, issue: str = 'braked_early') -> CornerPerformance:
    c = Corner(corner_id=cid, direction='RIGHT', entry_distance=100.0 * cid,
               turn_in_distance=100.0 * cid + 10, apex_distance=100.0 * cid + 30,
               exit_distance=100.0 * cid + 60, braking_start_distance=100.0 * cid - 40)
    return CornerPerformance(corner=c, lap_number=3, entry_speed=180, min_speed=90,
                             exit_speed=150, braking_distance=70, time_in_corner=2.1,
                             delta_vs_best=delta, throttle_application_distance=12,
                             grade=grade, primary_issue=issue,
                             tip='Brake a touch later and carry more speed to the apex.')


def _report(perfs) -> LapReport:
    return LapReport(lap_number=3, lap_time_s=107.9, delta_vs_best_lap=0.41,
                     corner_performances=perfs,
                     quick_win_corner_id=1,
                     quick_win_message='Your biggest opportunity this lap is Turn 1 (right) — '
                                       'braking 18m too early. Fix this one corner for ~0.4s.')


def test_empty_state_before_first_lap(app):
    t = CoachTab()
    assert t.isEmptyState()
    assert t.cornerCount() == 0


def test_report_shows_quick_win_and_corners(app):
    t = CoachTab()
    t.set_report(_report([_perf(1, 'red', 0.41), _perf(2, 'green', -0.05, 'great')]))
    assert not t.isEmptyState()
    assert 'Turn 1' in t.quickWinText()
    assert t.cornerCount() == 2


def test_report_without_corners_shows_message(app):
    t = CoachTab()
    t.set_report(_report([]))
    assert not t.isEmptyState()
    assert t.cornerCount() == 0
    assert 'No corners detected' in t.cornerListMessage()


def test_none_report_keeps_empty_state(app):
    t = CoachTab()
    t.set_report(None)
    assert t.isEmptyState()


def test_history_populates_lap_picker(app):
    t = CoachTab()
    r1 = _report([_perf(1, 'red', 0.4)]); r1.lap_number = 2
    r2 = _report([_perf(1, 'green', 0.0, 'great')]); r2.lap_number = 3
    t.set_report(r2, history=[r1, r2])
    assert t.lapPickerCount() == 2


def test_lap_bars_show_times_and_highlight_best(app):
    from matplotlib.colors import to_rgba
    from s1napse import theme
    t = CoachTab()
    r1 = _report([]); r1.lap_number = 2; r1.lap_time_s = 108.5
    r2 = _report([])
    t.set_report(r2, history=[r1, r2])
    bars = t._lap_ax.patches
    assert [b.get_height() for b in bars] == [108.5, 107.9]
    assert bars[1].get_facecolor() == to_rgba(theme.GOOD)
    t._picker.setCurrentIndex(0)
    assert 'Lap 2' in t._lap_line.text()


def test_quick_win_gain_is_green_and_text_preserved(app):
    from PyQt6.QtGui import QTextDocument
    from s1napse import theme
    t = CoachTab()
    report = _report([])
    t.set_report(report)
    assert theme.GOOD_FG in t._quick_lbl.text()
    doc = QTextDocument(); doc.setHtml(t._quick_lbl.text())
    assert doc.toPlainText() == report.quick_win_message
