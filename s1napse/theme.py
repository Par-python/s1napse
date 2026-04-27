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

# Tints — translucent variants used for pill backgrounds, card accents, etc.
# Use the same RGB as the parent token; alpha encodes intensity.
def _rgba(hex_color: str, alpha: float) -> str:
    """Convert '#RRGGBB' + alpha (0..1) into 'rgba(r,g,b,a)' for Qt stylesheets."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f'rgba({r},{g},{b},{alpha:.2f})'

ACCENT_BG     = '#1D1631'   # dark violet pill background
ACCENT_BORDER = _rgba(ACCENT, 0.32)
ACCENT_FG     = '#B4A0FF'   # readable violet on dark

GOOD_BG       = '#102A1C'
GOOD_BORDER   = _rgba(GOOD, 0.32)
GOOD_FG       = '#5FE39A'

WARN_BG       = '#2A200D'
WARN_BORDER   = _rgba(WARN, 0.32)
WARN_FG       = '#FBBF24'

BAD_BG        = '#2A1313'
BAD_BORDER    = _rgba(BAD, 0.32)
BAD_FG        = '#FCA5A5'

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


def build_app_qss() -> str:
    """Return the application-wide QSS stylesheet built from tokens."""
    return f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT_SECONDARY};
    font-size: {FONT_BODY_ROOMY}pt;
}}

QTabWidget::pane {{
    border: none;
    background: {BG};
}}

QTabBar {{
    background: {BG};
    border-bottom: 1px solid {BORDER_SUBTLE};
}}

QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 12px 14px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    font-size: {FONT_LABEL}pt;
    font-weight: 500;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}}

QTabBar::tab:selected {{
    color: {TEXT_PRIMARY};
    border-bottom-color: {ACCENT};
}}

QTabBar::tab:hover:!selected {{
    color: {TEXT_SECONDARY};
}}

QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {SURFACE_RAISED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS['md']}px;
    padding: 5px 9px;
    selection-background-color: {ACCENT};
    selection-color: {TEXT_PRIMARY};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 4px;
}}

QPushButton {{
    background: {SURFACE_RAISED};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS['md']}px;
    padding: 6px 14px;
    font-size: {FONT_LABEL}pt;
    font-weight: 500;
    letter-spacing: 0.4px;
}}

QPushButton:hover {{
    background: {SURFACE_HOVER};
    border-color: {ACCENT};
    color: {TEXT_PRIMARY};
}}

QPushButton:pressed {{
    background: {SURFACE};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    border: none;
    margin: 3px 1px;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 3px;
    min-height: 28px;
}}

QScrollBar::handle:vertical:hover  {{ background: {TEXT_MUTED}; }}
QScrollBar::handle:vertical:pressed{{ background: {ACCENT}; }}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0; background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    border: none;
    margin: 1px 3px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 3px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover  {{ background: {TEXT_MUTED}; }}
QScrollBar::handle:horizontal:pressed{{ background: {ACCENT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0; background: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

QScrollArea {{ background: transparent; border: none; }}

QGroupBox {{
    border: 1px solid {BORDER_SUBTLE};
    border-radius: {RADIUS['lg']}px;
    margin-top: 12px;
    color: {TEXT_MUTED};
    font-size: {FONT_LABEL}pt;
    letter-spacing: 0.5px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}

QLabel {{ background: transparent; color: {TEXT_SECONDARY}; }}

QSplitter::handle {{ background: {BORDER_SUBTLE}; }}

QToolTip {{
    background: {SURFACE_RAISED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    padding: 4px 6px;
    border-radius: {RADIUS['sm']}px;
}}
"""
