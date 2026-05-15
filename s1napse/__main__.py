"""Entry point for `python -m s1napse`."""

import os
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


def _set_windows_app_user_model_id():
    # Without this, Windows groups the running app under the default Python/Qt
    # icon in the taskbar instead of using the window icon we set on QApplication.
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('s1napse.s1napse')
    except Exception:
        pass


def _icon_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'icon.ico')
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'icon.ico',
    )


_enable_windows_dpi_awareness()
_set_windows_app_user_model_id()

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from . import theme
from .app import TelemetryApp


def main():
    app = QApplication(sys.argv)
    icon = QIcon(_icon_path())
    if not icon.isNull():
        app.setWindowIcon(icon)
    app.setStyleSheet(theme.build_app_qss())
    window = TelemetryApp()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
