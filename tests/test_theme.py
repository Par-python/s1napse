"""Token constant sanity checks."""

from s1napse import theme


def test_surface_scale_present():
    assert theme.BG == '#F5F5F7'
    assert theme.SURFACE == '#FFFFFF'
    assert theme.SURFACE_RAISED == '#FFFFFF'
    assert theme.SURFACE_HOVER == '#EDEDF0'
    assert theme.BORDER_SUBTLE == '#E3E3E8'
    assert theme.BORDER_STRONG == '#D2D2D7'


def test_text_scale_present():
    assert theme.TEXT_PRIMARY == '#1D1D1F'
    assert theme.TEXT_SECONDARY == '#424245'
    assert theme.TEXT_MUTED == '#6E6E73'
    assert theme.TEXT_FAINT == '#AEAEB2'


def test_accent_and_state_colors():
    assert theme.ACCENT == '#1D1D1F'
    assert theme.GOOD == '#34C759'
    assert theme.WARN == '#FF9F0A'
    assert theme.BAD == '#FF3B30'
    assert theme.INFO == '#0071E3'


def test_spacing_and_radius_scales():
    assert theme.SPACING == (4, 8, 12, 16, 20, 24, 32)
    assert theme.RADIUS == {'sm': 6, 'md': 10, 'lg': 14, 'xl': 18}


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


def test_label_font_sentence_case():
    from PyQt6.QtGui import QFont
    f = theme.label_font()
    assert f.pointSize() == theme.FONT_LABEL
    assert f.capitalization() == QFont.Capitalization.MixedCase
    assert f.letterSpacing() < 1.0


def test_type_roles_present():
    assert theme.FONT_HERO == 34
    assert theme.FONT_VALUE == 20
    assert theme.FONT_BODY == 12
    assert theme.FONT_LABEL == 10
    assert theme.FONT_FINE == 9
    # legacy aliases still resolve
    assert theme.FONT_DISPLAY == theme.FONT_HERO
    assert theme.FONT_NUMERIC_LG == theme.FONT_VALUE
    assert theme.FONT_BODY_ROOMY == theme.FONT_BODY


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
