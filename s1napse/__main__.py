"""Entry point for `python -m s1napse`."""

import sys
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
