import dataclasses
from datetime import UTC, datetime
from pathlib import Path

import pytest

from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.models.indices import (
    DstValue,
    F107Value,
    Kp1mValue,
    KpForecastStatus,
    KpForecastValue,
    KpValue,
    NoaaScales,
    PlanetaryKIndex,
)
from swpc_kit.parse import (
    parse_f107_flux_30_day,
    parse_kyoto_dst,
    parse_noaa_scales,
    parse_planetary_k_index,
    parse_planetary_k_index_1m,
    parse_planetary_k_index_forecast,
)
from swpc_kit.parse.indices import (
    F107_FLUX_30_DAY_URL,
    KYOTO_DST_URL,
    NOAA_SCALES_URL,
    PLANETARY_K_INDEX_1M_URL,
    PLANETARY_K_INDEX_FORECAST_URL,
    PLANETARY_K_INDEX_URL,
)

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


# --- Kp 3 hours -------------------------------------------------------------


def test_kp_3h_new_format() -> None:
    kp = parse_planetary_k_index(fixture("kp-3h/2026-10-15.json"))
    assert len(kp.values) == 61
    assert kp.values[0] == KpValue(
        time=utc(2026, 10, 8, 0), kp=1.0, a_running=4, station_count=8
    )
    assert kp.values[-1] == KpValue(
        time=utc(2026, 10, 15, 12), kp=2.67, a_running=12, station_count=8
    )
    assert kp.data_time == utc(2026, 10, 15, 12)
    assert kp.source_url == PLANETARY_K_INDEX_URL


def test_kp_3h_old_format_gives_the_same_model() -> None:
    new = parse_planetary_k_index(fixture("kp-3h/2026-10-15.json"))
    old = parse_planetary_k_index(fixture("kp-3h/2026-10-15-built.json"))
    assert old == new


def test_kp_3h_official_old_sample() -> None:
    kp = parse_planetary_k_index(fixture("kp-3h/2022-09-22-sample.json"))
    assert len(kp.values) == 62
    assert kp.values[0] == KpValue(
        time=utc(2022, 9, 15, 0), kp=3.67, a_running=22, station_count=8
    )
    assert kp.data_time == utc(2022, 9, 22, 15)


def test_kp_3h_source_url_can_be_overridden() -> None:
    kp = parse_planetary_k_index(
        fixture("kp-3h/2026-10-15.json"), source_url="https://example.org/kp.json"
    )
    assert kp.source_url == "https://example.org/kp.json"


def test_kp_3h_accepts_str() -> None:
    raw = fixture("kp-3h/2026-10-15.json")
    assert parse_planetary_k_index(raw.decode()) == parse_planetary_k_index(raw)


@pytest.mark.parametrize(
    ("raw", "field", "index"),
    [
        (
            b'[{"time_tag":"2026-10-08T00:00:00","Kp":9.33,"a_running":4,'
            b'"station_count":8}]',
            "Kp",
            0,
        ),
        (
            b'[{"time_tag":"2026-10-08T00:00:00","Kp":-1,"a_running":4,'
            b'"station_count":8}]',
            "Kp",
            0,
        ),
        (
            b'[{"time_tag":"2026-10-08T00:00:00","a_running":4,"station_count":8}]',
            "Kp",
            0,
        ),
        (
            b'[["time_tag","Kp","a_running","station_count"],'
            b'["2026-10-08 00:00:00","1.00","4","8"],'
            b'["2026-10-08 03:00:00","x","4","8"]]',
            "Kp",
            2,
        ),
        (b'[{"time_tag":"bad","Kp":1,"a_running":4,"station_count":8}]', "time_tag", 0),
        (
            b'[{"time_tag":"2026-10-08T00:00:00","Kp":1,"a_running":-4,'
            b'"station_count":8}]',
            "a_running",
            0,
        ),
    ],
)
def test_kp_3h_inconsistent_values(raw: bytes, field: str, index: int) -> None:
    with pytest.raises(ParseError) as info:
        parse_planetary_k_index(raw)
    assert info.value.field == field
    assert info.value.index == index


