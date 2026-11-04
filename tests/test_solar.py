import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.models.solar import (
    SolarProbabilities,
    SolarProbability,
    SolarRegion,
    SolarRegions,
)
from swpc_kit.parse.solar import (
    SOLAR_PROBABILITIES_URL,
    SOLAR_REGIONS_URL,
    parse_solar_probabilities,
    parse_solar_regions,
)

FIXTURES = Path(__file__).parent / "fixtures"
PROBABILITIES = "solar-probabilities/2026-11-04.json"
SHARED_PROBABILITIES = "solar-probabilities/2026-08-28-shared.json"
REGIONS = "solar-regions/2026-11-04.json"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def records(name: str) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = json.loads(fixture(name))
    return loaded


def dump(*items: dict[str, Any]) -> bytes:
    return json.dumps(list(items)).encode()


# --- Probabilities -----------------------------------------------------------


def test_probabilities_fixture() -> None:
    probabilities = parse_solar_probabilities(fixture(PROBABILITIES))
    assert isinstance(probabilities, SolarProbabilities)
    assert len(probabilities.values) == 31
    assert probabilities.skipped == ()
    assert probabilities.source_url == SOLAR_PROBABILITIES_URL
    # The file is newest first; the model is oldest first.
    assert probabilities.values[0].day == date(2026, 10, 5)
    assert probabilities.latest() == probabilities.values[-1]
    assert probabilities.latest() == SolarProbability(
        day=date(2026, 11, 4),
        c_class=(80, 85, 85),
        m_class=(30, 35, 35),
        x_class=(10, 10, 10),
        proton_10mev=(5, 5, 5),
        polar_cap_absorption="green",
    )
    assert probabilities.data_time == datetime(2026, 11, 4, tzinfo=UTC)


def test_probabilities_shared_fixture() -> None:
    probabilities = parse_solar_probabilities(fixture(SHARED_PROBABILITIES))
    assert len(probabilities.values) == 31
    assert probabilities.skipped == ()
    assert [p.day for p in probabilities.values[:: len(probabilities.values) - 1]] == [
        date(2026, 7, 29),
        date(2026, 8, 28),
    ]
    latest = probabilities.latest()
    assert (latest.c_class, latest.m_class, latest.x_class) == (
        (75, 75, 75),
        (25, 25, 25),
        (5, 5, 5),
    )


def test_probabilities_are_sorted_oldest_first() -> None:
    items = records(PROBABILITIES)
    reversed_ = parse_solar_probabilities(dump(*reversed(items)))
    assert reversed_.values == parse_solar_probabilities(fixture(PROBABILITIES)).values


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        # A day is midnight without a zone, as SWPC writes it.
        ({"date": "2026-10-20T12:00:00"}, "date"),
        ({"date": "2026-10-20"}, "date"),
        ({"date": None}, "date"),
        ({"c_class_1_day": 101}, "c_class_1_day"),
        ({"m_class_2_day": -1}, "m_class_2_day"),
        ({"x_class_3_day": None}, "x_class_3_day"),
        ({"10mev_protons_1_day": "x"}, "10mev_protons_1_day"),
        ({"polar_cap_absorption": None}, "polar_cap_absorption"),
        ({"polar_cap_absorption": ""}, "polar_cap_absorption"),
    ],
)
def test_unreadable_probabilities_are_skipped(
    changes: dict[str, Any], field: str
) -> None:
    good = records(PROBABILITIES)
    broken = [dict(r) for r in good]
    broken[3].update(changes)
    probabilities = parse_solar_probabilities(dump(*broken))
    assert [(s.index, s.field) for s in probabilities.skipped] == [(3, field)]
    assert len(probabilities.values) == len(good) - 1


def test_a_repeated_day_skips_the_second_probability() -> None:
    good = records(PROBABILITIES)
    probabilities = parse_solar_probabilities(
        dump(*good, {**good[0], "c_class_1_day": 1})
    )
    assert len(probabilities.values) == len(good)
    assert probabilities.latest().c_class == (80, 85, 85)
    assert [(s.index, s.field) for s in probabilities.skipped] == [(len(good), "date")]
    assert "twice" in probabilities.skipped[0].reason


