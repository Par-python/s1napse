"""Token constants and QSS builder sanity checks."""

from s1napse import theme


def test_surface_scale_present():
    assert theme.BG == '#0A0B0D'
    assert theme.SURFACE == '#0E0F12'
    assert theme.SURFACE_RAISED == '#14161A'
    assert theme.SURFACE_HOVER == '#1C1F25'
    assert theme.BORDER_SUBTLE == '#1A1D23'
    assert theme.BORDER_STRONG == '#262A31'


def test_text_scale_present():
    assert theme.TEXT_PRIMARY == '#F2F3F5'
    assert theme.TEXT_SECONDARY == '#C2C7D0'
    assert theme.TEXT_MUTED == '#8B94A3'
    assert theme.TEXT_FAINT == '#5A626F'


def test_accent_and_state_colors():
    assert theme.ACCENT == '#8B5CF6'
    assert theme.GOOD == '#22C55E'
    assert theme.WARN == '#F59E0B'
    assert theme.BAD == '#EF4444'
    assert theme.INFO == '#22D3EE'


def test_spacing_and_radius_scales():
    assert theme.SPACING == (4, 8, 12, 16, 20, 24)
    assert theme.RADIUS == {'sm': 4, 'md': 6, 'lg': 8, 'xl': 10}
