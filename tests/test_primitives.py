"""Visual primitives — props, sizing, paint sanity."""

import pytest
from PyQt6.QtWidgets import QApplication

from s1napse.widgets.primitives import Pill
from s1napse import theme


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


from s1napse.widgets.primitives import Card


def test_card_default_normal_dense_false(app):
    c = Card()
    assert c.variant() == 'normal'
    assert c.dense() is False


def test_card_dense_padding_smaller(app):
    c_roomy = Card(dense=False)
    c_dense = Card(dense=True)
    # roomy padding > dense padding on the content layout
    p_r = c_roomy.contentLayout().contentsMargins()
    p_d = c_dense.contentLayout().contentsMargins()
    assert p_r.left() > p_d.left()


def test_card_warn_variant_changes_border_color(app):
    c = Card(variant='warn')
    assert c.variant() == 'warn'
    # Sanity: a stylesheet was generated and contains the warn token
    assert theme.WARN[1:] in c.styleSheet().lower() or theme.WARN.lower() in c.styleSheet().lower()


def test_card_pill_attaches_to_header(app):
    c = Card(label='Last lap', pill=Pill('PB-0.41', tone='violet'))
    # A header with a label and a pill should be visible
    assert c.headerLabel().text() == 'Last lap'
    assert c.headerPill() is not None


from s1napse.widgets.primitives import Stat


def test_stat_renders_value_and_unit(app):
    s = Stat(value='12.4', unit='L')
    assert s.valueLabel().text() == '12.4'
    assert s.unitLabel() is not None
    assert s.unitLabel().text() == 'L'


def test_stat_delta_state_good(app):
    s = Stat(value='1:29.871', delta='-0.41', delta_state='good')
    style = s.deltaLabel().styleSheet()
    assert 'color:' in style.lower()
    assert theme.GOOD.lower() in style.lower()


def test_stat_no_delta(app):
    s = Stat(value='P4')
    assert s.deltaLabel() is None


def test_stat_invalid_delta_state_raises(app):
    with pytest.raises(ValueError):
        Stat(value='1', delta='+0', delta_state='maybe')
