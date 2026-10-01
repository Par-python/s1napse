"""Pre-built math channel definitions.

These ship with the app as ``built_in=True`` channels.  Users can see the
formulas as learning references, duplicate them into editable copies, and
toggle visibility — but cannot edit or delete them directly.

**Channel names below are adapted to the actual raw telemetry channel names
produced by the S1napse readers** (``speed``, ``throttle``, ``brake``,
``steer_deg``, ``fuel_l``, ``tyre_temp_fl``, etc.).
"""

from __future__ import annotations


# Each entry is a dict matching the MathEngine.add_channel() kwargs.
# Order matters: channels that depend on other built-in channels must
# appear *after* their dependencies so registration succeeds.

PRESETS: list[dict] = [
    # ------------------------------------------------------------------
    # Tyre diagnostics
    # ------------------------------------------------------------------
    {
        'name':        'front_temp_avg',
        'formula':     'avg(tyre_temp_fl, tyre_temp_fr)',
        'unit':        '\u00b0C',
        'color':       '#E8590C',
        'description': 'Average front tyre temperature.',
    },
    {
        'name':        'rear_temp_avg',
        'formula':     'avg(tyre_temp_rl, tyre_temp_rr)',
        'unit':        '\u00b0C',
        'color':       '#00A8A0',
        'description': 'Average rear tyre temperature.',
    },
    {
        'name':        'temp_balance_fb',
        'formula':     'front_temp_avg - rear_temp_avg',
        'unit':        '\u00b0C',
        'color':       '#D4A600',
        'description': 'Front vs rear temp balance. Positive = fronts hotter.',
    },
    {
        'name':        'tyre_temp_avg',
        'formula':     'avg(tyre_temp_fl, tyre_temp_fr, tyre_temp_rl, tyre_temp_rr)',
        'unit':        '\u00b0C',
        'color':       '#34C759',
        'description': 'Average temperature across all four tyres.',
    },
    {
        'name':        'tyre_temp_spread',
        'formula':     ('max(max(tyre_temp_fl, tyre_temp_fr), '
                        'max(tyre_temp_rl, tyre_temp_rr)) - '
                        'min(min(tyre_temp_fl, tyre_temp_fr), '
                        'min(tyre_temp_rl, tyre_temp_rr))'),
        'unit':        '\u00b0C',
        'color':       '#FF3B30',
        'description': 'Spread between hottest and coolest tyre. High = imbalance.',
    },

    # ------------------------------------------------------------------
    # Driving technique
    # ------------------------------------------------------------------
    {
        'name':        'trail_brake_flag',
        'formula':     '1 if brake > 5 and abs(steer_deg) > 15 else 0',
        'unit':        '',
        'color':       '#0071E3',
        'description': '1 when trail braking (brake + steering together), 0 otherwise.',
    },
    {
        'name':        'throttle_rate',
        'formula':     'clamp(rate(throttle), -500, 500)',
        'unit':        '%/s',
        'color':       '#248A3D',
        'description': 'How fast you apply or release throttle. Smooth drivers keep this low.',
    },
    {
        'name':        'brake_rate',
        'formula':     'clamp(rate(brake), -500, 500)',
        'unit':        '%/s',
        'color':       '#C93400',
        'description': 'How fast you apply or release brake.',
    },
    {
        'name':        'throttle_jitter',
        'formula':     'abs(delta(throttle))',
        'unit':        '%',
        'color':       '#6E6E73',
        'description': 'Per-tick throttle change. Helper channel for smoothness.',
    },
    {
        'name':        'throttle_smoothness',
        'formula':     'rolling_avg(throttle_jitter, 20)',
        'unit':        '',
        'color':       '#30B0C7',
        'description': 'Throttle smoothness score. Lower = smoother application.',
    },

    # ------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------
    {
        'name':        'accel_longitudinal',
        'formula':     'rate(speed) / 3.6',
        'unit':        'm/s\u00b2',
        'color':       '#FF9F0A',
        'description': 'Longitudinal acceleration. Positive = accel, negative = braking.',
    },
    {
        'name':        'peak_brake_recent',
        'formula':     'rolling_max(brake, 100)',
        'unit':        '%',
        'color':       '#5856D6',
        'description': 'Peak brake pressure over the last 5 seconds.',
    },
    {
        'name':        'fuel_used_lap',
        'formula':     'lap_start(fuel_l) - fuel_l',
        'unit':        'L',
        'color':       '#A2845E',
        'description': 'Fuel used so far this lap. Resets each lap.',
    },
]


# Raw telemetry channel names that S1napse readers produce (scalar values
# after array expansion).  Registered up-front so preset formulas validate
# even before the first telemetry tick arrives.
RAW_CHANNEL_NAMES: set[str] = {
    'speed', 'throttle', 'brake', 'steer_deg', 'rpm', 'gear', 'abs', 'tc',
    'fuel_l', 'brake_bias_pct', 'air_temp', 'road_temp',
    'tyre_temp_fl', 'tyre_temp_fr', 'tyre_temp_rl', 'tyre_temp_rr',
    'tyre_pressure_fl', 'tyre_pressure_fr', 'tyre_pressure_rl', 'tyre_pressure_rr',
    'brake_temp_fl', 'brake_temp_fr', 'brake_temp_rl', 'brake_temp_rr',
    'tyre_wear_fl', 'tyre_wear_fr', 'tyre_wear_rl', 'tyre_wear_rr',
}


def register_presets(engine) -> None:
    """Register all pre-built channels on *engine* (a ``MathEngine``)."""
    # Seed raw channel names so formulas referencing them pass validation
    engine.set_raw_channels(engine._raw_channel_names | RAW_CHANNEL_NAMES)

    for preset in PRESETS:
        engine.add_channel(
            name=preset['name'],
            formula=preset['formula'],
            unit=preset.get('unit', ''),
            color=preset.get('color', '#FFFFFF'),
            built_in=True,
            description=preset.get('description', ''),
            visible=preset.get('visible', False),
        )
