# Beta Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace raw `Synapse.exe` with an Inno Setup installer plus an in-app GitHub Releases update banner, at zero cost.

**Architecture:** A single `__version__` constant feeds (a) a Windows-only Inno Setup installer build script that wraps the existing PyInstaller output, and (b) a background `QThread` that polls GitHub Releases on app start and surfaces a dismissible banner under the title bar when a newer version exists. Update check is disabled when running from source.

**Tech Stack:** Python 3, PyQt6, PyInstaller (existing), Inno Setup 6 (new, Windows-only), `packaging.version` (new pinned dep), stdlib `urllib.request` for HTTP.

**Spec:** [docs/2026-05-09-beta-distribution-design.md](../../2026-05-09-beta-distribution-design.md)

**Repo for update check:** `Par-python/s1napse`

---

## File Structure

**Create:**
- `installer/synapse.iss` — Inno Setup script
- `tools/build_installer.py` — orchestrator (PyInstaller + ISCC)
- `s1napse/updater.py` — GitHub Releases checker (`QThread`)
- `s1napse/widgets/update_banner.py` — banner widget
- `tests/test_updater.py` — version comparator + tag parsing tests
- `.gitignore` — new file

**Modify:**
- `s1napse/__init__.py` — add `__version__`
- `s1napse/widgets/__init__.py` — export `UpdateBanner`
- `s1napse/app.py` — instantiate updater, mount banner under TitleBar
- `requirements.txt` — pin `packaging`
- `README.md` — beta install section

---

## Task 1: Add version constant

**Files:**
- Modify: `s1napse/__init__.py`

- [ ] **Step 1: Read current contents**

Run: `cat s1napse/__init__.py`
Expected: single comment line `# s1napse telemetry package`.

- [ ] **Step 2: Add version constant**

Replace file contents with:

```python
# s1napse telemetry package

__version__ = "0.5.1-beta"
```

- [ ] **Step 3: Verify it imports**

Run: `python -c "import s1napse; print(s1napse.__version__)"`
Expected output: `0.5.1-beta`

- [ ] **Step 4: Commit**

```bash
git add s1napse/__init__.py
git commit -m "chore: introduce __version__ constant for beta release"
```

---

## Task 2: Pin `packaging` dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append `packaging` to requirements.txt**

Add this line at the end of `requirements.txt`:

```
packaging>=23.0
```

The full file should become:

```
PyQt6>=6.4.0
matplotlib>=3.7.0
scipy>=1.10.0
numpy>=1.24.0
pyaccsharedmemory>=1.0.0
psutil>=5.9.0
pyirsdk>=1.3.5
obd>=0.7.1
packaging>=23.0
```

- [ ] **Step 2: Install it locally**

Run: `pip install 'packaging>=23.0'`
Expected: install succeeds (often already a transitive dep, may say "Requirement already satisfied").

- [ ] **Step 3: Verify import**

Run: `python -c "from packaging.version import Version; print(Version('0.5.1-beta'))"`
Expected output: `0.5.1b0` (PEP 440 normalized form — confirms parser handles our tag style).

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: pin packaging for version-compare in updater"
```

---

## Task 3: Updater module — TDD on the version comparator

The updater has two halves: pure logic (parse tag, compare versions) and side-effecting I/O (`urllib`, `QThread`). We test the pure half. The I/O half is small enough to exercise manually.

**Files:**
- Create: `tests/test_updater.py`
- Create: `s1napse/updater.py`

- [ ] **Step 1: Write failing tests for pure helpers**

Create `tests/test_updater.py` with:

```python
"""Unit tests for the GitHub Releases updater pure helpers."""

import pytest

from s1napse.updater import _normalize_tag, _is_newer


class TestNormalizeTag:
    def test_strips_leading_v(self):
        assert _normalize_tag("v0.5.1-beta") == "0.5.1-beta"

    def test_no_prefix_unchanged(self):
        assert _normalize_tag("0.6.0-beta") == "0.6.0-beta"

    def test_uppercase_v_stripped(self):
        assert _normalize_tag("V1.0.0") == "1.0.0"

    def test_empty_returns_empty(self):
        assert _normalize_tag("") == ""


