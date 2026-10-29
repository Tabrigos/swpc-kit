"""Plain data from the models: ``to_dict`` for JSON, ``to_records`` for tables."""

import csv
import io
import json
from dataclasses import fields, is_dataclass
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

import pytest

from swpc_kit.client import PRODUCTS, Client
from swpc_kit.export import to_dict, to_records
from swpc_kit.models import (
    Alerts,
    Grid,
    KpValue,
    NoaaScales,
    PlanetaryKIndex,
    SkippedRecord,
    ThreeDayForecast,
    TwentySevenDayOutlook,
)

NAMES = [p.name for p in PRODUCTS]


_MODELS: dict[str, Any] = {}


@pytest.fixture
def models(swpc_from_fixtures: None) -> dict[str, Any]:
    # Parsed once: the models are frozen, and parsing every fixture for each
    # test would take most of the time of this file.
    if not _MODELS:
        with Client() as client:
            _MODELS.update({p.name: client.fetch(p) for p in PRODUCTS})
    return _MODELS


def _walk(value: Any) -> list[Any]:
    """Every leaf of a JSON-like value."""
    if isinstance(value, dict):
        return [leaf for item in value.values() for leaf in _walk(item)]
    if isinstance(value, list):
        return [leaf for item in value for leaf in _walk(item)]
    return [value]


# --- to_dict -----------------------------------------------------------------


@pytest.mark.parametrize("name", NAMES)
def test_to_dict_is_ready_for_json(models: dict[str, Any], name: str) -> None:
    model = models[name]
    data = to_dict(model)
    assert list(data) == [f.name for f in fields(model)]
    text = json.dumps(data, allow_nan=False)
    assert json.loads(text) == data
    for leaf in _walk(data):
        assert leaf is None or type(leaf) in (str, int, float, bool), (name, leaf)


def test_to_dict_writes_times_in_iso_8601_with_z() -> None:
    kp = PlanetaryKIndex(
        values=(KpValue(datetime(2026, 10, 15, 12, tzinfo=UTC), 2.67, 7, 8),),
        source_url="https://example.org/kp.json",
    )
    assert to_dict(kp) == {
        "values": [
            {
                "time": "2026-10-15T12:00:00Z",
                "kp": 2.67,
                "a_running": 7,
                "station_count": 8,
            }
        ],
        "source_url": "https://example.org/kp.json",
        "skipped": [],
    }


def test_to_dict_writes_dates_enums_and_nested_models(models: dict[str, Any]) -> None:
    outlook = to_dict(models["twenty_seven_day_outlook"])
    first = models["twenty_seven_day_outlook"].days[0]
    assert outlook["days"][0]["day"] == first.day.isoformat()
    forecast = models["planetary_k_index_forecast"]
    assert to_dict(forecast)["values"][0]["status"] == forecast.values[0].status.value
    alerts = to_dict(models["alerts"])
    scaled = next(m for m in models["alerts"].messages if m.noaa_scale is not None)
    index = models["alerts"].messages.index(scaled)
    assert alerts["messages"][index]["noaa_scale"] == {
        "category": scaled.noaa_scale.category.value,
        "level": scaled.noaa_scale.level,
        "label": scaled.noaa_scale.label,
    }


def test_to_dict_keeps_the_skipped_records() -> None:
    kp = PlanetaryKIndex(
        values=(KpValue(datetime(2026, 10, 15, 12, tzinfo=UTC), 2.67, 7, 8),),
        source_url="https://example.org/kp.json",
        skipped=(SkippedRecord(3, "Kp", "Kp 12 out of range"),),
    )
    assert to_dict(kp)["skipped"] == [
        {"index": 3, "field": "Kp", "reason": "Kp 12 out of range"}
    ]


@pytest.mark.parametrize("value", [None, 3, "kp", [1, 2], {"kp": 1}, KpValue])
def test_to_dict_wants_a_model(value: object) -> None:
    with pytest.raises(TypeError, match="model"):
        to_dict(value)


# --- to_records ---------------------------------------------------------------

# The rows each product gives: the attribute that holds them.
ROWS = {
    "alerts": "messages",
    "noaa_scales": "days",
    "twenty_seven_day_outlook": "days",
    "three_day_forecast": "kp",
    "geomagnetic_forecast": "kp",
}
SCALARS = (str, int, float, bool, datetime, date)


@pytest.mark.parametrize("name", NAMES)
def test_to_records_gives_one_flat_row_per_record(
    models: dict[str, Any], name: str
) -> None:
    model = models[name]
    records = to_records(model)
    if hasattr(model, "grid"):
        assert len(records) == len(model.grid.latitudes) * len(model.grid.longitudes)
    elif name == "goes_xray_flare_latest":
        assert len(records) == 1  # a product of one record is its own row
    else:
        assert len(records) == len(getattr(model, ROWS.get(name, "values")))
    assert records
    columns = list(records[0])
    for record in records:
        assert list(record) == columns
        for value in record.values():
            assert value is None or isinstance(value, (*SCALARS, list)), (name, value)
            assert not isinstance(value, Enum), (name, value)


