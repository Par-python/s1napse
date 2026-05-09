"""Unit tests for LMUReader — runnable on macOS/Linux via mocking."""

import math
from unittest.mock import patch, MagicMock


def test_lmu_reader_unavailable_when_import_fails():
    """If pyRfactor2SharedMemory cannot be imported, the reader should
    set available=False and read()/is_connected() should return safely."""
    # Force import failure inside __init__ by patching the module's import.
    with patch.dict('sys.modules', {'pyRfactor2SharedMemory.sharedMemoryAPI': None}):
        from s1napse.readers.lmu import LMUReader
        # Re-instantiating should hit the except path because the patched
        # entry forces ImportError on `from ... import ...`.
        reader = LMUReader()
        assert reader.available is False
        assert reader.read() is None
        assert reader.is_connected() is False


def _make_fake_telemetry(**overrides):
    """Build a MagicMock matching the rF2 Telemetry struct shape we use."""
    telem = MagicMock()
    telem.mEngineRPM = 7000.0
    telem.mEngineMaxRPM = 9000.0
    telem.mGear = 3
    telem.mUnfilteredThrottle = 0.85
    telem.mUnfilteredBrake = 0.10
    telem.mUnfilteredSteering = -0.25
    telem.mFuel = 42.5
    telem.mFuelCapacity = 100.0
    telem.mLocalVel = MagicMock(x=10.0, y=0.0, z=0.0)  # |v| = 10 m/s = 36 km/h
    telem.mRearBrakeBias = 0.55
    telem.mElapsedTime = 123.456
    telem.mFrontTireCompoundName = b"Hard\x00\x00"
    # 4 wheels, default zeros — Task 4 fills these.
    wheel = MagicMock(
        mTireCarcassTemperature=300.0,  # Kelvin
        mPressure=180.0,
        mBrakeTemp=400.0,  # Kelvin
        mWear=0.0,
    )
    telem.mWheels = [wheel, wheel, wheel, wheel]
    for k, v in overrides.items():
        setattr(telem, k, v)
    return telem


def _make_fake_scoring(**overrides):
    """Build a MagicMock matching the rF2 Scoring struct shape we use."""
    veh = MagicMock()
    veh.mLastLapTime = 91.234
    veh.mPlace = 4
    veh.mVehicleName = b"Ferrari 499P\x00"
    veh.mTotalLaps = 7
    veh.mLapStartET = 100.0
    veh.mLapDist = 1500.0
    veh.mPos = MagicMock(x=123.0, y=0.0, z=-456.0)
    veh.mCountLapFlag = 1
    veh.mInPits = 0
    veh.mBestLapTime = 90.5
    veh.mTimeBehindNext = 1.5

    info = MagicMock()
    info.mTrackName = b"Le Mans\x00"
    info.mAmbientTemp = 22.0
    info.mTrackTemp = 35.0
    info.mSession = 6  # race
    info.mLapDist = 13629.0
    info.mCurrentET = 191.234

    scoring = MagicMock()
    scoring.mScoringInfo = info
    scoring.mVehicles = [veh]
    for k, v in overrides.items():
        setattr(scoring, k, v)
    return scoring


def _build_reader_with_fakes(telem, scoring):
    """Bypass __init__'s real import, install fakes, return a ready reader."""
    from s1napse.readers.lmu import LMUReader
    reader = LMUReader.__new__(LMUReader)
    reader.available = True
    reader._last_read_ok = False

    api = MagicMock()
    api.playerTelemetry.return_value = telem
    api.playerScoring.return_value = scoring
    reader.info = api

    # Cbytestring decoder: strip NULs and decode utf-8.
    reader._cbytestring = lambda b: b.split(b"\x00", 1)[0].decode("utf-8", "ignore")
    return reader


def test_speed_converts_m_s_to_km_h():
    telem = _make_fake_telemetry()
    scoring = _make_fake_scoring()
    reader = _build_reader_with_fakes(telem, scoring)
    data = reader.read()
    assert math.isclose(data['speed'], 36.0, abs_tol=0.01)


def test_rpm_and_max_rpm_pass_through():
    reader = _build_reader_with_fakes(_make_fake_telemetry(), _make_fake_scoring())
    data = reader.read()
    assert data['rpm'] == 7000.0
    assert data['max_rpm'] == 9000.0


