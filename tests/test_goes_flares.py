import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.models.goes import FlareClass, GoesFlare, GoesFlares, GoesLatestFlare
from swpc_kit.parse.goes import (
    GOES_XRAY_FLARE_LATEST_URL,
    GOES_XRAY_FLARES_7_DAY_URL,
    parse_goes_xray_flare_latest,
    parse_goes_xray_flares,
)

FIXTURES = Path(__file__).parent / "fixtures"
FLARES = "goes-flares-7-day/2026-10-29.json"
SHARED = "goes-flares-7-day/2026-08-28-shared.json"
LATEST = "goes-flares-latest/2026-10-29.json"

# The forms a flare in progress was seen with in a real `latest` file
# (2026-09-12, a partial sample shared by a user of the library).
IN_PROGRESS = {"end_time": "Unk", "end_class": None}


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def records(name: str) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = json.loads(fixture(name))
    return loaded


def dump(*items: dict[str, Any]) -> bytes:
    return json.dumps(list(items)).encode()


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def flare_record(**changes: Any) -> dict[str, Any]:
    record = dict(records(FLARES)[-1])
    record.update(changes)
    return record


def latest_record(**changes: Any) -> dict[str, Any]:
    (record,) = records(LATEST)
    record.update(changes)
    return record


# --- Flare class as written --------------------------------------------------


@pytest.mark.parametrize(
    ("text", "letter", "multiplier"),
    [("B3.2", "B", 3.2), ("C1.0", "C", 1.0), ("M6.9", "M", 6.9), ("X12.3", "X", 12.3)],
)
def test_flare_class_parse(text: str, letter: str, multiplier: float) -> None:
    assert FlareClass.parse(text) == FlareClass(letter, multiplier)
    assert str(FlareClass.parse(text)) == text


@pytest.mark.parametrize("text", ["", "M", "Z1.0", "m1.0", "M10.0", "M1.0x", " M1.0"])
def test_flare_class_parse_rejects_other_text(text: str) -> None:
    with pytest.raises(ValueError, match="flare class"):
        FlareClass.parse(text)


# --- The 7-day list ----------------------------------------------------------


def test_flares_fixture() -> None:
    flares = parse_goes_xray_flares(fixture(FLARES))
    assert isinstance(flares, GoesFlares)
    assert len(flares.values) == 54
    assert flares.skipped == ()
    assert flares.source_url == GOES_XRAY_FLARES_7_DAY_URL
    assert flares.values[0] == GoesFlare(
        begin_time=utc(2026, 10, 22, 17, 24),
        begin_class=FlareClass("B", 5.8),
        max_time=utc(2026, 10, 22, 17, 33),
        max_class=FlareClass("C", 1.4),
        max_flux=1.4643520671597798e-06,
        end_time=utc(2026, 10, 22, 17, 44),
        end_class=FlareClass("C", 1.0),
        satellite=18,
    )
    assert flares.data_time == utc(2026, 10, 28, 12, 38)
    latest = flares.latest()
    assert latest is not None
    assert latest.begin_time == utc(2026, 10, 28, 12, 38)
    assert not latest.ongoing


def test_flares_strongest() -> None:
    flares = parse_goes_xray_flares(fixture(SHARED))
    assert len(flares.values) == 41
    strongest = flares.strongest()
    assert strongest is not None
    assert strongest.max_class == FlareClass("M", 6.9)
    assert strongest.max_time == utc(2026, 8, 25, 10, 2)
    assert strongest.end_class == FlareClass("M", 3.3)


@pytest.mark.parametrize("name", [FLARES, SHARED])
def test_every_flare_of_the_fixtures_is_read_in_order(name: str) -> None:
    flares = parse_goes_xray_flares(fixture(name))
    assert flares.skipped == ()
    assert len(flares.values) == len(records(name))
    for flare in flares.values:
        assert flare.end_time is not None
        assert flare.begin_time <= flare.max_time <= flare.end_time
        assert FlareClass.from_flux(flare.max_flux) == flare.max_class
    begins = [f.begin_time for f in flares.values]
    assert begins == sorted(begins)


def test_flares_are_sorted_oldest_first() -> None:
    items = records(FLARES)
    flares = parse_goes_xray_flares(dump(*reversed(items)))
    assert flares.values == parse_goes_xray_flares(fixture(FLARES)).values


def test_no_flare_in_seven_days_is_an_empty_list() -> None:
    flares = parse_goes_xray_flares(b"[]")
    assert flares.values == ()
    assert flares.data_time is None
    assert flares.latest() is None
    assert flares.strongest() is None


