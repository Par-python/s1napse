"""End-to-end installer build for Synapse (Windows-only).

Steps:
  1. Read __version__ from s1napse/__init__.py.
  2. Write installer/version.iss with that version.
  3. Run PyInstaller against Synapse.spec.
  4. Locate ISCC.exe (Inno Setup compiler).
  5. Run ISCC.exe installer/synapse.iss.
  6. Print the resulting installer path.

Usage:
    python tools/build_installer.py

Run from project root on a Windows machine with Python, PyInstaller, and
Inno Setup 6 installed.
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
    exe = DIST_DIR / "S1napse.exe"
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
    candidates = sorted(INSTALLER_OUT.glob("S1napse-Setup-*.exe"))
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