def test_kp_3h_truncated_is_not_ready() -> None:
    raw = fixture("kp-3h/2026-10-15.json")
    with pytest.raises(SourceNotReady):
        parse_planetary_k_index(raw[: len(raw) // 2])


def test_kp_3h_html_is_unexpected() -> None:
    with pytest.raises(UnexpectedContent):
        parse_planetary_k_index(b"<html><body>Service moved</body></html>")


def test_models_are_frozen() -> None:
    kp = parse_planetary_k_index(fixture("kp-3h/2026-10-15.json"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        kp.source_url = "x"  # type: ignore[misc]
    assert isinstance(kp.values, tuple)


def test_empty_series_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="empty"):
        PlanetaryKIndex(values=(), source_url=PLANETARY_K_INDEX_URL)


def test_naive_time_cannot_be_built() -> None:
    naive = datetime(2026, 10, 8)  # noqa: DTZ001
    with pytest.raises(ValueError, match="UTC"):
        KpValue(time=naive, kp=1.0, a_running=4, station_count=8)


# --- Kp forecast ------------------------------------------------------------


def test_kp_forecast_new_format() -> None:
    fc = parse_planetary_k_index_forecast(fixture("kp-forecast/2026-10-15.json"))
    assert len(fc.values) == 81
    assert fc.values[0] == KpForecastValue(
        time=utc(2026, 10, 8, 0),
        kp=1.0,
        status=KpForecastStatus.OBSERVED,
        noaa_scale=None,
    )
    storm = [v for v in fc.values if v.noaa_scale is not None]
    assert [(v.time, v.noaa_scale) for v in storm] == [
        (utc(2026, 10, 10, 15), "G3"),
        (utc(2026, 10, 10, 18), "G3"),
        (utc(2026, 10, 10, 21), "G1"),
    ]
    statuses = [v.status for v in fc.values]
    assert statuses.count(KpForecastStatus.OBSERVED) == 61
    assert statuses.count(KpForecastStatus.ESTIMATED) == 3
    assert statuses.count(KpForecastStatus.PREDICTED) == 17
    assert fc.source_url == PLANETARY_K_INDEX_FORECAST_URL


def test_kp_forecast_data_time_is_the_last_observed_value() -> None:
    fc = parse_planetary_k_index_forecast(fixture("kp-forecast/2026-10-15.json"))
    # Estimated values can lie in the future (18:00 and 21:00 at 17:57 UTC).
    assert fc.data_time == utc(2026, 10, 15, 12)
    assert fc.values[-1].time == utc(2026, 10, 18, 0)


def test_kp_forecast_official_old_sample() -> None:
    fc = parse_planetary_k_index_forecast(fixture("kp-forecast/2022-09-22-sample.json"))
    assert len(fc.values) == 81
    assert fc.values[0] == KpForecastValue(
        time=utc(2022, 7, 27, 0),
        kp=2.67,
        status=KpForecastStatus.OBSERVED,
        noaa_scale=None,
    )
    assert fc.values[-1].status is KpForecastStatus.PREDICTED
    assert fc.data_time == utc(2022, 8, 3, 12)


def test_kp_forecast_without_observed_values_uses_the_first_time() -> None:
    fc = parse_planetary_k_index_forecast(
        b'[{"time_tag":"2026-10-16T00:00:00","kp":1.67,"observed":"predicted",'
        b'"noaa_scale":null},'
        b'{"time_tag":"2026-10-16T03:00:00","kp":2,"observed":"predicted",'
        b'"noaa_scale":null}]'
    )
    assert fc.data_time == utc(2026, 10, 16, 0)


def test_kp_forecast_unknown_status() -> None:
    with pytest.raises(ParseError, match="observed") as info:
        parse_planetary_k_index_forecast(
            b'[{"time_tag":"2026-10-16T00:00:00","kp":1.67,"observed":"guessed",'
            b'"noaa_scale":null}]'
        )
    assert info.value.field == "observed"


# --- Kp 1 minute ------------------------------------------------------------


def test_kp_1m() -> None:
    kp = parse_planetary_k_index_1m(fixture("kp-1m/2026-10-15.json"))
    assert len(kp.values) == 358
    assert kp.values[0] == Kp1mValue(
        time=utc(2026, 10, 15, 11, 56), kp_index=3, estimated_kp=3.0, kp="3Z"
    )
    assert kp.values[-1] == Kp1mValue(
        time=utc(2026, 10, 15, 17, 53), kp_index=3, estimated_kp=2.67, kp="3M"
    )
    assert kp.data_time == utc(2026, 10, 15, 17, 53)
    assert kp.source_url == PLANETARY_K_INDEX_1M_URL


def test_kp_1m_accepts_bom() -> None:
    raw = fixture("kp-1m/2026-10-15.json")
    assert parse_planetary_k_index_1m(b"\xef\xbb\xbf" + raw) == (
        parse_planetary_k_index_1m(raw)
    )


@pytest.mark.parametrize("label", ["3", "3X", "10Z", "", "3z"])
def test_kp_1m_rejects_bad_labels(label: str) -> None:
    raw = (
        '[{"time_tag":"2026-10-15T11:56:00","kp_index":3,"estimated_kp":3.00,'
        f'"kp":"{label}"}}]'
    )
    with pytest.raises(ParseError) as info:
        parse_planetary_k_index_1m(raw)
    assert info.value.field == "kp"


# --- Dst --------------------------------------------------------------------


def test_dst_new_and_old_formats() -> None:
    new = parse_kyoto_dst(fixture("dst/2026-10-15.json"))
    assert len(new.values) == 168
    assert new.values[0] == DstValue(time=utc(2026, 10, 8, 18), dst=-17)
    assert new.values[-1] == DstValue(time=utc(2026, 10, 15, 17), dst=-20)
    assert new.data_time == utc(2026, 10, 15, 17)
    assert new.source_url == KYOTO_DST_URL
    assert parse_kyoto_dst(fixture("dst/2026-10-15-built.json")) == new


def test_dst_rejects_fractional_values() -> None:
    with pytest.raises(ParseError) as info:
        parse_kyoto_dst(b'[{"time_tag":"2026-10-08T18:00:00","dst":-17.5}]')
    assert info.value.field == "dst"


# --- F10.7 ------------------------------------------------------------------


def test_f107_new_and_old_formats() -> None:
    new = parse_f107_flux_30_day(fixture("f107-30-day/2026-10-15.json"))
    assert len(new.values) == 30
    assert new.values[0] == F107Value(time=utc(2026, 9, 15, 20), flux=107.0)
    assert new.values[-1] == F107Value(time=utc(2026, 10, 14, 20), flux=123.0)
    assert new.data_time == utc(2026, 10, 14, 20)
    assert new.source_url == F107_FLUX_30_DAY_URL
    assert parse_f107_flux_30_day(fixture("f107-30-day/2026-10-15-built.json")) == new


def test_f107_rejects_negative_flux() -> None:
    with pytest.raises(ParseError) as info:
        parse_f107_flux_30_day(b'[{"time_tag":"2026-09-15T20:00:00","flux":-1}]')
    assert info.value.field == "flux"


# --- NOAA scales ------------------------------------------------------------


def test_noaa_scales() -> None:
    scales = parse_noaa_scales(fixture("noaa-scales/2026-10-15.json"))
    assert isinstance(scales, NoaaScales)
    assert [d.day for d in scales.days] == [-1, 0, 1, 2, 3]
    current = scales.day(0)
    assert current is not None
    assert current.time == utc(2026, 10, 15, 17, 54)
    assert current.r.scale == 0
    assert current.r.text == "none"
    assert current.r.minor_prob is None
    assert current.s.scale == 0
    assert current.s.prob is None
    assert current.g.scale == 0
    tomorrow = scales.day(2)
    assert tomorrow is not None
    assert tomorrow.time == utc(2026, 10, 16, 0)
    assert tomorrow.r.scale is None
    assert tomorrow.r.minor_prob == 20
    assert tomorrow.r.major_prob == 5
    assert tomorrow.s.prob == 1
    assert scales.day(7) is None
    assert scales.data_time == utc(2026, 10, 15, 17, 54)
    assert scales.source_url == NOAA_SCALES_URL


def _scales(day0: str) -> bytes:
    return (
        '{"0": {"DateStamp": "2026-10-15", "TimeStamp": "17:54:00", '
        '"R": {"Scale": "0", "Text": "none", "MinorProb": null, "MajorProb": null}, '
        '"S": {"Scale": "0", "Text": "none", "Prob": null}, '
        f'"G": {day0}}}}}'
    ).encode()


def test_noaa_scales_rejects_out_of_range_scale() -> None:
    with pytest.raises(ParseError) as info:
        parse_noaa_scales(_scales('{"Scale": "6", "Text": "none"}'))
    assert info.value.field == "0.G.Scale"


def test_noaa_scales_rejects_missing_group() -> None:
    with pytest.raises(ParseError) as info:
        parse_noaa_scales(_scales('{"Text": "none"}'))
    assert info.value.field == "0.G.Scale"


def test_noaa_scales_rejects_bad_day_key() -> None:
    with pytest.raises(ParseError, match="day"):
        parse_noaa_scales(b'{"today": {}}')


def test_noaa_scales_empty_object_is_not_ready() -> None:
    with pytest.raises(SourceNotReady):
        parse_noaa_scales(b"{}")


def test_noaa_scales_array_is_unexpected() -> None:
    with pytest.raises(UnexpectedContent):
        parse_noaa_scales(b"[]")


def test_noaa_scales_needs_an_observed_day() -> None:
    raw = _scales('{"Scale": "0", "Text": "none"}').replace(b'"0":', b'"1":')
    with pytest.raises(ParseError, match="observed"):
        parse_noaa_scales(raw)