class TestIsNewer:
    def test_higher_patch_is_newer(self):
        assert _is_newer(remote="0.5.2-beta", local="0.5.1-beta") is True

    def test_higher_minor_is_newer(self):
        assert _is_newer(remote="0.6.0-beta", local="0.5.9-beta") is True

    def test_double_digit_patch_is_newer(self):
        # Naive string compare would say "0.5.10-beta" < "0.5.9-beta"; PEP 440 must not.
        assert _is_newer(remote="0.5.10-beta", local="0.5.9-beta") is True

    def test_same_version_is_not_newer(self):
        assert _is_newer(remote="0.5.1-beta", local="0.5.1-beta") is False

    def test_older_is_not_newer(self):
        assert _is_newer(remote="0.5.0-beta", local="0.5.1-beta") is False

    def test_stable_newer_than_beta(self):
        # 1.0.0 final is newer than 1.0.0-beta under PEP 440.
        assert _is_newer(remote="1.0.0", local="1.0.0-beta") is True

    def test_handles_v_prefix_on_either_side(self):
        assert _is_newer(remote="v0.6.0-beta", local="v0.5.1-beta") is True

    def test_invalid_remote_returns_false(self):
        # Garbage in -> never claim there's an update.
        assert _is_newer(remote="not-a-version", local="0.5.1-beta") is False

    def test_invalid_local_returns_false(self):
        assert _is_newer(remote="0.6.0", local="not-a-version") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_updater.py -v`
Expected: collection error / `ModuleNotFoundError: No module named 's1napse.updater'`.

- [ ] **Step 3: Implement `s1napse/updater.py` (helpers + thread)**

Create `s1napse/updater.py` with:

```python
"""GitHub Releases update checker.

Runs in a background QThread on app start, hits the public GitHub Releases API
once, and emits a signal if a newer version exists. Silent on every failure
mode (network, parse, rate limit) — the goal is "nag user about updates," not
"warn user about anything that goes wrong."

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
    """Strip a leading 'v' or 'V' from a git tag. Returns the input unchanged
    if there's no prefix or the input is empty."""
    if tag and tag[0] in ("v", "V"):
        return tag[1:]
    return tag


def _is_newer(remote: str, local: str) -> bool:
    """Return True iff the remote version string represents a strictly newer
    release than the local one, per PEP 440. Returns False on any parse error.
    Both inputs may carry a leading 'v'.
    """
    try:
        return Version(_normalize_tag(remote)) > Version(_normalize_tag(local))
    except InvalidVersion:
        return False


