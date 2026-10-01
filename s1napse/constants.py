"""Channel colors and track-shape constants.

Chrome/theme constants live in s1napse/theme.py. This file is kept narrow:
it only exports values that paint *data*, not chrome.
"""

from PyQt6.QtGui import QFont


# --- Channel colors (used inside graphs) ------------------------------
# Tuned for the light theme: saturated enough to read as thin lines on white.
C_SPEED    = '#0071E3'
C_THROTTLE = '#34C759'
C_BRAKE    = '#FF3B30'
C_RPM      = '#FF9F0A'
C_GEAR     = '#6E6E73'
C_STEER    = '#30B0C7'
C_ABS      = '#E8590C'
C_TC       = '#D4A600'
C_DELTA    = '#1D1D1F'
C_PURPLE   = '#AF52DE'   # best lap / fastest sector (motorsport "purple")
C_PURPLE_BG = '#F5EDFB'
C_GREEN_BG  = '#E9F9EE'
C_REF      = '#D70015'

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
