# Beta Distribution: Inno Setup Installer + In-App Update Check

**Date:** 2026-05-09
**Status:** Design — pending implementation
**Target:** S1napse public beta release

## Goal

Replace the raw `Synapse.exe` PyInstaller output with a more legitimate-feeling beta distribution that:

1. Ships as a Windows installer (Start Menu entry, uninstaller, install path).
2. Notifies running users when a new beta version is available.
3. Costs $0 — no code signing certificate, no paid hosting.

Out of scope: code signing, auto-download/auto-apply updates, crash/usage telemetry, Microsoft Store submission. Those are post-beta concerns.

## Context

- App entry: `s1napse.py`, packaged via [Synapse.spec](../Synapse.spec) into `dist/Synapse.exe`.
- Main window: `TelemetryApp` in [s1napse/app.py](../s1napse/app.py), built around `QMainWindow` with a `TitleBar` widget at the top of the main page (line ~268).
- No existing version constant.
- Distribution today: drop the `.exe` somewhere, send users a link. Windows SmartScreen warns "Unrecognized app", many users bounce.
- GitHub repo: `Par-python/s1napse`.

## Approach

Three independent pieces:

### 1. Single-source version constant

Add to [s1napse/__init__.py](../s1napse/__init__.py):

```python
__version__ = "0.5.1-beta"
```

Read from:
- The installer build script (to name the output file and embed in installer metadata).
- The in-app update check (to compare against the latest GitHub Release tag).
- Optionally surfaced in the UI (About box / title bar) — not required for this work.

### 2. Inno Setup installer

**New file:** `installer/synapse.iss`

Inno Setup script that wraps the existing `dist/Synapse.exe` into `Synapse-Setup-<version>.exe`. Build host is **Windows only** (Inno Setup compiler `ISCC.exe` does not run on macOS/Linux); user has confirmed they will build locally on Windows.

Installer behavior:

- Install path: `{autopf}\Synapse` (resolves to `C:\Program Files\Synapse` for admin install, `%LOCALAPPDATA%\Programs\Synapse` for per-user).
- Privileges: `lowest` — per-user install by default, no admin prompt. Reduces SmartScreen friction on locked-down machines.
- Start Menu group: `Synapse`.
- Optional desktop shortcut (checkbox during install).
- Registers proper uninstaller in Add/Remove Programs with publisher "S1napse", URL pointing at the GitHub repo.
- Output: `dist/installer/Synapse-Setup-<version>.exe`.
- Compression: `lzma2/max` (acceptable build time for a beta cadence; produces noticeably smaller artifact than the raw PyInstaller `.exe`).

**Version handling:** the `.iss` file `#include`s a generated `installer/version.iss` that defines `MyAppVersion`. The build helper writes this file from `__version__` so the version lives in exactly one place.

**New file:** `tools/build_installer.py`

Python helper that runs end-to-end on Windows:

1. Read `__version__` from `s1napse/__init__.py`.
2. Write `installer/version.iss` with `#define MyAppVersion "<version>"`.
3. Run `pyinstaller --noconfirm Synapse.spec`.
4. Locate `ISCC.exe` (check PATH first, then default install path `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`).
5. Run `ISCC.exe installer/synapse.iss`.
6. Print the path to the resulting installer.

