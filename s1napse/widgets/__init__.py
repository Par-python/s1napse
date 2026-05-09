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
from .math_formula_editor import FormulaEditorWidget
from .math_channel_panel import MathChannelPanel
from .primitives import Card, Pill, Stat, Sparkline, GapBar
from .title_bar import TitleBar
from .tab_bar import LiveTabBar
from .update_banner import UpdateBanner

__all__ = [
    'RevBar', 'PedalBar', 'ValueDisplay', 'SteeringWidget', 'SteeringBar',
    'TyreCard', '_lerp_color', '_TYRE_TEMP_KP', '_BRAKE_TEMP_KP',
    'TrackMapWidget',
    'ChannelGraph', 'MultiChannelGraph',
    'AnalysisTelemetryGraph', 'AnalysisMultiLineGraph',
    'TimeDeltaGraph', 'ComparisonGraph', 'ComparisonDeltaGraph',
    'RacePaceChart', 'ReplayGraph', 'ReplayMultiGraph',
    'SectorTimesPanel', 'SectorScrubWidget', 'LapHistoryPanel',
    'AidBadge',
    'FormulaEditorWidget', 'MathChannelPanel',
    'Card', 'Pill', 'Stat', 'Sparkline', 'GapBar',
    'TitleBar',
    'LiveTabBar',
    'UpdateBanner',
]
