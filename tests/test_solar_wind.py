import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.models.solar_wind import (
    RtswMag1m,
    RtswMagSample,
    RtswSource,
    RtswWind1m,
    RtswWindSample,
)
from swpc_kit.parse.solar_wind import (
    RTSW_MAG_1M_URL,
    RTSW_WIND_1M_URL,
    parse_rtsw_mag_1m,
    parse_rtsw_wind_1m,
)

FIXTURES = Path(__file__).parent / "fixtures"
MAG = "rtsw-mag-1m/2026-10-15.json"
WIND = "rtsw-wind-1m/2026-10-15.json"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def utc(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0
) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def mag_record(**changes: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "time_tag": "2026-10-15T17:52:00",
        "active": True,
        "source": "SOLAR1",
        "range": None,
        "scale": None,
        "sensitivity": None,
        "manual_mode": False,
        "sample_size": 60,
        "bt": 4.75,
        "bx_gse": 3.11,
        "by_gse": -3.32,
        "bz_gse": 1.17,
        "theta_gse": 14.24,
        "phi_gse": 312.91,
        "bx_gsm": 3.11,
        "by_gsm": -2.74,
        "bz_gsm": 2.13,
        "theta_gsm": 26.79,
        "phi_gsm": 317.7,
        "max_telemetry_flag": 0,
        "max_data_flag": -9999,
        "overall_quality": 0,
    }
    record.update(changes)
    return record


def wind_record(**changes: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "time_tag": "2026-10-15T17:51:00",
        "active": True,
        "source": "SOLAR1",
        "proton_speed": 466.9,
        "proton_temperature": 103246,
        "proton_density": 4.18,
        "proton_vx_gse": -463.6,
        "proton_vy_gse": 6.8,
        "proton_vz_gse": -55.2,
        "proton_vx_gsm": -463.6,
        "proton_vy_gsm": -11.5,
        "proton_vz_gsm": -54.4,
        "proton_sample_size": 1,
        "alpha_speed": None,
        "alpha_temperature": None,
        "alpha_density": None,
        "alpha_vx_gse": None,
        "alpha_vy_gse": None,
        "alpha_vz_gse": None,
        "alpha_vx_gsm": None,
        "alpha_vy_gsm": None,
        "alpha_vz_gsm": None,
        "alpha_sample_size": None,
        "max_convergence_flag": 0,
        "max_data_flag": 0,
        "max_error_count_flag": 0,
        "max_processing_flag": 0,
        "max_range_flag": 0,
        "max_sample_count_flag": 0,
        "max_telemetry_flag": 0,
        "overall_quality": 0,
    }
    record.update(changes)
    return record


def dump(*records: dict[str, Any]) -> bytes:
    return json.dumps(list(records)).encode()


# --- Magnetic field: fixture ------------------------------------------------


def test_mag_fixture() -> None:
    mag = parse_rtsw_mag_1m(fixture(MAG))
    assert isinstance(mag, RtswMag1m)
    assert len(mag.values) == 223
    assert mag.source_url == RTSW_MAG_1M_URL
    assert mag.values[-1] == RtswMagSample(
        time=utc(2026, 10, 15, 17, 52),
        source="SOLAR1",
        active=True,
        bt=4.75,
        bx_gse=3.11,
        by_gse=-3.32,
        bz_gse=1.17,
        theta_gse=14.24,
        phi_gse=312.91,
        bx_gsm=3.11,
        by_gsm=-2.74,
        bz_gsm=2.13,
        theta_gsm=26.79,
        phi_gsm=317.7,
        manual_mode=False,
        sample_size=60,
        max_telemetry_flag=0,
        max_data_flag=-9999,
        overall_quality=0,
    )


def test_mag_values_are_oldest_first() -> None:
    # The source is newest first; the model is oldest first, like the indices.
    mag = parse_rtsw_mag_1m(fixture(MAG))
    times = [v.time for v in mag.values]
    assert times == sorted(times)
    assert times[0] == utc(2026, 10, 14, 17, 56)
    assert mag.data_time == utc(2026, 10, 15, 17, 52)


