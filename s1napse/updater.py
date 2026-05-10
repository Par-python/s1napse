"""GitHub Releases update checker.

Runs in a background QThread on app start, hits the public GitHub Releases API
once, and emits a signal if a newer version exists. Silent on every failure
mode (network, parse, rate limit).

Disabled when running from source (sys.frozen is False) so dev runs are quiet.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from packaging.version import InvalidVersion, Version
from PyQt6.QtCore import QThread, pyqtSignal

from . import __version__

GITHUB_REPO = "Par-python/s1napse"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
HTTP_TIMEOUT_SECONDS = 5


def _normalize_tag(tag: str) -> str:
    """Strip a leading 'v' or 'V' from a git tag."""
    if tag and tag[0] in ("v", "V"):
        return tag[1:]
    return tag


def _is_newer(remote: str, local: str) -> bool:
    """Return True iff remote is strictly newer than local per PEP 440.
    Returns False on any parse error. Both inputs may carry a leading 'v'.
    """
    try:
        return Version(_normalize_tag(remote)) > Version(_normalize_tag(local))
    except InvalidVersion:
        return False


class UpdateChecker(QThread):
    """One-shot QThread that hits the GitHub Releases API and emits
    `update_available(version, html_url)` if a newer release exists.
    Does nothing when running from source.
    """

    update_available = pyqtSignal(str, str)

    def run(self) -> None:
        if not getattr(sys, "frozen", False):
            return

        try:
            req = urllib.request.Request(
                RELEASES_URL,
                headers={"User-Agent": f"Synapse/{__version__}"},
            )
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return

        tag = payload.get("tag_name") or ""
        html_url = payload.get("html_url") or ""
        if not tag or not html_url:
            return

        if _is_newer(remote=tag, local=__version__):
            self.update_available.emit(_normalize_tag(tag), html_url)