Fails fast with a clear message if Inno Setup is not installed (with a link to https://jrsoftware.org/isdl.php).

### 3. In-app update check (non-blocking banner)

**New file:** `s1napse/updater.py`

A `QThread`-based checker that:

1. Skips entirely when `not getattr(sys, 'frozen', False)` — i.e., running from source. Devs don't need update nags.
2. On app start (delayed ~3 seconds so it doesn't compete with first paint), fires a single GET to `https://api.github.com/repos/Par-python/s1napse/releases/latest` with a 5-second timeout and a `User-Agent: Synapse/<version>` header.
3. Parses the response, extracts `tag_name` (e.g. `v0.6.0-beta`), strips a leading `v`, and compares against `__version__` using `packaging.version.parse` (already a dependency tree of `pip`/setuptools, but we'll pin it explicitly in `requirements.txt`).
4. If the remote version is strictly newer, emits a Qt signal carrying `(version, html_url)`.
5. On any error (network, JSON parse, missing field, rate limit) — silently no-op. No popups, no console spam (the app is `console=False`).

**Banner UI:** `s1napse/widgets/update_banner.py`

A thin `QFrame` (~28px tall) styled to match the existing theme. Contents, left to right:

- Label: `"Synapse <new-version> is available"`.
- Link button: `"Download"` → opens `html_url` in the default browser via `QDesktopServices.openUrl`.
- Spacer.
- Close button (×) → hides the banner for the rest of the session.

Hidden by default; shown when the updater signal fires. Inserted into the main page layout in [s1napse/app.py](../s1napse/app.py) immediately after the `TitleBar` (between current lines 269 and 271). When hidden it occupies zero vertical space, so the layout is unchanged for users on the latest version.

The banner does **not** persist a "don't show again" preference — every fresh launch re-checks. Beta users *should* be nagged.

### 4. README / docs updates

Add a short "Beta install" section to [README.md](../README.md):

- Link to the latest GitHub Release.
- Note about SmartScreen: "Windows may show 'Windows protected your PC'. Click **More info** → **Run anyway**. This warning will go away once we have enough installs to build SmartScreen reputation, or once we get a code signing certificate."
- One-line uninstall note (Settings → Apps → Synapse → Uninstall).

## File layout

```
acc-telemetry/
├── installer/
│   ├── synapse.iss          # NEW — Inno Setup script
│   └── version.iss          # NEW (generated, gitignored)
├── tools/
│   └── build_installer.py   # NEW — orchestrates PyInstaller + ISCC
├── s1napse/
│   ├── __init__.py          # MODIFIED — add __version__
│   ├── app.py               # MODIFIED — instantiate updater, mount banner
│   ├── updater.py           # NEW — GitHub Releases check thread
│   └── widgets/
│       └── update_banner.py # NEW — banner widget
├── README.md                # MODIFIED — beta install section
└── .gitignore               # MODIFIED — ignore installer/version.iss, dist/installer/
```

## Release flow (manual, beta-cadence)

1. Bump `__version__` in `s1napse/__init__.py`.
2. Commit, tag `v<version>`, push.
3. On Windows machine: `python tools/build_installer.py`.
4. Create GitHub Release for the tag, upload `dist/installer/Synapse-Setup-<version>.exe` as the release asset.
5. Existing users see the banner on next launch.

No CI/CD for this iteration. If beta cadence picks up, a `.github/workflows/release.yml` on `windows-latest` is the obvious next step but it's explicitly deferred.

## Trade-offs and chosen positions

- **Per-user install (`PrivilegesRequired=lowest`)** rather than admin: lower friction, plays better with SmartScreen on managed machines. Cost: each Windows user on a shared machine installs separately, which is fine for a beta.
- **Banner over modal dialog:** user explicitly chose this. Less invasive; still visible.
- **No "skip this version" preference:** beta users on stale builds are a support burden. Re-nagging every launch is intentional.
- **Update check disabled in source mode:** prevents test runs from hitting GitHub's API and prevents confused dev-mode banners.
- **`packaging.version` for comparison** rather than naive string compare: handles `0.5.1-beta` < `0.5.10-beta` correctly and treats `-beta` suffixes per PEP 440.

## Risks

- **GitHub API rate limit:** unauthenticated requests are 60/hr per IP. One request per app launch is fine for beta volume; would need a token-backed approach at scale.
- **`packaging` PEP 440 vs. our tag style:** `0.5.1-beta` parses as `0.5.1b0` under PEP 440, which is what we want. Verified mentally; the implementation will include a unit test for the comparator.
- **Inno Setup not installed on user's build machine:** mitigated by clear error message in `build_installer.py`.
- **SmartScreen still warns:** unavoidable without a code signing cert. Documented in README. Reputation builds over time.