def test_mag_same_instant_keeps_file_order() -> None:
    mag = parse_rtsw_mag_1m(fixture(MAG))
    at_1751 = [v.source for v in mag.values if v.time == utc(2026, 10, 15, 17, 51)]
    assert at_1751 == ["SOLAR1", "ACE"]


def test_mag_sources_and_series() -> None:
    mag = parse_rtsw_mag_1m(fixture(MAG))
    assert mag.sources == ("ACE", "IMAP", "SOLAR1")
    counts = {s: len(mag.series(s)) for s in mag.sources}
    assert counts == {"ACE": 87, "IMAP": 22, "SOLAR1": 114}
    for source in mag.sources:
        series = mag.series(source)
        assert all(v.source == source for v in series)
        assert [v.time for v in series] == sorted(v.time for v in series)
    assert mag.series(RtswSource.ACE) == mag.series("ACE")
    assert mag.series("DSCOVR") == ()


def test_mag_active_series_has_one_record_per_active_instant() -> None:
    mag = parse_rtsw_mag_1m(fixture(MAG))
    active = mag.active_series()
    assert len(active) == 114
    assert all(v.active and v.source == RtswSource.SOLAR1 for v in active)
    times = [v.time for v in active]
    assert times == sorted(set(times))


def test_mag_active_at() -> None:
    mag = parse_rtsw_mag_1m(fixture(MAG))
    sample = mag.active_at(utc(2026, 10, 15, 17, 51))
    assert sample is not None
    assert (sample.source, sample.bt) == ("SOLAR1", 4.8)
    # A minute with ACE only: no active record.
    assert [v.source for v in mag.values if v.time == utc(2026, 10, 14, 21, 1)] == [
        "ACE"
    ]
    assert mag.active_at(utc(2026, 10, 14, 21, 1)) is None
    # IMAP times are not on the minute and IMAP is inactive.
    assert mag.active_at(utc(2026, 10, 15, 15, 53, 9)) is None
    assert mag.active_at(utc(2026, 10, 15, 15, 53)) is None
    assert mag.active_at(utc(2020, 1, 1)) is None


def test_mag_latest_active() -> None:
    mag = parse_rtsw_mag_1m(fixture(MAG))
    latest = mag.latest_active()
    assert latest is not None
    assert latest.time == utc(2026, 10, 15, 17, 52)
    assert latest.source == "SOLAR1"


def test_mag_imap_times_are_not_on_the_minute() -> None:
    mag = parse_rtsw_mag_1m(fixture(MAG))
    imap = mag.series("IMAP")
    assert imap[-1].time == utc(2026, 10, 15, 15, 53, 9)
    assert {v.time.second for v in imap} == {1, 9}
    assert not any(v.active for v in imap)
    assert {v.max_data_flag for v in imap} == {0}


def test_mag_fill_flag_is_kept_as_is() -> None:
    mag = parse_rtsw_mag_1m(fixture(MAG))
    assert {v.max_data_flag for v in mag.series("SOLAR1")} == {-9999}


# --- Magnetic field: hand-built cases ---------------------------------------


def test_mag_nulls_become_none() -> None:
    nulls = dict.fromkeys(
        [
            "bt",
            "bx_gse",
            "by_gse",
            "bz_gse",
            "theta_gse",
            "phi_gse",
            "bx_gsm",
            "by_gsm",
            "bz_gsm",
            "theta_gsm",
            "phi_gsm",
            "manual_mode",
            "sample_size",
            "max_telemetry_flag",
            "max_data_flag",
            "overall_quality",
        ]
    )
    mag = parse_rtsw_mag_1m(dump(mag_record(**nulls)))
    sample = mag.values[0]
    assert sample.bt is None
    assert sample.bz_gsm is None
    assert sample.manual_mode is None
    assert sample.max_data_flag is None
    assert sample.active is True


def test_mag_unknown_source_is_kept() -> None:
    mag = parse_rtsw_mag_1m(
        dump(
            mag_record(source="SOLAR2", time_tag="2026-10-15T17:53:00"),
            mag_record(source="SOLAR1", active=False),
        )
    )
    assert mag.sources == ("SOLAR1", "SOLAR2")
    assert [v.source for v in mag.active_series()] == ["SOLAR2"]