def test_probabilities_errors() -> None:
    raw = fixture(PROBABILITIES)
    with pytest.raises(SourceNotReady):
        parse_solar_probabilities(raw[:-2])
    with pytest.raises(SourceNotReady):
        parse_solar_probabilities(b"[]")
    with pytest.raises(UnexpectedContent):
        parse_solar_probabilities(b"<html></html>")
    with pytest.raises(UnexpectedContent):
        parse_solar_probabilities(dump({"time_tag": "2026-11-04T00:00:00"}))
    with pytest.raises(ParseError) as info:
        parse_solar_probabilities(dump({**records(PROBABILITIES)[0], "date": "x"}))
    assert info.value.field == "date"


def test_probability_needs_three_days() -> None:
    latest = parse_solar_probabilities(fixture(PROBABILITIES)).latest()
    with pytest.raises(ValueError, match="three"):
        replace(latest, m_class=(30, 35))  # type: ignore[arg-type]


# --- Regions -----------------------------------------------------------------


def test_regions_fixture() -> None:
    regions = parse_solar_regions(fixture(REGIONS))
    assert isinstance(regions, SolarRegions)
    assert len(regions.values) == 175
    assert regions.skipped == ()
    assert regions.source_url == SOLAR_REGIONS_URL
    keys = [(r.day, r.region) for r in regions.values]
    assert keys == sorted(keys)
    assert regions.values[0].day == date(2026, 10, 5)
    assert regions.data_time == datetime(2026, 11, 4, tzinfo=UTC)
    latest = regions.latest_day()
    assert [r.region for r in latest] == [4562, 4564, 4565, 4566, 4567]
    assert latest[3] == SolarRegion(
        day=date(2026, 11, 4),
        region=4566,
        latitude=-6,
        longitude=40,
        location="S06E40",
        carrington_longitude=153,
        status="f",
        spot_class="Fai",
        mag_class="BGD",
        area=120,
        extent=16,
        number_spots=12,
        c_xray_events=1,
        m_xray_events=0,
        x_xray_events=0,
        c_flare_probability=70,
        m_flare_probability=20,
        x_flare_probability=5,
        proton_probability=1,
        first_date=datetime(2026, 11, 2, 7, 20, 1, tzinfo=UTC),
    )


def test_regions_of_one_day() -> None:
    regions = parse_solar_regions(fixture(REGIONS))
    assert [r.region for r in regions.on(date(2026, 10, 25))] == [4560]
    assert regions.on(date(2026, 1, 1)) == ()
    assert regions.days() == tuple(sorted({r.day for r in regions.values}))
    assert len(regions.days()) == 31


def test_a_region_without_spots() -> None:
    regions = parse_solar_regions(fixture(REGIONS))
    # Written with null in every spot field, and without a status.
    (no_status,) = [r for r in regions.latest_day() if r.region == 4562]
    assert no_status.status is None
    assert no_status.longitude == -71
    assert (
        no_status.spot_class,
        no_status.mag_class,
        no_status.area,
        no_status.extent,
        no_status.number_spots,
    ) == (None, None, None, None, None)
    # Written with "" in the two classes.
    (empty,) = [r for r in regions.on(date(2026, 10, 30)) if r.region == 4562]
    assert (empty.spot_class, empty.mag_class, empty.area) == (None, None, None)
    assert empty.status == "f"
    spotless = [r for r in regions.values if r.spot_class is None]
    assert len(spotless) == 61  # 60 written with null, one with ""
    assert all(
        r.mag_class is None
        and r.area is None
        and r.extent is None
        and r.number_spots is None
        for r in spotless
    )


def test_a_location_beyond_the_west_limb_is_kept_as_written() -> None:
    regions = parse_solar_regions(fixture(REGIONS))
    (gone,) = [r for r in regions.on(date(2026, 10, 31)) if r.region == 4563]
    assert (gone.location, gone.latitude, gone.longitude) == ("S19W0*", -19, -108)
    assert gone.status == "d"


