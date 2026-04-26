"""Visual primitives — props, sizing, paint sanity."""

import pytest
from PyQt6.QtWidgets import QApplication

from s1napse.widgets.primitives import Pill


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_pill_neutral_default(app):
    p = Pill('+1 lap')
    assert p.text() == '+1 lap'
    assert p.tone() == 'neutral'


def test_pill_tone_violet(app):
    p = Pill('PB', tone='violet')
    assert p.tone() == 'violet'


def test_pill_invalid_tone_raises(app):
    with pytest.raises(ValueError):
        Pill('x', tone='magenta')
