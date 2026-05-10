"""Thin dismissible banner shown at the top of the main window when a newer
beta release is available on GitHub. Hidden by default."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from ..theme import ACCENT, BORDER_SUBTLE, SURFACE_RAISED, TEXT_PRIMARY


class UpdateBanner(QFrame):
    """Compact banner: '<message> [Download] [×]'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("UpdateBanner")
        self.setFixedHeight(28)
        self.setStyleSheet(
            f"""
            QFrame#UpdateBanner {{
                background-color: {SURFACE_RAISED};
                border-bottom: 1px solid {BORDER_SUBTLE};
            }}
            QFrame#UpdateBanner QLabel {{
                color: {TEXT_PRIMARY};
            }}
            QFrame#UpdateBanner QPushButton {{
                background: transparent;
                border: none;
                color: {ACCENT};
                padding: 2px 8px;
            }}
            QFrame#UpdateBanner QPushButton:hover {{
                text-decoration: underline;
            }}
            QFrame#UpdateBanner QPushButton#UpdateBannerClose {{
                color: {TEXT_PRIMARY};
            }}
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        self._message = QLabel("")
        layout.addWidget(self._message, 0, Qt.AlignmentFlag.AlignVCenter)

        self._download_btn = QPushButton("Download")
        self._download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_btn.clicked.connect(self._open_release_url)
        layout.addWidget(self._download_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch(1)

        self._close_btn = QPushButton("×")
        self._close_btn.setObjectName("UpdateBannerClose")
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setFixedWidth(24)
        self._close_btn.clicked.connect(self.hide)
        layout.addWidget(self._close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self._html_url: str = ""
        self.hide()

    def show_update(self, version: str, html_url: str) -> None:
        self._html_url = html_url
        self._message.setText(f"Synapse {version} is available")
        self.show()

    def _open_release_url(self) -> None:
        if self._html_url:
            QDesktopServices.openUrl(QUrl(self._html_url))