class UpdateChecker(QThread):
    """One-shot QThread that hits the GitHub Releases API and emits
    `update_available(version, html_url)` if a newer release exists.

    Does nothing (and emits nothing) when running from source.
    """

    update_available = pyqtSignal(str, str)  # (version, html_url)

    def run(self) -> None:  # noqa: D401 — Qt API
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_updater.py -v`
Expected: all 13 tests pass.

- [ ] **Step 5: Commit**

```bash
git add s1napse/updater.py tests/test_updater.py
git commit -m "feat: add GitHub Releases update checker"
```

---

## Task 4: Update banner widget

**Files:**
- Create: `s1napse/widgets/update_banner.py`
- Modify: `s1napse/widgets/__init__.py`

- [ ] **Step 1: Inspect existing widget exports**

Run: `cat s1napse/widgets/__init__.py | head -40`
Expected: an `__all__` or list of imports from sibling widget modules. Note the style.

- [ ] **Step 2: Create the banner widget**

Create `s1napse/widgets/update_banner.py`:

```python
"""Thin dismissible banner shown at the top of the main window when a newer
beta release is available on GitHub. Hidden by default — has zero vertical
footprint when not shown."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from ..theme import ACCENT, BORDER_SUBTLE, SURFACE_RAISED, TEXT_PRIMARY


class UpdateBanner(QFrame):
    """Compact banner: '<message> [Download] [×]'.

    Use `show_update(version, html_url)` to display; the close button hides it
    for the rest of the session.
    """

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
```

- [ ] **Step 3: Export from widgets package**

Modify `s1napse/widgets/__init__.py` — add at the end of the existing imports:

```python
from .update_banner import UpdateBanner
```

If the file uses `__all__`, append `"UpdateBanner"` to it. (Read the file first to match style.)

- [ ] **Step 4: Verify it imports without errors**

Run: `python -c "from s1napse.widgets import UpdateBanner; print(UpdateBanner)"`
Expected: prints the class object, no traceback.

- [ ] **Step 5: Commit**

```bash
git add s1napse/widgets/update_banner.py s1napse/widgets/__init__.py
git commit -m "feat: add UpdateBanner widget"
```

---

## Task 5: Wire updater + banner into the main window

**Files:**
- Modify: `s1napse/app.py`

- [ ] **Step 1: Read the relevant region**

Run: `sed -n '1,5p;55,75p;245,275p' s1napse/app.py`
Expected: shows the imports area, widget imports area, and the `_init_ui` block where `TitleBar` is added at line ~268-269.

- [ ] **Step 2: Add the imports**

In `s1napse/app.py`, locate the existing widget import block ending at the line `from .widgets.title_bar import TitleBar` (around line 59). Modify the multi-line `from .widgets import (...)` import block to also import `UpdateBanner` — append `UpdateBanner,` on the line that lists `AidBadge, LiveTabBar,`. The block becomes:

```python
from .widgets import (
    RevBar, PedalBar, ValueDisplay, SteeringWidget, SteeringBar,
    TyreCard, _lerp_color, _TYRE_TEMP_KP, TrackMapWidget,
    ChannelGraph, MultiChannelGraph,
    AnalysisTelemetryGraph, AnalysisMultiLineGraph,
    TimeDeltaGraph, ComparisonGraph, ComparisonDeltaGraph,
    RacePaceChart, ReplayGraph, ReplayMultiGraph,
    SectorTimesPanel, SectorScrubWidget, LapHistoryPanel,
    AidBadge, LiveTabBar, UpdateBanner,
)
```

Then directly below the existing `from .widgets.title_bar import TitleBar` line, add:

```python
from .updater import UpdateChecker
```

- [ ] **Step 3: Mount the banner under the title bar**

Find this block in `_init_ui` (around lines 268-270):

```python
        self.title_bar = TitleBar()
        main_layout.addWidget(self.title_bar)
```

Replace it with:

```python
        self.title_bar = TitleBar()
        main_layout.addWidget(self.title_bar)

        self.update_banner = UpdateBanner()
        main_layout.addWidget(self.update_banner)
```

- [ ] **Step 4: Start the update checker**

At the very end of `_init_ui` (just before the method's closing — find the last line of the method, typically a `self.show()` or end-of-method), append:

```python
        # --- Update check (no-op when running from source) ---
        self._update_checker = UpdateChecker(self)
        self._update_checker.update_available.connect(
            self.update_banner.show_update
        )
        self._update_checker.start()
```

If the method is long and you can't easily spot the end, search for the next `def ` after `_init_ui` and insert these lines immediately above that next `def`, but still indented to method body level (8 spaces).

- [ ] **Step 5: Smoke test from source**

Run: `python s1napse.py` (or however the app is normally launched on this machine — see README).
Expected: app launches normally; no banner appears (because `sys.frozen` is False in source mode); no console errors related to the updater. Close the app.

If the app cannot be launched on macOS because of Windows-only readers, instead run:

```bash
python -c "from s1napse.app import TelemetryApp; print('import ok')"
```

Expected: `import ok`, no traceback. This proves the wiring at least imports cleanly.

- [ ] **Step 6: Commit**

```bash
git add s1napse/app.py
git commit -m "feat: mount UpdateBanner and start UpdateChecker in main window"
```

---

## Task 6: Inno Setup script

**Files:**
- Create: `installer/synapse.iss`

- [ ] **Step 1: Create the installer directory and script**

Create `installer/synapse.iss`:

```iss
; Inno Setup script for Synapse beta installer.
; Build with: tools/build_installer.py (Windows-only).
;
; Version is injected via installer/version.iss, which is generated from
; s1napse/__init__.py at build time.

#include "version.iss"

#define MyAppName "Synapse"
#define MyAppPublisher "S1napse"
#define MyAppURL "https://github.com/Par-python/s1napse"
#define MyAppExeName "Synapse.exe"

[Setup]
; AppId: stable GUID so upgrades replace the previous install rather than
; creating a second entry in Add/Remove Programs. Generated once for this app.
AppId={{6F7B0E6E-1F8D-4F3A-9D1B-5A7C2E1F9A01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=Synapse-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Synapse.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
```

- [ ] **Step 2: Verify the file is well-formed (best-effort on macOS)**

Run: `wc -l installer/synapse.iss`
Expected: ~50 lines, file exists. (Real syntax check happens when ISCC runs on Windows.)

- [ ] **Step 3: Commit**

```bash
git add installer/synapse.iss
git commit -m "build: add Inno Setup script for Synapse installer"
```

---

## Task 7: `tools/build_installer.py`

**Files:**
- Create: `tools/build_installer.py`

- [ ] **Step 1: Confirm `tools/` exists**

Run: `ls tools/`
Expected: directory exists with at least one file in it. If it doesn't exist, create it: `mkdir -p tools`.

- [ ] **Step 2: Create the build orchestrator**

Create `tools/build_installer.py`:

```python
"""End-to-end installer build for Synapse (Windows-only).