def test_mag_two_active_records_first_in_file_wins() -> None:
    mag = parse_rtsw_mag_1m(
        dump(mag_record(source="SOLAR1", bt=1.0), mag_record(source="ACE", bt=2.0))
    )
    sample = mag.active_at(utc(2026, 10, 15, 17, 52))
    assert sample is not None
    assert sample.source == "SOLAR1"
    assert len(mag.active_series()) == 1


def test_mag_without_active_records() -> None:
    mag = parse_rtsw_mag_1m(dump(mag_record(source="ACE", active=False)))
    assert mag.active_series() == ()
    assert mag.latest_active() is None
    assert mag.data_time == utc(2026, 10, 15, 17, 52)


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"bt": -1.0}, "bt"),
        ({"theta_gse": 90.5}, "theta_gse"),
        ({"theta_gsm": -91}, "theta_gsm"),
        ({"phi_gsm": 361}, "phi_gsm"),
        ({"phi_gse": -0.1}, "phi_gse"),
        ({"bz_gsm": "south"}, "bz_gsm"),
        ({"active": "true"}, "active"),
        ({"active": None}, "active"),
        ({"source": None}, "source"),
        ({"time_tag": "now"}, "time_tag"),
        ({"sample_size": -1}, "sample_size"),
    ],
)
def test_mag_inconsistent_values(changes: dict[str, Any], field: str) -> None:
    raw = dump(mag_record(time_tag="2026-10-15T17:53:00"), mag_record(**changes))
    with pytest.raises(ParseError) as info:
        parse_rtsw_mag_1m(raw)
    assert info.value.field == field
    assert info.value.index == 1


def test_mag_missing_field() -> None:
    record = mag_record()
    del record["bz_gsm"]
    with pytest.raises(ParseError, match="missing") as info:
        parse_rtsw_mag_1m(dump(record))
    assert info.value.field == "bz_gsm"


