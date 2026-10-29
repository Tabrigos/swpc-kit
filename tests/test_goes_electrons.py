import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.models.goes import ElectronSample, GoesIntegralElectrons
from swpc_kit.parse.goes import (
    GOES_INTEGRAL_ELECTRONS_1_DAY_URL,
    parse_goes_integral_electrons,
)

FIXTURES = Path(__file__).parent / "fixtures"
ELECTRONS = "goes-electrons-1-day/2026-10-29.json"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def electron_record(**changes: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "time_tag": "2026-10-29T14:15:00Z",
        "satellite": 19,
        "flux": 1010.1483764648438,
        "energy": ">=2 MeV",
    }
    record.update(changes)
    return record


def dump(*records: dict[str, Any]) -> bytes:
    return json.dumps(list(records)).encode()


def test_electrons_fixture() -> None:
    electrons = parse_goes_integral_electrons(fixture(ELECTRONS))
    assert isinstance(electrons, GoesIntegralElectrons)
    assert len(electrons.values) == 46
    assert electrons.skipped == ()
    assert electrons.source_url == GOES_INTEGRAL_ELECTRONS_1_DAY_URL
    assert electrons.values[0] == ElectronSample(
        time=utc(2026, 10, 28, 14, 30),
        satellite=19,
        energy=">=2 MeV",
        threshold_mev=2.0,
        flux=1622.5244140625,
    )
    assert electrons.data_time == utc(2026, 10, 29, 14, 15)


def test_electrons_threshold_series_and_latest() -> None:
    electrons = parse_goes_integral_electrons(fixture(ELECTRONS))
    assert electrons.thresholds == (2.0,)
    series = electrons.series(2)
    assert len(series) == 46
    times = [v.time for v in series]
    assert times == sorted(set(times))
    latest = electrons.latest(2)
    assert latest is not None
    assert latest.time == utc(2026, 10, 29, 14, 15)
    assert latest.flux == 1010.1483764648438
    assert electrons.latest(10) is None


def test_electrons_are_sorted_oldest_first() -> None:
    late = electron_record(time_tag="2026-10-29T14:20:00Z", flux=2.0)
    early = electron_record(time_tag="2026-10-29T14:15:00Z", flux=1.0)
    electrons = parse_goes_integral_electrons(dump(late, early))
    assert [v.flux for v in electrons.values] == [1.0, 2.0]


def test_electrons_null_flux_becomes_none() -> None:
    sample = parse_goes_integral_electrons(dump(electron_record(flux=None))).values[0]
    assert sample.flux is None


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"energy": "2-4 MeV"}, "energy"),
        ({"energy": 2}, "energy"),
        ({"flux": "high"}, "flux"),
        ({"flux": 1e9}, "flux"),
        ({"satellite": "19a"}, "satellite"),
        ({"time_tag": None}, "time_tag"),
    ],
)
def test_electrons_inconsistent_values(changes: dict[str, Any], field: str) -> None:
    with pytest.raises(ParseError) as info:
        parse_goes_integral_electrons(dump(electron_record(**changes)))
    assert info.value.field == field
    assert info.value.index == 0


def test_electrons_errors() -> None:
    raw = fixture(ELECTRONS)
    with pytest.raises(SourceNotReady):
        parse_goes_integral_electrons(raw[:-2])
    with pytest.raises(UnexpectedContent):
        parse_goes_integral_electrons(b"<html></html>")
    with pytest.raises(UnexpectedContent):
        parse_goes_integral_electrons(dump({"time_tag": "2026-10-29T14:15:00Z"}))


def test_empty_electrons_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="empty"):
        GoesIntegralElectrons(values=(), source_url=GOES_INTEGRAL_ELECTRONS_1_DAY_URL)