Steps performed:
  1. Read __version__ from s1napse/__init__.py.
  2. Write installer/version.iss with that version.
  3. Run PyInstaller against Synapse.spec.
  4. Locate ISCC.exe (Inno Setup compiler).
  5. Run ISCC.exe installer/synapse.iss.
  6. Print the resulting installer path.

Usage:
    python tools/build_installer.py

Run this from the project root on a Windows machine that has Python,
PyInstaller, and Inno Setup 6 installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT_PY = ROOT / "s1napse" / "__init__.py"
SPEC_FILE = ROOT / "Synapse.spec"
ISS_FILE = ROOT / "installer" / "synapse.iss"
VERSION_ISS = ROOT / "installer" / "version.iss"
DIST_DIR = ROOT / "dist"
INSTALLER_OUT = DIST_DIR / "installer"

DEFAULT_ISCC = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
INNO_DOWNLOAD = "https://jrsoftware.org/isdl.php"


def read_version() -> str:
    text = INIT_PY.read_text(encoding="utf-8")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("__version__"):
            # __version__ = "0.5.1-beta"
            _, _, rhs = line.partition("=")
            return rhs.strip().strip('"').strip("'")
    raise RuntimeError(f"__version__ not found in {INIT_PY}")


def write_version_iss(version: str) -> None:
    VERSION_ISS.parent.mkdir(parents=True, exist_ok=True)
    VERSION_ISS.write_text(
        f'#define MyAppVersion "{version}"\n',
        encoding="utf-8",
    )
    print(f"[build] wrote {VERSION_ISS} -> {version}")


def run_pyinstaller() -> None:
    print("[build] running PyInstaller…")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", str(SPEC_FILE)],
        cwd=str(ROOT),
        check=True,
    )
    exe = DIST_DIR / "Synapse.exe"
    if not exe.exists():
        raise RuntimeError(f"PyInstaller did not produce {exe}")
    print(f"[build] PyInstaller produced {exe}")


def find_iscc() -> Path:
    on_path = shutil.which("ISCC") or shutil.which("ISCC.exe")
    if on_path:
        return Path(on_path)
    if DEFAULT_ISCC.exists():
        return DEFAULT_ISCC
    raise RuntimeError(
        "Inno Setup compiler (ISCC.exe) not found.\n"
        f"Install Inno Setup 6 from {INNO_DOWNLOAD} and try again,\n"
        "or add ISCC.exe to your PATH."
    )


def run_iscc() -> Path:
    iscc = find_iscc()
    print(f"[build] running {iscc}…")
    subprocess.run(
        [str(iscc), str(ISS_FILE)],
        cwd=str(ROOT),
        check=True,
    )
    # Locate the produced installer (only one, named per the .iss OutputBaseFilename).
    candidates = sorted(INSTALLER_OUT.glob("Synapse-Setup-*.exe"))
    if not candidates:
        raise RuntimeError(f"ISCC ran but no installer found in {INSTALLER_OUT}")
    return candidates[-1]


