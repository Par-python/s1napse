"""Data models for the coaching engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Corner geometry (detected once per track, cached)
# ---------------------------------------------------------------------------

@dataclass
class Corner:
    corner_id: int                    # 1-indexed
    direction: str                    # "LEFT" or "RIGHT"
    entry_distance: float             # metres from start/finish
    turn_in_distance: float
    apex_distance: float
    exit_distance: float
    braking_start_distance: float     # where brake > threshold before entry

    def to_dict(self) -> dict:
        return {
            'corner_id': self.corner_id,
            'direction': self.direction,
            'entry_distance': round(self.entry_distance, 1),
            'turn_in_distance': round(self.turn_in_distance, 1),
            'apex_distance': round(self.apex_distance, 1),
            'exit_distance': round(self.exit_distance, 1),
            'braking_start_distance': round(self.braking_start_distance, 1),
        }

    @classmethod
    def from_dict(cls, d: dict) -> Corner:
        return cls(
            corner_id=d['corner_id'],
            direction=d['direction'],
            entry_distance=d['entry_distance'],
            turn_in_distance=d['turn_in_distance'],
            apex_distance=d['apex_distance'],
            exit_distance=d['exit_distance'],
            braking_start_distance=d['braking_start_distance'],
        )


# ---------------------------------------------------------------------------
# Per-corner, per-lap performance
# ---------------------------------------------------------------------------

@dataclass
class CornerPerformance:
    corner: Corner
    lap_number: int
    entry_speed: float                # km/h at turn_in_distance
    min_speed: float                  # km/h at apex
    exit_speed: float                 # km/h at exit_distance
    braking_distance: float           # metres from brake start to apex
    time_in_corner: float             # seconds from entry to exit
    delta_vs_best: float              # seconds gained/lost vs personal best
    throttle_application_distance: float  # dist from apex where throttle > 20%
    grade: str = ""                   # "green", "yellow", "red"
    primary_issue: str = ""           # single biggest problem key
    tip: str = ""                     # actionable one-liner


# ---------------------------------------------------------------------------
# Per-corner braking analysis
# ---------------------------------------------------------------------------

@dataclass
class BrakingAnalysis:
    corner: Corner
    lap_number: int
    brake_start_distance: float       # where brake > 5%
    brake_start_speed: float          # speed at brake initiation
    brake_start_delta_vs_best: float  # metres early/late vs best (negative = later)
    peak_brake_pct: float             # max brake % (0-100)
    time_to_peak_ms: int              # ms from brake start to peak
    brake_application_shape: str      # "progressive", "spike", "hesitant"
    total_brake_duration_m: float     # metres from brake start to brake = 0
    speed_scrubbed: float             # brake_start_speed - min_speed
    deceleration_efficiency: float    # speed_scrubbed / total_brake_duration_m


# ---------------------------------------------------------------------------
# Per-corner personal best (persisted across sessions)
# ---------------------------------------------------------------------------

@dataclass
class CornerBest:
    corner_id: int
    best_time_in_corner: float        # seconds
    entry_speed: float
    min_speed: float
    exit_speed: float
    braking_distance: float
    brake_start_distance: float
    peak_brake_pct: float
    throttle_application_distance: float

    def to_dict(self) -> dict:
        return {
            'corner_id': self.corner_id,
            'best_time_in_corner': round(self.best_time_in_corner, 4),
            'entry_speed': round(self.entry_speed, 1),
            'min_speed': round(self.min_speed, 1),
            'exit_speed': round(self.exit_speed, 1),
            'braking_distance': round(self.braking_distance, 1),
            'brake_start_distance': round(self.brake_start_distance, 1),
            'peak_brake_pct': round(self.peak_brake_pct, 1),
            'throttle_application_distance': round(self.throttle_application_distance, 1),
        }

    @classmethod
    def from_dict(cls, d: dict) -> CornerBest:
        return cls(**d)


# ---------------------------------------------------------------------------
# Trail braking per corner
# ---------------------------------------------------------------------------

@dataclass
class TrailBrakeAnalysis:
    corner: Corner
    lap_number: int
    detected: bool                    # any brake+steer overlap at all
    overlap_distance: float           # metres of brake+steer overlap
    overlap_entry_brake_pct: float    # brake % at moment steering begins
    brake_release_gradient: float     # brake_pct lost per metre through overlap
    brake_at_apex: float              # brake % at apex distance
    release_quality: str              # "smooth", "abrupt", "none"
    stage: int = 0                    # coaching stage 0/1/2


# ---------------------------------------------------------------------------
# Tyre snapshot (end-of-lap, single core temp per tyre)
# ---------------------------------------------------------------------------

@dataclass
class TyreLapSummary:
    lap_number: int
    temp_fl: float                    # core temp at end of lap
    temp_fr: float
    temp_rl: float
    temp_rr: float
    pressure_fl: float
    pressure_fr: float
    pressure_rl: float
    pressure_rr: float
    front_avg: float                  # (FL + FR) / 2
    rear_avg: float                   # (RL + RR) / 2
    left_avg: float                   # (FL + RL) / 2
    right_avg: float                  # (FR + RR) / 2
    balance: str = ""                 # "balanced", "front-biased", "rear-biased"
    message: str = ""


# ---------------------------------------------------------------------------
# Session progress metrics
# ---------------------------------------------------------------------------

@dataclass
class SessionProgress:
    lap_times: list[float] = field(default_factory=list)   # all lap times in order
    best_lap_time: float = 0.0
    best_lap_number: int = 0
    consistency_pct: float = 0.0      # 100 - normalised stddev of last 10 laps
    improvement_msg: str = ""         # e.g. "Dropped 1.2s in last 10 laps"
    best_corner_msg: str = ""
    worst_corner_msg: str = ""


# ---------------------------------------------------------------------------
# Aggregated lap report
# ---------------------------------------------------------------------------

@dataclass
class LapReport:
    lap_number: int
    lap_time_s: float
    delta_vs_best_lap: float          # seconds vs overall best lap
    corner_performances: list[CornerPerformance] = field(default_factory=list)
    braking_analyses: list[BrakingAnalysis] = field(default_factory=list)
    trail_brake_analyses: list[TrailBrakeAnalysis] = field(default_factory=list)
    tyre_summary: Optional[TyreLapSummary] = None
    session_progress: Optional[SessionProgress] = None
    quick_win_corner_id: Optional[int] = None
    quick_win_message: str = ""
    green_count: int = 0
    yellow_count: int = 0
    red_count: int = 0
    is_personal_best: bool = False
    braking_consistency_pct: float = 0.0  # 0-100
