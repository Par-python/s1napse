"""Message templates for coaching insights.

All messages follow the spec's tone guidelines:
- Plain language, no jargon
- Positive first — celebrate improvements
- Actionable — every message includes something to try
- Specific numbers — "18m too early" not "too early"
- One issue per corner
"""

from __future__ import annotations

from .models import (
    CornerPerformance, BrakingAnalysis, LapReport,
    TrailBrakeAnalysis, TyreLapSummary, SessionProgress,
)


# ---------------------------------------------------------------------------
# Corner coaching messages
# ---------------------------------------------------------------------------

def corner_message(perf: CornerPerformance) -> str:
    """Return a single plain-language message for a corner performance."""
    c = perf.corner
    label = f"Turn {c.corner_id} ({c.direction.lower()})"

    if perf.primary_issue == "baseline":
        return f"{label}: Building your baseline — keep pushing!"

    if perf.primary_issue == "great":
        delta_str = _delta_str(perf.delta_vs_best)
        return f"{label}: Great lap! {delta_str} vs your best. Entry and exit are dialled in."

    if perf.primary_issue == "minor":
        return f"{label}: Small time loss (+{perf.delta_vs_best:.2f}s) — keep building consistency."

    # Issue-specific messages (tip is pre-computed in corner_analyzer)
    return f"{label}: {perf.tip}"


# ---------------------------------------------------------------------------
# Braking messages
# ---------------------------------------------------------------------------

_BRAKING_TEMPLATES: dict[str, str] = {
    "spike": (
        "Turn {cid}: You're slamming the brake to {peak:.0f}% instantly. "
        "Try squeezing it on over half a second — this keeps the car more "
        "stable and gives you better control."
    ),
    "hesitant": (
        "Turn {cid}: Your peak brake pressure is only {peak:.0f}%. The car "
        "can handle much more. Try braking harder and shorter — firm initial "
        "pressure, then ease off as you turn in."
    ),
    "progressive": (
        "Turn {cid}: Clean braking — progressive application, good pressure. "
        "This is textbook."
    ),
}


def braking_message(ba: BrakingAnalysis) -> str:
    """Return a plain-language braking insight."""
    cid = ba.corner.corner_id
    template = _BRAKING_TEMPLATES.get(ba.brake_application_shape, "")
    msg = template.format(cid=cid, peak=ba.peak_brake_pct)

    # Append braking-point delta if significant
    if abs(ba.brake_start_delta_vs_best) > 10:
        if ba.brake_start_delta_vs_best > 0:
            msg += (
                f" You're braking {ba.brake_start_delta_vs_best:.0f}m before "
                f"your best — try braking a little later."
            )
        else:
            msg += (
                f" You're braking {abs(ba.brake_start_delta_vs_best):.0f}m "
                f"later than your best — nice commitment!"
            )

    return msg


# ---------------------------------------------------------------------------
# Quick win
# ---------------------------------------------------------------------------

def quick_win_message(perf: CornerPerformance) -> str:
    """Generate the 'Quick Win' banner message."""
    c = perf.corner
    delta = perf.delta_vs_best
    issue = perf.primary_issue

    label = f"Turn {c.corner_id} ({c.direction.lower()})"

    issue_hint = {
        "braked_early": f"braking {abs(perf.corner.braking_start_distance):.0f}m too early",
        "braked_late": "carrying too much speed in",
        "slow_apex": f"apex speed {perf.min_speed:.0f} km/h below your best",
        "slow_exit": f"exit speed {perf.exit_speed:.0f} km/h below your best",
        "late_throttle": "picking up throttle late",
    }.get(issue, "room for improvement")

    return (
        f"Your biggest opportunity this lap is {label} — "
        f"{issue_hint}. Fix this one corner for ~{delta:.1f}s."
    )


# ---------------------------------------------------------------------------
# Lap summary header
# ---------------------------------------------------------------------------

def lap_summary_text(report: LapReport) -> str:
    """One-line lap summary."""
    delta = _delta_str(report.delta_vs_best_lap)
    if report.is_personal_best:
        return f"LAP {report.lap_number} — {_fmt_time(report.lap_time_s)} — PERSONAL BEST!"
    return f"LAP {report.lap_number} — {_fmt_time(report.lap_time_s)} ({delta} vs best)"