def main() -> int:
    if os.name != "nt":
        print("[build] WARNING: this script is intended for Windows. ISCC will not run elsewhere.")
    version = read_version()
    print(f"[build] version = {version}")
    write_version_iss(version)
    run_pyinstaller()
    installer = run_iscc()
    print(f"[build] DONE -> {installer}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Sanity-check the version reader**

Run: `python -c "import sys; sys.path.insert(0, 'tools'); from build_installer import read_version; print(read_version())"`
Expected output: `0.5.1-beta`.

- [ ] **Step 4: Commit**

```bash
git add tools/build_installer.py
git commit -m "build: add build_installer.py to drive PyInstaller + ISCC"
```

---

## Task 8: `.gitignore`

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Check that no .gitignore exists yet**

Run: `ls -la .gitignore`
Expected: `ls: .gitignore: No such file or directory`. If a `.gitignore` exists, read it and append the entries below instead of overwriting.

- [ ] **Step 2: Create `.gitignore`**

Create `.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# PyInstaller / installer build artifacts
build/
dist/
*.spec.bak

# Generated installer version include
installer/version.iss

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Verify nothing important is now ignored**

Run: `git status --ignored | head -40`
Expected: only build outputs, caches, and `installer/version.iss` show as ignored — no source files.

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore covering build artifacts and installer/version.iss"
```

---

## Task 9: README beta install section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the existing README structure**

Run: `head -60 README.md`
Expected: identifies where install/usage sections begin so the new section can be slotted in naturally.

- [ ] **Step 2: Add a "Beta install (Windows)" section**

Insert this section near the top of `README.md`, after the project title/intro and before any developer-setup section. Adjust heading level (`##` vs `###`) to match the existing structure:

```markdown
## Beta install (Windows)

1. Download the latest installer from the [Releases page](https://github.com/Par-python/s1napse/releases/latest) — look for `Synapse-Setup-<version>.exe`.
2. Run the installer. **Windows may show a blue "Windows protected your PC" dialog.** Click **More info**, then **Run anyway**. This warning appears because the beta build is not yet code-signed; it goes away once SmartScreen has seen enough installs.
3. Pick a Start Menu group (default `Synapse`) and optionally a desktop shortcut, then finish the wizard.

Synapse will check for new beta releases on startup and show a small banner at the top of the window when one is available — click **Download** to jump straight to the release page.

To uninstall: **Settings → Apps → Synapse → Uninstall**.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add beta install instructions and SmartScreen note"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass, including the 13 new tests in `test_updater.py`. If a pre-existing test fails for unrelated reasons, note it but do not fix it as part of this work.

- [ ] **Step 2: Verify imports of all new modules**

Run:
```bash
python -c "
import s1napse
from s1napse.updater import UpdateChecker, _is_newer, _normalize_tag
from s1napse.widgets import UpdateBanner
print('version:', s1napse.__version__)
print('updater + banner imported OK')
"
```
Expected output:
```
version: 0.5.1-beta
updater + banner imported OK
```

- [ ] **Step 3: Confirm git log**

Run: `git log --oneline -n 12`
Expected: roughly 9 new commits from Tasks 1-9, on top of the prior tip (`62830b8 docs: add beta distribution design …`).

- [ ] **Step 4: Print Windows-build instructions for the user**

Output (do not commit) the following message so the user knows what to do on their Windows box:

```
Beta packaging is in place. To produce the installer:

  1. On a Windows machine with this branch checked out:
       pip install -r requirements.txt
       pip install pyinstaller
       Install Inno Setup 6 from https://jrsoftware.org/isdl.php
  2. From the project root:
       python tools/build_installer.py
  3. Output: dist/installer/Synapse-Setup-0.5.1-beta.exe
  4. Tag the commit (git tag v0.5.1-beta && git push --tags), create a
     GitHub Release for that tag, and upload the .exe as a release asset.
```

---

## Self-review notes

- **Spec coverage:**
  - Version constant → Task 1.
  - Inno Setup installer (synapse.iss + tools/build_installer.py) → Tasks 6, 7.
  - Update check (updater.py) → Task 3.
  - Banner widget + main-window mount → Tasks 4, 5.
  - README beta install section → Task 9.
  - .gitignore for `installer/version.iss` and `dist/` → Task 8.
  - `packaging` dependency pinned → Task 2.
  - Unit test on the comparator (called out in the spec's Risks section) → Task 3.
- **No placeholders.** All code, paths, and commands are concrete.
- **Type/name consistency:** `UpdateChecker.update_available(str, str)` matches `UpdateBanner.show_update(version, html_url)`. `_normalize_tag` and `_is_newer` are used identically across module + tests. `__version__` string is consistent everywhere.
- **Out of scope (per spec):** code signing, auto-apply updates, GH Actions workflow, Microsoft Store submission. Not included by design.