def test_regions_are_sorted_by_day_and_number() -> None:
    items = records(REGIONS)
    reversed_ = parse_solar_regions(dump(*reversed(items)))
    assert reversed_.values == parse_solar_regions(fixture(REGIONS)).values


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        # Only the empty forms seen in a real file are read as absent.
        ({"area": ""}, "area"),
        ({"number_spots": "Unk"}, "number_spots"),
        ({"spot_class": 0}, "spot_class"),
        ({"status": ""}, "status"),
        ({"location": ""}, "location"),
        # A region with spots has all five fields (D-028): one empty is wrong.
        ({"spot_class": None}, "spot_class"),
        ({"mag_class": ""}, "mag_class"),
        ({"area": None}, "area"),
        ({"extent": None}, "extent"),
        ({"number_spots": None}, "number_spots"),
        # Values that are wrong.
        ({"observed_date": "2026-11-4"}, "observed_date"),
        ({"observed_date": "2026-11-04T00:00:00"}, "observed_date"),
        # ISO forms that date.fromisoformat reads, but SWPC does not write.
        ({"observed_date": "20261104"}, "observed_date"),
        ({"observed_date": "2026-W45-3"}, "observed_date"),
        ({"observed_date": "2026-13-04"}, "observed_date"),
        ({"region": None}, "region"),
        ({"region": -1}, "region"),
        ({"latitude": 91}, "latitude"),
        ({"longitude": -181}, "longitude"),
        ({"longitude": 181}, "longitude"),
        ({"carrington_longitude": -1}, "carrington_longitude"),
        ({"carrington_longitude": 361}, "carrington_longitude"),
        ({"location": None}, "location"),
        ({"area": -1}, "area"),
        ({"extent": -1}, "extent"),
        ({"number_spots": -1}, "number_spots"),
        ({"c_flare_probability": 101}, "c_flare_probability"),
        ({"proton_probability": -1}, "proton_probability"),
        ({"c_xray_events": -1}, "c_xray_events"),
        ({"m_xray_events": -1}, "m_xray_events"),
        ({"x_xray_events": -1}, "x_xray_events"),
        ({"first_date": "Unk"}, "first_date"),
    ],
)
def test_unreadable_regions_are_skipped(changes: dict[str, Any], field: str) -> None:
    # Record 0 is region 4566 on 11-04, with spots.
    good = records(REGIONS)
    broken = [dict(r) for r in good]
    broken[0].update(changes)
    regions = parse_solar_regions(dump(*broken))
    assert [(s.index, s.field) for s in regions.skipped] == [(0, field)]
    assert len(regions.values) == len(good) - 1


@pytest.mark.parametrize(
    "changes",
    [
        # Forms never seen: with any of them the region is read as one with
        # spots, and its first empty field is the error (D-028).
        {"area": ""},
        {"extent": ""},
        {"number_spots": ""},
        {"mag_class": "Unk"},
        {"area": 0},
    ],
)
def test_a_region_without_spots_needs_all_five_fields_empty(
    changes: dict[str, Any],
) -> None:
    good = records(REGIONS)
    index = next(i for i, r in enumerate(good) if r["spot_class"] is None)
    broken = [dict(r) for r in good]
    broken[index].update(changes)
    regions = parse_solar_regions(dump(*broken))
    assert [(s.index, s.field) for s in regions.skipped] == [(index, "spot_class")]


def test_skipped_regions_are_in_source_order() -> None:
    good = records(REGIONS)
    broken = [dict(r) for r in good]
    broken[5]["latitude"] = 91
    broken[3] = dict(good[2])  # the same region and day as record 2
    regions = parse_solar_regions(dump(*broken))
    assert [s.index for s in regions.skipped] == [3, 5]


def test_a_repeated_region_of_a_day_skips_the_second() -> None:
    good = records(REGIONS)
    regions = parse_solar_regions(dump(*good, {**good[0], "area": 999}))
    assert len(regions.values) == len(good)
    assert regions.latest_day()[3].area == 120
    assert [(s.index, s.field) for s in regions.skipped] == [(len(good), "region")]
    assert "twice" in regions.skipped[0].reason


def test_regions_errors() -> None:
    raw = fixture(REGIONS)
    with pytest.raises(SourceNotReady):
        parse_solar_regions(raw[:-2])
    with pytest.raises(SourceNotReady):
        parse_solar_regions(b"[]")
    with pytest.raises(UnexpectedContent):
        parse_solar_regions(b"<html></html>")
    with pytest.raises(UnexpectedContent):
        parse_solar_regions(dump({"observed_date": "2026-11-04"}))


def test_naive_time_cannot_be_built() -> None:
    region = parse_solar_regions(fixture(REGIONS)).values[0]
    with pytest.raises(ValueError, match="UTC"):
        replace(region, first_date=datetime(2026, 11, 2, 7, 20, 1))  # noqa: DTZ001