def test_mag_truncated_is_not_ready() -> None:
    raw = fixture(MAG)
    with pytest.raises(SourceNotReady):
        parse_rtsw_mag_1m(raw[: len(raw) // 3])


@pytest.mark.parametrize("raw", [b"", b"[]"])
def test_mag_empty_is_not_ready(raw: bytes) -> None:
    with pytest.raises(SourceNotReady):
        parse_rtsw_mag_1m(raw)


def test_mag_html_is_unexpected() -> None:
    with pytest.raises(UnexpectedContent):
        parse_rtsw_mag_1m(b"<!DOCTYPE html><html><body>Moved</body></html>")


def test_mag_accepts_str_and_source_url() -> None:
    raw = fixture(MAG)
    assert parse_rtsw_mag_1m(raw.decode()) == parse_rtsw_mag_1m(raw)
    mag = parse_rtsw_mag_1m(raw, source_url="https://example.org/mag.json")
    assert mag.source_url == "https://example.org/mag.json"


# --- Plasma (wind): fixture -------------------------------------------------


def test_wind_fixture() -> None:
    wind = parse_rtsw_wind_1m(fixture(WIND))
    assert isinstance(wind, RtswWind1m)
    assert len(wind.values) == 220
    assert wind.source_url == RTSW_WIND_1M_URL
    assert wind.data_time == utc(2026, 10, 15, 17, 51)
    latest = wind.latest_active()
    assert latest == RtswWindSample(
        time=utc(2026, 10, 15, 17, 51),
        source="SOLAR1",
        active=True,
        proton_speed=466.9,
        proton_temperature=103246.0,
        proton_density=4.18,
        proton_vx_gse=-463.6,
        proton_vy_gse=6.8,
        proton_vz_gse=-55.2,
        proton_vx_gsm=-463.6,
        proton_vy_gsm=-11.5,
        proton_vz_gsm=-54.4,
        proton_sample_size=1,
        alpha_speed=None,
        alpha_temperature=None,
        alpha_density=None,
        alpha_vx_gse=None,
        alpha_vy_gse=None,
        alpha_vz_gse=None,
        alpha_vx_gsm=None,
        alpha_vy_gsm=None,
        alpha_vz_gsm=None,
        alpha_sample_size=None,
        max_convergence_flag=0,
        max_data_flag=0,
        max_error_count_flag=0,
        max_processing_flag=0,
        max_range_flag=0,
        max_sample_count_flag=0,
        max_telemetry_flag=0,
        overall_quality=0,
    )


def test_wind_sources_and_active_series() -> None:
    wind = parse_rtsw_wind_1m(fixture(WIND))
    assert wind.sources == ("ACE", "IMAP", "SOLAR1")
    counts = {s: len(wind.series(s)) for s in wind.sources}
    assert counts == {"ACE": 99, "IMAP": 28, "SOLAR1": 93}
    active = wind.active_series()
    assert len(active) == 93
    assert all(v.source == "SOLAR1" for v in active)
    times = [v.time for v in wind.values]
    assert times == sorted(times)


def test_wind_minute_with_only_ace_has_no_active_record() -> None:
    wind = parse_rtsw_wind_1m(fixture(WIND))
    minute = utc(2026, 10, 15, 17, 46)
    assert [v.source for v in wind.values if v.time == minute] == ["ACE"]
    assert wind.active_at(minute) is None
    ace = [v for v in wind.series("ACE") if v.time == minute]
    assert ace[0].proton_speed is not None


def test_wind_ace_and_imap_have_no_velocity_components() -> None:
    wind = parse_rtsw_wind_1m(fixture(WIND))
    for source in ("ACE", "IMAP"):
        assert all(v.proton_vx_gse is None for v in wind.series(source))
        assert all(v.proton_speed is not None for v in wind.series(source))
    assert all(v.proton_vx_gse is not None for v in wind.series("SOLAR1"))
    assert all(v.alpha_density is None for v in wind.values)


def test_wind_imap_times_are_not_on_the_minute() -> None:
    wind = parse_rtsw_wind_1m(fixture(WIND))
    assert {v.time.second for v in wind.series("IMAP")} == {3}


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"proton_speed": -1}, "proton_speed"),
        ({"proton_density": -0.1}, "proton_density"),
        ({"proton_temperature": -5}, "proton_temperature"),
        ({"alpha_density": -1}, "alpha_density"),
        ({"max_range_flag": 0.5}, "max_range_flag"),
        ({"active": 1}, "active"),
    ],
)
def test_wind_inconsistent_values(changes: dict[str, Any], field: str) -> None:
    with pytest.raises(ParseError) as info:
        parse_rtsw_wind_1m(dump(wind_record(**changes)))
    assert info.value.field == field
    assert info.value.index == 0


def test_wind_nulls_become_none() -> None:
    sample = parse_rtsw_wind_1m(
        dump(wind_record(proton_speed=None, max_data_flag=None))
    ).values[0]
    assert sample.proton_speed is None
    assert sample.max_data_flag is None


def test_wind_truncated_and_html() -> None:
    raw = fixture(WIND)
    with pytest.raises(SourceNotReady):
        parse_rtsw_wind_1m(raw[:-1])
    with pytest.raises(UnexpectedContent):
        parse_rtsw_wind_1m(b"<html></html>")
    with pytest.raises(UnexpectedContent):
        parse_rtsw_wind_1m(b'{"error": "maintenance"}')


# --- Models -----------------------------------------------------------------


def test_models_are_frozen() -> None:
    mag = parse_rtsw_mag_1m(fixture(MAG))
    with pytest.raises(dataclasses.FrozenInstanceError):
        mag.source_url = "x"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        mag.values[0].bt = 1.0  # type: ignore[misc]


def test_empty_series_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="empty"):
        RtswMag1m(values=(), source_url=RTSW_MAG_1M_URL)
    with pytest.raises(ValueError, match="empty"):
        RtswWind1m(values=(), source_url=RTSW_WIND_1M_URL)


def test_naive_time_cannot_be_built() -> None:
    sample = parse_rtsw_mag_1m(fixture(MAG)).values[0]
    naive = datetime(2026, 10, 15)  # noqa: DTZ001
    with pytest.raises(ValueError, match="UTC"):
        dataclasses.replace(sample, time=naive)
