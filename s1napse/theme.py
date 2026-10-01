"""Design tokens for the S1napse UI.

Single source of truth for all colors/typography/spacing in the app chrome.
Channel colors (C_SPEED, C_THROTTLE, etc.) live in constants.py — they
belong to graphs, not chrome.
"""

# Light, Apple-style palette: smoky-white ground, white cards, graphite ink.
# Colour is reserved for data and state (good / warn / bad / info).

# Surface scale --------------------------------------------------------
BG             = '#F5F5F7'
SURFACE        = '#FFFFFF'
SURFACE_RAISED = '#FFFFFF'
SURFACE_HOVER  = '#EDEDF0'
BORDER_SUBTLE  = '#E3E3E8'
BORDER_STRONG  = '#D2D2D7'

# Text scale -----------------------------------------------------------
TEXT_PRIMARY   = '#1D1D1F'
TEXT_SECONDARY = '#424245'
TEXT_MUTED     = '#6E6E73'
TEXT_FAINT     = '#AEAEB2'

# Accent + state -------------------------------------------------------
ACCENT = '#1D1D1F'      # graphite: selected tab, primary buttons, focus
GOOD   = '#34C759'
WARN   = '#FF9F0A'
BAD    = '#FF3B30'
INFO   = '#0071E3'      # links and informational highlights

# Tints — translucent variants used for pill backgrounds, card accents, etc.
# Use the same RGB as the parent token; alpha encodes intensity.
def _rgba(hex_color: str, alpha: float) -> str:
    """Convert '#RRGGBB' + alpha (0..1) into 'rgba(r,g,b,a)' for Qt stylesheets."""
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f'rgba({r},{g},{b},{alpha:.2f})'

ACCENT_BG     = '#EDEDF0'   # neutral pill background
ACCENT_BORDER = _rgba(ACCENT, 0.14)
ACCENT_FG     = '#1D1D1F'

GOOD_BG       = '#E9F9EE'
GOOD_BORDER   = _rgba(GOOD, 0.35)
GOOD_FG       = '#248A3D'   # readable green on white

WARN_BG       = '#FFF4E5'
WARN_BORDER   = _rgba(WARN, 0.40)
WARN_FG       = '#C93400'

BAD_BG        = '#FFECEB'
BAD_BORDER    = _rgba(BAD, 0.35)
BAD_FG        = '#D70015'

# Layout scales --------------------------------------------------------
SPACING = (4, 8, 12, 16, 20, 24, 32)
RADIUS  = {'sm': 6, 'md': 10, 'lg': 14, 'xl': 18}

# Typography (point sizes used by font helpers) ------------------------
FONT_UI_FAMILY   = 'Inter'
# Numbers use the UI face with tabular figures (see mono_font), not a monospace.
FONT_MONO_FAMILY = 'Inter'

# Five text roles. Everything on screen uses one of these.
FONT_HERO   = 34   # the one big number on a card
FONT_VALUE  = 20   # secondary readings
FONT_BODY   = 12   # running text, table cells, coaching messages
FONT_LABEL  = 10   # card / field labels, sentence case
FONT_FINE   = 9    # units, footnotes, axis text

# Legacy names, mapped onto the roles so existing call sites keep working.
FONT_DISPLAY     = FONT_HERO
FONT_NUMERIC_LG  = FONT_VALUE
FONT_NUMERIC_MD  = 13
FONT_HEADING     = 14
FONT_BODY_DENSE  = 11
FONT_BODY_ROOMY  = FONT_BODY

from PyQt6.QtGui import QFont


def ui_font(size: int = FONT_BODY_ROOMY, *, bold: bool = False) -> QFont:
    """Inter (or system fallback) at the given point size."""
    f = QFont(FONT_UI_FAMILY, size)
    f.setStyleHint(QFont.StyleHint.SansSerif)
    f.setBold(bold)
    return f


def mono_font(size: int = FONT_NUMERIC_MD, *, bold: bool = False) -> QFont:
    """Numeric face: the UI sans with tabular figures, semibold for readouts."""
    f = QFont(FONT_MONO_FAMILY, size)
    f.setStyleHint(QFont.StyleHint.SansSerif)
    f.setStyleStrategy(QFont.StyleStrategy.PreferMatch)
    f.setBold(bold)
    if hasattr(f, 'setFeatureSettings'):
        f.setFeatureSettings('tnum')  # tabular numerals — digits don't jitter
    return f


def label_font() -> QFont:
    """Small sentence-case label: medium weight, a hair of tracking."""
    f = QFont(FONT_UI_FAMILY, FONT_LABEL)
    f.setStyleHint(QFont.StyleHint.SansSerif)
    f.setWeight(QFont.Weight.Medium)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.2)
    return f


def build_app_qss() -> str:
    """Return the application-wide QSS stylesheet built from tokens."""
    return f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT_SECONDARY};
}}

QTabWidget::pane {{
    border: none;
    background: {BG};
}}

QTabBar {{
    background: {BG};
    border: none;
    qproperty-drawBase: 0;
}}

QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 7px 14px;
    margin: 8px 2px 8px 2px;
    border: none;
    border-radius: {RADIUS['md']}px;
    font-size: {FONT_BODY}pt;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background: {SURFACE_HOVER};
    color: {TEXT_PRIMARY};
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
    selection-background-color: {INFO};
    selection-color: #FFFFFF;
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