def test_to_records_keeps_times_as_utc_datetimes(models: dict[str, Any]) -> None:
    kp = models["planetary_k_index"]
    records = to_records(kp)
    assert records[-1] == {
        "time": kp.values[-1].time,
        "kp": kp.values[-1].kp,
        "a_running": kp.values[-1].a_running,
        "station_count": kp.values[-1].station_count,
    }
    assert records[-1]["time"].tzinfo is UTC


def test_to_records_flattens_nested_models(models: dict[str, Any]) -> None:
    scales: NoaaScales = models["noaa_scales"]
    record = to_records(scales)[0]
    day = scales.days[0]
    assert record["g_scale"] == day.g.scale
    assert record["r_minor_prob"] == day.r.minor_prob
    assert record["s_prob"] == day.s.prob
    assert "g" not in record


def test_to_records_of_the_flares_splits_each_class(models: dict[str, Any]) -> None:
    flares = models["goes_xray_flares"]
    first = to_records(flares)[0]
    assert (first["max_class_letter"], first["max_class_multiplier"]) == ("C", 1.4)
    (latest,) = to_records(models["goes_xray_flare_latest"])
    assert latest["current_class_letter"] == "B"
    assert latest["flare_max_class_multiplier"] == 6.4
    assert latest["flare_end_time"] == datetime(2026, 10, 28, 13, 3, tzinfo=UTC)
    assert latest["source_url"].endswith("xray-flares-latest.json")


def test_to_records_flattens_an_absent_nested_model_to_none(
    models: dict[str, Any],
) -> None:
    alerts: Alerts = models["alerts"]
    records = to_records(alerts)
    plain = next(i for i, m in enumerate(alerts.messages) if m.noaa_scale is None)
    scaled = next(i for i, m in enumerate(alerts.messages) if m.noaa_scale)
    scale = alerts.messages[scaled].noaa_scale
    assert scale is not None
    assert records[plain]["noaa_scale_level"] is None
    assert records[scaled]["noaa_scale_level"] == scale.level
    assert records[scaled]["noaa_scale_category"] == scale.category.value
    assert records[scaled]["fields"] == [
        {"name": f.name, "value": f.value} for f in alerts.messages[scaled].fields
    ]


def test_to_records_of_a_grid_gives_its_cells_as_delivered(
    models: dict[str, Any],
) -> None:
    oval = models["ovation_aurora"]
    records = to_records(oval)
    assert records[0] == dict(
        zip(("latitude", "longitude", "value"), next(oval.grid.cells()), strict=True)
    )
    assert to_records(oval.grid) == records
    assert max(r["longitude"] for r in records) == 359


def test_to_records_takes_a_sequence_of_records(models: dict[str, Any]) -> None:
    wind = models["rtsw_wind_1m"]
    active = wind.active_series()
    records = to_records(active)
    assert len(records) == len(active)
    assert all(r["active"] for r in records)
    assert to_records(()) == []
    skipped = (SkippedRecord(1, None, "expected an object"),)
    assert to_records(skipped) == [
        {"index": 1, "field": None, "reason": "expected an object"}
    ]


def test_to_records_of_the_bulletins_gives_their_kp_periods(
    models: dict[str, Any],
) -> None:
    forecast: ThreeDayForecast = models["three_day_forecast"]
    assert to_records(forecast) == to_records(forecast.kp)
    outlook: TwentySevenDayOutlook = models["twenty_seven_day_outlook"]
    assert to_records(outlook)[0]["day"] == outlook.days[0].day


def test_to_records_writes_to_csv(models: dict[str, Any]) -> None:
    records = to_records(models["kyoto_dst"])
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(records[0]))
    writer.writeheader()
    writer.writerows(records)
    assert out.getvalue().splitlines()[0] == "time,dst"


@pytest.mark.parametrize("value", [None, 3, "kp", [1, 2], KpValue, {"a": 1}])
def test_to_records_wants_a_product_or_records(value: object) -> None:
    with pytest.raises(TypeError, match="to_records"):
        to_records(value)


def test_to_records_wants_records_of_one_kind(models: dict[str, Any]) -> None:
    kp = models["planetary_k_index"].values[0]
    dst = models["kyoto_dst"].values[0]
    with pytest.raises(TypeError, match="one kind"):
        to_records([kp, dst])


def test_grid_is_a_model_for_both() -> None:
    grid = Grid((0.0,), (0.0,), 1.0, 1.0, ((5.0,),), "aurora", "%")
    assert is_dataclass(grid)
    assert to_dict(grid)["values"] == [[5.0]]
    assert to_records(grid) == [{"latitude": 0.0, "longitude": 0.0, "value": 5.0}]