def test_gear_normalization():
    """rF2: -1=R, 0=N, 1+=fwd → ACC: 0=R, 1=N, 2+=fwd. Add 1."""
    for rf2_gear, acc_gear in [(-1, 0), (0, 1), (1, 2), (5, 6)]:
        reader = _build_reader_with_fakes(
            _make_fake_telemetry(mGear=rf2_gear),
            _make_fake_scoring(),
        )
        assert reader.read()['gear'] == acc_gear, f"gear={rf2_gear}"


def test_pedals_scale_to_percent():
    reader = _build_reader_with_fakes(
        _make_fake_telemetry(mUnfilteredThrottle=0.85, mUnfilteredBrake=0.10),
        _make_fake_scoring(),
    )
    data = reader.read()
    assert math.isclose(data['throttle'], 85.0, abs_tol=0.01)
    assert math.isclose(data['brake'], 10.0, abs_tol=0.01)


def test_fuel_passthrough():
    reader = _build_reader_with_fakes(
        _make_fake_telemetry(mFuel=42.5, mFuelCapacity=100.0),
        _make_fake_scoring(),
    )
    data = reader.read()
    assert data['fuel'] == 42.5
    assert data['max_fuel'] == 100.0


def test_tyre_temp_kelvin_to_celsius():
    """rF2 tire carcass temp is Kelvin; ACC dict expects Celsius."""
    wheels = [
        MagicMock(mTireCarcassTemperature=350.0, mPressure=180.0,
                  mBrakeTemp=500.0, mWear=0.05),
        MagicMock(mTireCarcassTemperature=355.0, mPressure=181.0,
                  mBrakeTemp=505.0, mWear=0.06),
        MagicMock(mTireCarcassTemperature=340.0, mPressure=175.0,
                  mBrakeTemp=480.0, mWear=0.04),
        MagicMock(mTireCarcassTemperature=345.0, mPressure=176.0,
                  mBrakeTemp=485.0, mWear=0.045),
    ]
    telem = _make_fake_telemetry()
    telem.mWheels = wheels
    reader = _build_reader_with_fakes(telem, _make_fake_scoring())
    data = reader.read()
    # Kelvin - 273.15
    assert math.isclose(data['tyre_temp'][0], 350.0 - 273.15, abs_tol=0.01)
    assert math.isclose(data['tyre_temp'][3], 345.0 - 273.15, abs_tol=0.01)


def test_brake_temp_kelvin_to_celsius():
    wheels = [
        MagicMock(mTireCarcassTemperature=300.0, mPressure=180.0,
                  mBrakeTemp=600.0, mWear=0.0),
    ] * 4
    telem = _make_fake_telemetry()
    telem.mWheels = wheels
    reader = _build_reader_with_fakes(telem, _make_fake_scoring())
    data = reader.read()
    for v in data['brake_temp']:
        assert math.isclose(v, 600.0 - 273.15, abs_tol=0.01)


def test_tyre_pressure_passthrough():
    """rF2 pressure is kPa; ACC also kPa — no conversion."""
    wheels = [
        MagicMock(mTireCarcassTemperature=300.0, mPressure=178.0,
                  mBrakeTemp=400.0, mWear=0.0),
    ] * 4
    telem = _make_fake_telemetry()
    telem.mWheels = wheels
    reader = _build_reader_with_fakes(telem, _make_fake_scoring())
    data = reader.read()
    assert data['tyre_pressure'] == [178.0, 178.0, 178.0, 178.0]


def test_tyre_wear_scales_to_percent():
    """rF2 mWear is 0..1; ACC reader returns 0..100."""
    wheels = [
        MagicMock(mTireCarcassTemperature=300.0, mPressure=180.0,
                  mBrakeTemp=400.0, mWear=0.25),
    ] * 4
    telem = _make_fake_telemetry()
    telem.mWheels = wheels
    reader = _build_reader_with_fakes(telem, _make_fake_scoring())
    data = reader.read()
    assert data['tyre_wear'] == [25.0, 25.0, 25.0, 25.0]


def test_lap_fields():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mLastLapTime = 91.234
    scoring.mVehicles[0].mTotalLaps = 7
    scoring.mScoringInfo.mCurrentET = 200.0
    scoring.mVehicles[0].mLapStartET = 105.0
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    data = reader.read()
    assert math.isclose(data['lap_time'], 91.234, abs_tol=0.001)
    assert data['lap_count'] == 7
    # current_time is (mCurrentET - mLapStartET) seconds × 1000 → ms
    assert math.isclose(data['current_time'], 95.0 * 1000.0, abs_tol=0.1)


