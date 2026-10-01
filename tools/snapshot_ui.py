"""Render every S1napse screen offscreen to PNGs, fed by telemetry_simulator.js.

usage: python3 tools/snapshot_ui.py OUTDIR [seconds_of_data]
"""
import os
import subprocess
import sys
import time
import tempfile
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


def _pump(app, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> None:
    out = sys.argv[1]
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 210.0
    os.makedirs(out, exist_ok=True)

    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    from s1napse import theme
    from s1napse.app import TelemetryApp
    app.setStyleSheet(theme.build_app_qss())

    # Simulator reports must not replace the driver's saved corner bests.
    from s1napse.coaching import corner_detector, corner_analyzer
    cache = tempfile.TemporaryDirectory(prefix='s1napse-snapshot-')
    corner_detector._get_tracks_dir = lambda: Path(cache.name)
    corner_analyzer._get_tracks_dir = lambda: Path(cache.name)

    sim = subprocess.Popen(['node', os.path.join(REPO, 'telemetry_simulator.js')],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        w = TelemetryApp()
        w.resize(1600, 1000)
        w.show()
        w._stack.setCurrentIndex(0)
        _pump(app, 0.3)
        w.grab().save(os.path.join(out, '00-welcome.png'))
        w._app_mode = 'sim'
        w._stack.setCurrentIndex(1)
        w.game_combo.setCurrentText('AC')
        w._on_game_changed('AC')
        _pump(app, secs)
        if sim.poll() is not None:
            raise RuntimeError('Telemetry simulator exited before screenshots were captured.')
        if secs >= 180 and (not w.session_laps or w.coach_tab.isEmptyState()):
            raise RuntimeError('No coached lap captured; increase the data duration.')
        w._refresh_comparison()
        if w.session_laps:
            w._load_replay_lap(len(w.session_laps) - 1)
            w._replay_seek(int(w._replay_total_ms * 0.5))
        for i in range(w.tabs.count()):
            w.tabs.setCurrentIndex(i)
            _pump(app, 0.4)
            name = w.tabs.tabText(i).lower().replace(' ', '-')
            w.grab().save(os.path.join(out, f'{i + 1:02d}-{name}.png'))
        w.title_bar.showPopover()
        _pump(app, 0.3)
        w.title_bar.popover().grab().save(os.path.join(out, '10-source-popover.png'))
        w.title_bar.popover().hide()
        w._stack.setCurrentIndex(2)
        _pump(app, 0.3)
        w.grab().save(os.path.join(out, '20-obd-setup.png'))
        w._on_obd_demo()
        _pump(app, 4)
        w._stack.setCurrentIndex(3)
        _pump(app, 0.4)
        w.grab().save(os.path.join(out, '21-real-racing.png'))
        print('completed laps:', len(w.session_laps), 'coach corners:', w.coach_tab.cornerCount(), flush=True)
        print('saved', sorted(os.listdir(out)), flush=True)
    finally:
        sim.terminate()
        try:
            sim.wait(timeout=3)
        except subprocess.TimeoutExpired:
            sim.kill()
            sim.wait()
        if 'w' in locals():
            w.close()
        cache.cleanup()


if __name__ == '__main__':
    main()
