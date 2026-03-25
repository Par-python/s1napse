"""Entry point for `python -m s1napse`."""

import sys
from PyQt6.QtWidgets import QApplication
from .constants import APP_STYLE
from .app import TelemetryApp


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    window = TelemetryApp()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
