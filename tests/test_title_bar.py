import pytest
from PyQt6.QtWidgets import QApplication
from s1napse.widgets.title_bar import TitleBar


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_titlebar_default_no_source(app):
    t = TitleBar()
    assert t.brand() == 'S1NAPSE'
    assert t.sourceText() == ''


def test_titlebar_set_source_visible(app):
    t = TitleBar()
    t.setSource('ACC · MONZA · 28°C / 34°C', live=True)
    assert t.sourceText() == 'ACC · MONZA · 28°C / 34°C'
    assert t.isLive() is True


def test_titlebar_set_session(app):
    t = TitleBar()
    t.setSession(lap='8 / —', stint='Stint 2', last_lap='1:29.871')
    assert t.sessionLap().text() == '8 / —'
    assert t.sessionStint().text() == 'Stint 2'
    assert t.sessionLastLap().text() == '1:29.871'
