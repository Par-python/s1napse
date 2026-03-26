"""Lap coach orchestrator — runs all analysers after each lap."""

from __future__ import annotations

import numpy as np

from .models import LapReport, CornerBest, TyreLapSummary, SessionProgress
from .corner_detector import detect_corners, save_corners, load_corners
from .corner_analyzer import analyze_corners, save_bests, load_bests
from .braking_analyzer import analyze_braking, compute_consistency
from .trail_brake_analyzer import analyze_trail_braking
from .tyre_analyzer import analyze_tyres
from .insight_messages import quick_win_message


class LapCoach:
    """Stateful coaching engine for one session.

    Instantiate once per track/session.  Call :meth:`analyze` after every
    completed lap.
    """

    def __init__(self):
        self._corners = None                   # list[Corner] | None
        self._track_key: str = ""
        self._bests: dict[int, CornerBest] = {}
        self._braking_history: list = []       # list[list[BrakingAnalysis]]
        self._trail_brake_stages: dict[int, int] = {}   # corner_id → stage (0/1/2)
        self._tyre_history: list[TyreLapSummary] = []
        self._lap_times: list[float] = []
        self._best_lap_time: float = 0.0
        self._best_lap_number: int = 0
        self._reports: list[LapReport] = []

    @property
    def corners(self):
        return self._corners

    @property
    def reports(self) -> list[LapReport]:
        return self._reports

    def analyze(self, lap: dict) -> LapReport | None:
        """Run the full analysis pipeline on a completed lap.

        Parameters
        ----------
        lap : dict
            A completed lap dict as stored in ``session_laps`` (keys:
            ``lap_number``, ``total_time_s``, ``data``, ``meta``).

        Returns
        -------
        LapReport or None
            None if analysis cannot run (insufficient data).
        """
        data = lap.get('data', {})
        meta = lap.get('meta', {})
        lap_number = lap.get('lap_number', 0)
        lap_time = lap.get('total_time_s', 0.0)
        track_key = meta.get('track_key', '')

        if not data.get('dist_m') or len(data['dist_m']) < 50:
            return None

        # ── Track lap time for session progress ────────────────────────
        self._lap_times.append(lap_time)

        # ── Track change → reload corners and bests ──────────────────────
        if track_key and track_key != self._track_key:
            self._track_key = track_key
            self._corners = load_corners(track_key)
            self._bests = load_bests(track_key)
            self._braking_history = []
            self._trail_brake_stages = {}
            self._tyre_history = []

        # ── Corner detection (first lap or no cache) ─────────────────────
        if self._corners is None:
            self._corners = detect_corners(data)
            if self._corners and track_key:
                save_corners(track_key, self._corners)

        if not self._corners:
            return None

        # ── Corner analysis ──────────────────────────────────────────────
        corner_perfs = analyze_corners(
            self._corners, data, lap_number, self._bests)

        # ── Braking analysis ─────────────────────────────────────────────
        braking_analyses = analyze_braking(
            self._corners, data, lap_number, self._bests)
        self._braking_history.append(braking_analyses)

        # Update bests with peak brake info from braking analysis
        for ba in braking_analyses:
            cid = ba.corner.corner_id
            if cid in self._bests:
                if ba.peak_brake_pct > self._bests[cid].peak_brake_pct:
                    self._bests[cid].peak_brake_pct = ba.peak_brake_pct

        # ── Trail braking analysis ───────────────────────────────────────
        trail_analyses = analyze_trail_braking(
            self._corners, data, lap_number, self._trail_brake_stages)

        # ── Tyre analysis ────────────────────────────────────────────────
        tyre_summary = analyze_tyres(
            data, lap_number, self._tyre_history, self._lap_times)
        self._tyre_history.append(tyre_summary)

        # ── Persist personal bests ───────────────────────────────────────
        if track_key:
            save_bests(track_key, self._bests)

        # ── Personal best tracking ───────────────────────────────────────
        is_pb = False
        if self._best_lap_time <= 0 or lap_time < self._best_lap_time:
            self._best_lap_time = lap_time
            self._best_lap_number = lap_number
            is_pb = True
        delta_vs_best = lap_time - self._best_lap_time

        # ── Corner grade counts ──────────────────────────────────────────
        green = sum(1 for p in corner_perfs if p.grade == "green")
        yellow = sum(1 for p in corner_perfs if p.grade == "yellow")
        red = sum(1 for p in corner_perfs if p.grade == "red")

        # ── Quick win ────────────────────────────────────────────────────
        quick_corner = None
        quick_msg = ""
        worst = [p for p in corner_perfs if p.delta_vs_best > 0.05]
        if worst:
            worst.sort(key=lambda p: p.delta_vs_best, reverse=True)
            quick_corner = worst[0].corner.corner_id
            quick_msg = quick_win_message(worst[0])

        consistency = compute_consistency(self._braking_history)

        # ── Session progress ─────────────────────────────────────────────
        session_progress = self._compute_session_progress(corner_perfs)

        # ── Assemble report ──────────────────────────────────────────────
        report = LapReport(
            lap_number=lap_number,
            lap_time_s=lap_time,
            delta_vs_best_lap=round(delta_vs_best, 3),
            corner_performances=corner_perfs,
            braking_analyses=braking_analyses,
            trail_brake_analyses=trail_analyses,
            tyre_summary=tyre_summary,
            session_progress=session_progress,
            quick_win_corner_id=quick_corner,
            quick_win_message=quick_msg,
            green_count=green,
            yellow_count=yellow,
            red_count=red,
            is_personal_best=is_pb,
            braking_consistency_pct=consistency,
        )

        self._reports.append(report)
        return report

    # ------------------------------------------------------------------
    # Session progress
    # ------------------------------------------------------------------

    def _compute_session_progress(
        self, corner_perfs: list,
    ) -> SessionProgress:
        sp = SessionProgress(
            lap_times=list(self._lap_times),
            best_lap_time=self._best_lap_time,
            best_lap_number=self._best_lap_number,
        )

        # Consistency: 100 - normalised stddev of last 10 laps
        window = self._lap_times[-10:]
        if len(window) >= 2:
            mean = float(np.mean(window))
            std = float(np.std(window))
            if mean > 0:
                sp.consistency_pct = round(max(0.0, 100.0 - (std / mean) * 1000), 1)

        # Improvement message
        if len(self._lap_times) >= 5:
            first_5 = float(np.mean(self._lap_times[:5]))
            last_5 = float(np.mean(self._lap_times[-5:]))
            drop = first_5 - last_5
            if drop > 0.3:
                sp.improvement_msg = (
                    f"You've dropped {drop:.1f}s average since the start of the session"
                )
            elif drop < -0.3:
                sp.improvement_msg = (
                    f"Lap times have risen {abs(drop):.1f}s on average — "
                    f"tyres or concentration fading?"
                )

        # Best / worst corner this lap
        if corner_perfs:
            best_c = min(corner_perfs, key=lambda p: p.delta_vs_best)
            worst_c = max(corner_perfs, key=lambda p: p.delta_vs_best)
            if best_c.delta_vs_best < -0.05:
                sp.best_corner_msg = (
                    f"Best corner: Turn {best_c.corner.corner_id} — "
                    f"{abs(best_c.delta_vs_best):.2f}s faster than your previous best!"
                )
            if worst_c.delta_vs_best > 0.1:
                sp.worst_corner_msg = (
                    f"Worst corner: Turn {worst_c.corner.corner_id} — "
                    f"+{worst_c.delta_vs_best:.2f}s ({worst_c.primary_issue.replace('_', ' ')})"
                )

        return sp
