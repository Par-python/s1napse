"""Token constant sanity checks."""

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


def test_ui_font_helper_returns_qfont():
    from PyQt6.QtGui import QFont
    f = theme.ui_font(12)
    assert isinstance(f, QFont)
    assert f.pointSize() == 12


def test_mono_font_uses_tabular_figures():
    from PyQt6.QtGui import QFont
    f = theme.mono_font(13)
    assert isinstance(f, QFont)
    assert f.pointSize() == 13
    feat = f.featureSettings() if hasattr(f, 'featureSettings') else ''
    assert 'tnum' in feat or f.styleStrategy() != QFont.StyleStrategy.PreferDefault


def test_label_font_uppercase_letterspacing():
    f = theme.label_font()
    assert f.pointSize() == theme.FONT_LABEL
    assert f.letterSpacing() > 1.0


def test_build_app_qss_returns_string_with_tokens():
    qss = theme.build_app_qss()
    assert isinstance(qss, str)
    # Surface tokens flow through
    assert theme.BG in qss
    assert theme.SURFACE in qss
    assert theme.BORDER_SUBTLE in qss
    # Accent applied to active tab underline
    assert theme.ACCENT in qss
    # Text tokens applied
    assert theme.TEXT_PRIMARY in qss
    # Tabs styled
    assert 'QTabBar::tab' in qss
    # Buttons styled
    assert 'QPushButton' in qss


def test_build_app_qss_no_legacy_colors():
    qss = theme.build_app_qss()
    # Old muddled hexes from constants.py must not appear
    for legacy in ('#0b0b0b', '#111111', '#181818', '#222222',
                   '#2a2a2a', '#383838', '#c8c8c8', '#6a6a6a', '#f2f2f2'):
        assert legacy.lower() not in qss.lower(), f'legacy color {legacy} leaked into theme QSS'
