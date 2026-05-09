"""Le Mans Ultimate via the rFactor 2 Shared Memory Plugin.

Requires:
    - pip install pyRfactor2SharedMemory
    - rFactor2SharedMemoryMapPlugin64.dll installed in LMU's Plugins folder
      and enabled in CustomPluginVariables.JSON (note the leading-space
      ' Enabled' key — required by the game).
"""

from .base import TelemetryReader


class LMUReader(TelemetryReader):
    """Le Mans Ultimate via the rFactor 2 Shared Memory Plugin."""

    def __init__(self):
        self._last_read_ok = False
        self.info = None
        self._cbytestring = None
        try:
            from pyRfactor2SharedMemory.sharedMemoryAPI import (
                Cbytestring2Python,
                SimInfoAPI,
            )
            self.info = SimInfoAPI()
            self._cbytestring = Cbytestring2Python
            self.available = True
        except Exception as e:
            print(f"LMU Reader initialization failed: {e}")
            print("Install with: pip install pyRfactor2SharedMemory")
            print(
                "Also: install rFactor2SharedMemoryMapPlugin64.dll into "
                "LMU's Plugins folder and enable it in CustomPluginVariables.JSON"
            )
            self.available = False

    def read(self):
        if not self.available:
            self._last_read_ok = False
            return None
        # Field extraction lands in Task 3.
        self._last_read_ok = False
        return None

    def is_connected(self):
        if not self.available:
            return False
        return self._last_read_ok
