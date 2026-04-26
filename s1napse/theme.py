"""Design tokens for the S1napse UI.

Single source of truth for all colors/typography/spacing in the app chrome.
Channel colors (C_SPEED, C_THROTTLE, etc.) live in constants.py — they
belong to graphs, not chrome.
"""

# Surface scale --------------------------------------------------------
BG             = '#0A0B0D'
SURFACE        = '#0E0F12'
SURFACE_RAISED = '#14161A'
SURFACE_HOVER  = '#1C1F25'
BORDER_SUBTLE  = '#1A1D23'
BORDER_STRONG  = '#262A31'

# Text scale -----------------------------------------------------------
TEXT_PRIMARY   = '#F2F3F5'
TEXT_SECONDARY = '#C2C7D0'
TEXT_MUTED     = '#8B94A3'
TEXT_FAINT     = '#5A626F'

# Accent + state -------------------------------------------------------
ACCENT = '#8B5CF6'
GOOD   = '#22C55E'
WARN   = '#F59E0B'
BAD    = '#EF4444'
INFO   = '#22D3EE'

# Layout scales --------------------------------------------------------
SPACING = (4, 8, 12, 16, 20, 24)
RADIUS  = {'sm': 4, 'md': 6, 'lg': 8, 'xl': 10}

# Typography (point sizes used by font helpers) ------------------------
FONT_UI_FAMILY   = 'Inter'
FONT_MONO_FAMILY = 'JetBrains Mono'

FONT_DISPLAY     = 22
FONT_NUMERIC_LG  = 17
FONT_NUMERIC_MD  = 13
FONT_HEADING     = 14
FONT_BODY_DENSE  = 11
FONT_BODY_ROOMY  = 12
FONT_LABEL       = 10

from PyQt6.QtGui import QFont


def ui_font(size: int = FONT_BODY_ROOMY, *, bold: bool = False) -> QFont:
    """Inter (or system fallback) at the given point size."""
    f = QFont(FONT_UI_FAMILY, size)
    f.setStyleHint(QFont.StyleHint.SansSerif)
    f.setBold(bold)
    return f


def mono_font(size: int = FONT_NUMERIC_MD, *, bold: bool = False) -> QFont:
    """JetBrains Mono (or system mono fallback) with tabular figures."""
    f = QFont(FONT_MONO_FAMILY, size)
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setStyleStrategy(QFont.StyleStrategy.PreferMatch)
    f.setBold(bold)
    if hasattr(f, 'setFeatureSettings'):
        f.setFeatureSettings('tnum')  # tabular numerals — digits don't jitter
    return f


def label_font() -> QFont:
    """10pt uppercase label with positive letter-spacing."""
    f = QFont(FONT_UI_FAMILY, FONT_LABEL)
    f.setStyleHint(QFont.StyleHint.SansSerif)
    f.setWeight(QFont.Weight.Medium)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
    f.setCapitalization(QFont.Capitalization.AllUppercase)
    return f
