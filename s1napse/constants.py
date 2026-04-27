"""Channel colors and track-shape constants.

Chrome/theme constants live in s1napse/theme.py. This file is kept narrow:
it only exports values that paint *data*, not chrome.
"""

from PyQt6.QtGui import QFont


# --- Channel colors (used inside graphs) ------------------------------
C_SPEED    = '#00d4ff'
C_THROTTLE = '#00e87a'
C_BRAKE    = '#ff3232'
C_RPM      = '#ffc200'
C_GEAR     = '#e0e0e0'
C_STEER    = '#cc77ff'
C_ABS      = '#ff7f00'
C_TC       = '#ffe000'
C_DELTA    = '#4499ff'
C_PURPLE   = '#a855f7'
C_PURPLE_BG = '#1e0f35'
C_GREEN_BG  = '#0a2218'
C_REF      = '#e74c3c'

# Number of distance-buckets used to store per-position telemetry
N_TRACK_SEG = 220

# Fallback length used by graph x-axis before a real track length is known
MONZA_LENGTH_M: int = 5000

# No default track - widget starts empty and builds live
DEFAULT_TRACK: str | None = None


# --- Legacy font helpers (kept for files not yet migrated to theme) ---

def mono(size: int, bold: bool = False) -> QFont:
    f = QFont('Consolas', size)
    f.setBold(bold)
    return f


def sans(size: int, bold: bool = False) -> QFont:
    f = QFont()
    f.setPointSize(size)
    f.setBold(bold)
    return f
