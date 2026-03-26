"""Custom Qt widgets for the telemetry dashboard."""

from .gauges import RevBar, PedalBar, ValueDisplay, SteeringWidget, SteeringBar
from .tyre_card import TyreCard, _lerp_color, _TYRE_TEMP_KP, _BRAKE_TEMP_KP
from .track_map import TrackMapWidget
from .graphs import (
    ChannelGraph, MultiChannelGraph,
    AnalysisTelemetryGraph, AnalysisMultiLineGraph,
    TimeDeltaGraph, ComparisonGraph, ComparisonDeltaGraph,
    RacePaceChart, ReplayGraph, ReplayMultiGraph,
)
from .panels import SectorTimesPanel, SectorScrubWidget, LapHistoryPanel
from .badges import AidBadge
from .coach_tab import CoachTab

__all__ = [
    'RevBar', 'PedalBar', 'ValueDisplay', 'SteeringWidget', 'SteeringBar',
    'TyreCard', '_lerp_color', '_TYRE_TEMP_KP', '_BRAKE_TEMP_KP',
    'TrackMapWidget',
    'ChannelGraph', 'MultiChannelGraph',
    'AnalysisTelemetryGraph', 'AnalysisMultiLineGraph',
    'TimeDeltaGraph', 'ComparisonGraph', 'ComparisonDeltaGraph',
    'RacePaceChart', 'ReplayGraph', 'ReplayMultiGraph',
    'SectorTimesPanel', 'SectorScrubWidget', 'LapHistoryPanel',
    'AidBadge', 'CoachTab',
]