def grade_summary_text(report: LapReport) -> str:
    """Corner grade counts as a compact string."""
    return f"Corners:  \u2022 {report.green_count} green  \u2022 {report.yellow_count} yellow  \u2022 {report.red_count} red"


# ---------------------------------------------------------------------------
# Trail braking messages
# ---------------------------------------------------------------------------

_TRAIL_BRAKE_STAGE_MSGS: dict[int, str] = {
    0: (
        "Turn {cid}: Right now you're releasing the brake before you start "
        "turning. Trail braking means keeping a bit of brake pressure as you "
        "turn in, then gradually releasing it. This pushes weight onto the "
        "front tyres and helps the car turn. Try keeping ~20-30% brake as "
        "you start to steer into the corner."
    ),
    1: (
        "Turn {cid}: You're starting to trail brake — that's a big step! "
        "Right now you're releasing the brake suddenly mid-corner. Try to "
        "ease off the brake gradually, like slowly lifting your foot, so "
        "the car stays balanced."
    ),
    2: (
        "Turn {cid}: Excellent trail braking here. Smooth brake release "
        "through the turn-in — this is exactly what fast drivers do."
    ),
}

# Icons for the compact trail-braking line
_TB_ICONS = {0: "\u274C", 1: "\u26A0\uFE0F", 2: "\u2705"}


def trail_brake_message(tb: TrailBrakeAnalysis) -> str:
    """Return coaching message for a corner's trail braking status."""
    template = _TRAIL_BRAKE_STAGE_MSGS.get(tb.stage, "")
    return template.format(cid=tb.corner.corner_id)


def trail_brake_summary_text(analyses: list[TrailBrakeAnalysis]) -> str:
    """Compact one-liner:  Trail braking: [check] T1 T3  [warn] T5  [x] T2 T4"""
    groups: dict[int, list[str]] = {0: [], 1: [], 2: []}
    for tb in analyses:
        groups[tb.stage].append(f"T{tb.corner.corner_id}")
    parts = []
    for stage in (2, 1, 0):
        if groups[stage]:
            parts.append(f"{_TB_ICONS[stage]} {' '.join(groups[stage])}")
    return "Trail braking:  " + "   ".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Tyre messages  (tyre_analyzer builds the primary message itself;
#                  these are helpers for the UI summary line)
# ---------------------------------------------------------------------------

def tyre_summary_text(ts: TyreLapSummary | None) -> str:
    """Short one-liner for the left overview panel."""
    if ts is None or ts.balance == "unknown":
        return "Tyres: No data"
    if ts.balance == "balanced":
        return f"Tyres: Balanced — fronts {ts.front_avg:.0f} C, rears {ts.rear_avg:.0f} C"
    if ts.balance == "front-biased":
        return f"Tyres: Front-biased — fronts {ts.front_avg:.0f} C, rears {ts.rear_avg:.0f} C"
    return f"Tyres: Rear-biased — fronts {ts.front_avg:.0f} C, rears {ts.rear_avg:.0f} C"


# ---------------------------------------------------------------------------
# Session progress messages
# ---------------------------------------------------------------------------

def session_progress_text(sp: SessionProgress | None) -> str:
    """Multi-line session progress summary."""
    if sp is None or not sp.lap_times:
        return ""
    lines = []
    if sp.improvement_msg:
        lines.append(sp.improvement_msg)
    lines.append(f"Consistency: {sp.consistency_pct:.0f}%")
    if sp.best_corner_msg:
        lines.append(sp.best_corner_msg)
    if sp.worst_corner_msg:
        lines.append(sp.worst_corner_msg)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _delta_str(delta: float) -> str:
    if delta <= -0.005:
        return f"-{abs(delta):.2f}s"
    if delta >= 0.005:
        return f"+{delta:.2f}s"
    return "matched your best"


def _fmt_time(seconds: float) -> str:
    """Format seconds as M:SS.mmm."""
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"{m}:{s:06.3f}"