def test_a_flare_in_progress_has_no_end() -> None:
    flares = parse_goes_xray_flares(dump(flare_record(**IN_PROGRESS)))
    (flare,) = flares.values
    assert flare.end_time is None
    assert flare.end_class is None
    assert flare.ongoing
    assert flare.max_class == FlareClass("B", 6.4)


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        # Empty forms not seen in a real file stay unreadable (D-025).
        ({"end_time": None}, "end_time"),
        ({"end_time": ""}, "end_time"),
        ({"end_class": "Unk"}, "end_class"),
        # Seen only as a pair: one alone says in progress, the other not.
        ({"end_time": "Unk"}, "end_time"),
        ({"end_class": None}, "end_class"),
        ({"max_time": "Unk"}, "max_time"),
        ({"max_class": None}, "max_class"),
        ({"begin_class": None}, "begin_class"),
        # Values that are wrong.
        ({"begin_class": "Q1.0"}, "begin_class"),
        ({"max_class": "M10.0"}, "max_class"),
        ({"max_xrlong": "x"}, "max_xrlong"),
        ({"max_xrlong": 0}, "max_xrlong"),
        ({"max_xrlong": 1.0}, "max_xrlong"),
        ({"satellite": "18a"}, "satellite"),
        ({"max_time": "2026-10-28T12:30:00Z"}, "max_time"),
        ({"end_time": "2026-10-28T12:50:00Z"}, "end_time"),
    ],
)
def test_unreadable_flares_are_skipped(changes: dict[str, Any], field: str) -> None:
    # The last flare: begin 12:38, peak 12:52, end 13:03.
    good = records(FLARES)
    broken = [dict(r) for r in good]
    broken[-1].update(changes)
    flares = parse_goes_xray_flares(dump(*broken))
    assert [(s.index, s.field) for s in flares.skipped] == [(len(good) - 1, field)]
    assert len(flares.values) == len(good) - 1


def test_flares_errors() -> None:
    raw = fixture(FLARES)
    with pytest.raises(SourceNotReady):
        parse_goes_xray_flares(raw[:-2])
    with pytest.raises(UnexpectedContent):
        parse_goes_xray_flares(b"<html></html>")
    with pytest.raises(UnexpectedContent):
        parse_goes_xray_flares(b'{"flares": []}')
    with pytest.raises(UnexpectedContent):
        parse_goes_xray_flares(dump({"time_tag": "2026-10-28T12:38:00Z"}))
    with pytest.raises(ParseError) as info:
        parse_goes_xray_flares(dump(flare_record(max_class="Q1.0")))
    assert info.value.field == "max_class"


# --- The latest flare --------------------------------------------------------


def test_latest_fixture() -> None:
    latest = parse_goes_xray_flare_latest(fixture(LATEST))
    assert latest == GoesLatestFlare(
        time=utc(2026, 10, 29, 14, 24),
        satellite=18,
        current_class=FlareClass("B", 2.1),
        flare=GoesFlare(
            begin_time=utc(2026, 10, 28, 12, 38),
            begin_class=FlareClass("B", 3.2),
            max_time=utc(2026, 10, 28, 12, 52),
            max_class=FlareClass("B", 6.4),
            max_flux=6.468203537224326e-07,
            end_time=utc(2026, 10, 28, 13, 3),
            end_class=FlareClass("B", 4.7),
            satellite=18,
        ),
        source_url=GOES_XRAY_FLARE_LATEST_URL,
    )
    assert latest.data_time == utc(2026, 10, 29, 14, 24)


def test_latest_flare_in_progress() -> None:
    latest = parse_goes_xray_flare_latest(dump(latest_record(**IN_PROGRESS)))
    assert latest.flare.ongoing
    assert latest.flare.end_time is None
    assert latest.current_class == FlareClass("B", 2.1)


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"current_class": None}, "current_class"),
        ({"current_class": "Q2"}, "current_class"),
        ({"time_tag": "Unk"}, "time_tag"),
        ({"end_time": None}, "end_time"),
    ],
)
def test_latest_unreadable_values(changes: dict[str, Any], field: str) -> None:
    with pytest.raises(ParseError) as info:
        parse_goes_xray_flare_latest(dump(latest_record(**changes)))
    assert info.value.field == field


def test_latest_errors() -> None:
    with pytest.raises(SourceNotReady):
        parse_goes_xray_flare_latest(fixture(LATEST)[:-2])
    with pytest.raises(SourceNotReady):
        parse_goes_xray_flare_latest(b"[]")
    with pytest.raises(UnexpectedContent, match="one record"):
        parse_goes_xray_flare_latest(dump(latest_record(), latest_record()))
    with pytest.raises(UnexpectedContent):
        parse_goes_xray_flare_latest(dump({"time_tag": "2026-10-29T14:24:00Z"}))


# --- Models ------------------------------------------------------------------


def test_naive_time_cannot_be_built() -> None:
    flare = parse_goes_xray_flares(fixture(FLARES)).values[0]
    naive = datetime(2026, 10, 22, 17, 24)  # noqa: DTZ001
    with pytest.raises(ValueError, match="UTC"):
        GoesFlare(
            begin_time=naive,
            begin_class=flare.begin_class,
            max_time=flare.max_time,
            max_class=flare.max_class,
            max_flux=flare.max_flux,
            end_time=flare.end_time,
            end_class=flare.end_class,
            satellite=18,
        )