def test_position_passthrough():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mPlace = 12
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    assert reader.read()['position'] == 12


def test_lap_dist_pct_normalised():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mLapDist = 1500.0
    scoring.mScoringInfo.mLapDist = 6000.0
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    assert math.isclose(reader.read()['lap_dist_pct'], 0.25, abs_tol=0.001)


def test_world_position_xz():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mPos = MagicMock(x=111.0, y=2.0, z=-222.0)
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    data = reader.read()
    assert data['world_x'] == 111.0
    assert data['world_z'] == -222.0


def test_pit_and_lap_validity_flags():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mInPits = 1
    scoring.mVehicles[0].mCountLapFlag = 0  # invalid
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    data = reader.read()
    assert data['is_in_pit_lane'] is True
    assert data['lap_valid'] is False


def test_byte_string_names_decode():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mVehicleName = b"Porsche 963\x00\x00\x00"
    scoring.mScoringInfo.mTrackName = b"Sebring International\x00"
    telem = _make_fake_telemetry()
    telem.mFrontTireCompoundName = b"Soft\x00\x00\x00"
    reader = _build_reader_with_fakes(telem, scoring)
    data = reader.read()
    assert data['car_name'] == "Porsche 963"
    assert data['track_name'] == "Sebring International"
    assert data['tyre_compound'] == "Soft"


def test_session_type_mapping():
    """rF2 mSession: 0=test, 1-4=practice, 5-8=qualify, 9=warmup, 10-13=race."""
    cases = [
        (1, 'PRACTICE'),
        (5, 'QUALIFY'),
        (9, 'PRACTICE'),  # warmup → treat as practice
        (10, 'RACE'),
        (13, 'RACE'),
    ]
    for code, expected in cases:
        scoring = _make_fake_scoring()
        scoring.mScoringInfo.mSession = code
        reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
        assert reader.read()['session_type'] == expected, f"code={code}"


def test_weather_passthrough():
    scoring = _make_fake_scoring()
    scoring.mScoringInfo.mAmbientTemp = 18.5
    scoring.mScoringInfo.mTrackTemp = 28.0
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    data = reader.read()
    assert data['air_temp'] == 18.5
    assert data['road_temp'] == 28.0


def test_estimated_lap_seconds_to_ms():
    scoring = _make_fake_scoring()
    scoring.mVehicles[0].mBestLapTime = 89.123
    reader = _build_reader_with_fakes(_make_fake_telemetry(), scoring)
    assert math.isclose(reader.read()['estimated_lap'], 89123.0, abs_tol=1.0)


def test_read_returns_none_when_no_session():
    """playerTelemetry/playerScoring may return None when no session active."""
    from s1napse.readers.lmu import LMUReader
    reader = LMUReader.__new__(LMUReader)
    reader.available = True
    reader._last_read_ok = True  # was True; should flip to False
    api = MagicMock()
    api.playerTelemetry.return_value = None
    api.playerScoring.return_value = None
    reader.info = api
    reader._cbytestring = lambda b: b.decode('utf-8', 'ignore')
    assert reader.read() is None
    assert reader._last_read_ok is False


def test_read_swallows_field_exceptions():
    """If any field access raises, read() returns None rather than crashing."""
    from s1napse.readers.lmu import LMUReader
    reader = LMUReader.__new__(LMUReader)
    reader.available = True
    reader._last_read_ok = True
    api = MagicMock()
    bad_telem = MagicMock()
    # Accessing mLocalVel raises.
    type(bad_telem).mLocalVel = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("kaboom"))
    )
    api.playerTelemetry.return_value = bad_telem
    api.playerScoring.return_value = _make_fake_scoring()
    reader.info = api
    reader._cbytestring = lambda b: b.decode('utf-8', 'ignore')
    assert reader.read() is None
    assert reader._last_read_ok is False


def test_is_connected_caches_last_read_state():
    """is_connected() should reflect the latest read() outcome."""
    reader = _build_reader_with_fakes(_make_fake_telemetry(), _make_fake_scoring())
    assert reader.is_connected() is False  # nothing read yet
    reader.read()
    assert reader.is_connected() is True
