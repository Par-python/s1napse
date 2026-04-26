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
