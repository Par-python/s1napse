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
