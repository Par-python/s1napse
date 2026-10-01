from s1napse import theme
from s1napse.app import TAB_TITLES


def test_tab_titles_sentence_case_and_coach_third():
    assert TAB_TITLES[0] == 'Dashboard'
    assert TAB_TITLES[2] == 'Coach'
    for t in TAB_TITLES:
        assert t[0].isupper() and not t.isupper()


def test_race_tab_title_still_matches_indicator_lookup():
    assert 'Race' in TAB_TITLES and 'Race'.upper() == 'RACE'


def test_tab_qss_is_segmented():
    qss = theme.build_app_qss().replace(' ', '')
    tab_selected = qss.split('QTabBar::tab:selected{', 1)[1].split('}', 1)[0]
    assert f'background:{theme.SURFACE_HOVER}' in tab_selected
    assert 'border-bottom' not in tab_selected

import re
from pathlib import Path

_SHOUTY = re.compile(r"QLabel\('([A-Z][A-Z0-9 /&%·()-]{2,})'\)")
_ALLOWED = {'RPM', 'LAP 0', 'OBD-II CONNECTED', 'DISCONNECTED'}  # dynamic or acronym-only


def test_no_all_caps_static_labels():
    root = Path(__file__).resolve().parents[1] / 's1napse'
    offenders = []
    for p in root.rglob('*.py'):
        if 'vendor' in p.parts:
            continue
        for m in _SHOUTY.finditer(p.read_text(encoding='utf-8')):
            if m.group(1) not in _ALLOWED:
                offenders.append(f'{p.name}: {m.group(1)}')
    assert offenders == []


def test_live_analysis_updates_analysis_tab_after_coach_inserted():
    from PyQt6.QtWidgets import QApplication
    from s1napse.app import TelemetryApp
    app = QApplication.instance() or QApplication([])
    w = TelemetryApp()
    try:
        w._sampler.stop()
        w._sampler.join(timeout=1)
        w.auto_detect = False
        w.current_reader = w.ir_reader
        w._last_data = {'speed': 180.0, 'current_time': 15000,
                        'lap_dist_pct': 0.2, 'gear': 4}
        w.tabs.setCurrentWidget(w.lap_analysis_tab)
        w._render_telemetry()
        assert list(w.ana_speed.line.get_ydata()) == [180.0]
        w.tabs.setCurrentWidget(w.coach_tab)
        w._render_telemetry()
        assert list(w.ana_speed.line.get_ydata()) == [180.0]
    finally:
        w.close()
