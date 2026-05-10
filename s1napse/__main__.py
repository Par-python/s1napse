"""Entry point for `python -m s1napse`."""

import sys


def _enable_windows_dpi_awareness():
    """Mark the process as per-monitor DPI aware on Windows.

    Without this the PyInstaller-built exe runs DPI-unaware and Windows
    bitmap-stretches the window, which makes the track map lines look fat.
    Must run before QApplication is constructed.
    """
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


_enable_windows_dpi_awareness()

from PyQt6.QtWidgets import QApplication
from . import theme
from .app import TelemetryApp


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.build_app_qss())
    window = TelemetryApp()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
