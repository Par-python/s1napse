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


def _force_win32_window_icon(window, icon_path):
    # Windows occasionally caches a stale taskbar icon for our AUMID even after
    # QApplication.setWindowIcon. Push the icon straight onto the HWND via
    # WM_SETICON so the taskbar refreshes from the file on every launch.
    if sys.platform != 'win32' or not os.path.isfile(icon_path):
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
            ctypes.c_int, ctypes.c_int, wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        ]
        user32.SendMessageW.restype = ctypes.c_void_p
        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.GetSystemMetrics.restype = ctypes.c_int

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL, ICON_BIG = 0, 1
        SM_CXICON, SM_CYICON = 11, 12
        SM_CXSMICON, SM_CYSMICON = 49, 50

        big = user32.LoadImageW(
            None, icon_path, IMAGE_ICON,
            user32.GetSystemMetrics(SM_CXICON),
            user32.GetSystemMetrics(SM_CYICON),
            LR_LOADFROMFILE,
        )
        sml = user32.LoadImageW(
            None, icon_path, IMAGE_ICON,
            user32.GetSystemMetrics(SM_CXSMICON),
            user32.GetSystemMetrics(SM_CYSMICON),
            LR_LOADFROMFILE,
        )
        hwnd = int(window.winId())
        if big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
        if sml:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, sml)
    except Exception:
        pass


_enable_windows_dpi_awareness()
_set_windows_app_user_model_id()

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from . import theme
from .app import TelemetryApp


def main():
    app = QApplication(sys.argv)
    icon_path = _icon_path()
    icon = QIcon(icon_path)
    if not icon.isNull():
        app.setWindowIcon(icon)
    app.setStyleSheet(theme.build_app_qss())
    window = TelemetryApp()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()
    _force_win32_window_icon(window, icon_path)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
