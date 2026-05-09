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
