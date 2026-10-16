import dataclasses
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.models.grids import (
    DrapFrequencies,
    Grid,
    GridProduct,
    OvationAurora,
    wrap_longitude,
)
from swpc_kit.parse.grids import (
    DRAP_GLOBAL_FREQUENCIES_URL,
    OVATION_AURORA_URL,
    parse_drap_global_frequencies,
    parse_ovation_aurora,
)

FIXTURES = Path(__file__).parent / "fixtures"
OVATION = FIXTURES / "ovation-aurora" / "2026-10-15.json"
DRAP = FIXTURES / "drap" / "2026-10-15.txt"
FIXTURE_LONGITUDES = (0, 1, *range(30, 331, 30), 358, 359)
FIELDS = {
    "observation_time": "Observation Time",
    "forecast_time": "Forecast Time",
    "data_format": "Data Format",
    "coordinates": "coordinates",
}


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


# --- Synthetic OVATION content ----------------------------------------------


def aurora(lon: int, lat: int) -> int:
    """A made-up but recognisable value for each grid point."""
    return (lon * 7 + (lat + 90) * 3) % 41


def full_coordinates() -> list[list[Any]]:
    return [
        [lon, lat, aurora(lon, lat)] for lon in range(360) for lat in range(-90, 91)
    ]


def ovation_json(points: list[list[Any]] | None = None, **overrides: Any) -> bytes:
    document: dict[str, Any] = {
        "Observation Time": "2026-10-15T17:48:00Z",
        "Forecast Time": "2026-10-15T18:47:00Z",
        "Data Format": "[Longitude, Latitude, Aurora]",
        "coordinates": full_coordinates() if points is None else points,
        "type": "MultiPoint",
    }
    for key, value in overrides.items():
        name = FIELDS[key]
        if value is None:
            del document[name]
        else:
            document[name] = value
    return json.dumps(document).encode()


# --- Grid model --------------------------------------------------------------


def small_grid(**changes: Any) -> Grid:
    fields: dict[str, Any] = {
        "latitudes": (-1.0, 1.0),
        "longitudes": (0.0, 4.0, 8.0),
        "latitude_step": 2.0,
        "longitude_step": 4.0,
        "values": ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0)),
        "quantity": "q",
        "units": "u",
    }
    fields.update(changes)
    return Grid(**fields)


def test_grid_lookup_and_cells() -> None:
    grid = small_grid()
    assert grid.shape == (2, 3)
    assert grid.is_contiguous
    assert grid.value_at(1, 4) == 5.0
    assert list(grid.cells())[:2] == [(-1.0, 0.0, 1.0), (-1.0, 4.0, 2.0)]
    with pytest.raises(KeyError):
        grid.value_at(0, 4)


@pytest.mark.parametrize(
    "changes",
    [
        {"latitudes": ()},
        {"latitudes": (1.0, -1.0)},
        {"longitudes": (0.0, 4.0, 9.0)},
        {"latitude_step": 0.0},
        {"latitudes": (89.0, 91.0)},
        {"longitudes": (-184.0, -180.0, -176.0)},
        {"values": ((1.0, 2.0, 3.0),)},
        {"values": ((1.0, 2.0), (4.0, 5.0))},
        {"values": ((1.0, 2.0, float("nan")), (4.0, 5.0, 6.0))},
    ],
)
def test_grid_rejects_inconsistent_shapes(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        small_grid(**changes)


def test_grid_with_gaps_is_not_contiguous() -> None:
    grid = small_grid(longitudes=(0.0, 8.0, 12.0))
    assert not grid.is_contiguous


@pytest.mark.parametrize(
    ("longitude", "wrapped"),
    [(0, 0), (179, 179), (180, -180), (359, -1), (-180, -180), (-1, -1)],
)
def test_wrap_longitude(longitude: float, wrapped: float) -> None:
    assert wrap_longitude(longitude) == wrapped


def test_grid_wrapped_reorders_columns() -> None:
    grid = small_grid(
        longitudes=(0.0, 180.0, 270.0),
        longitude_step=90.0,
        values=((1.0, 2.0, 3.0), (4.0, 5.0, 6.0)),
    )
    wrapped = grid.wrapped()
    assert wrapped.longitudes == (-180.0, -90.0, 0.0)
    assert wrapped.values == ((2.0, 3.0, 1.0), (5.0, 6.0, 4.0))
    assert wrapped.wrapped() is wrapped
    assert wrapped.value_at(1, 180) == grid.value_at(1, -180) == 5.0


def test_products_follow_the_grid_product_protocol() -> None:
    products: list[GridProduct] = [
        parse_ovation_aurora(ovation_json()),
        parse_drap_global_frequencies(DRAP.read_bytes()),
    ]
    for product in products:
        assert product.data_time in product.times.values()


def test_models_are_frozen() -> None:
    oval = parse_ovation_aurora(OVATION.read_bytes(), partial=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        oval.source_url = "x"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        oval.grid.units = "x"  # type: ignore[misc]


def test_naive_time_cannot_be_built() -> None:
    grid = small_grid()
    naive = datetime(2026, 10, 15)  # noqa: DTZ001
    with pytest.raises(ValueError, match="UTC"):
        OvationAurora(
            grid=grid, observation_time=naive, forecast_time=naive, source_url="x"
        )
    with pytest.raises(ValueError, match="UTC"):
        DrapFrequencies(
            grid=grid,
            valid_at=naive,
            estimated_recovery_time=None,
            xray_message=None,
            xray_warning=None,
            proton_message=None,
            proton_warning=None,
            source_url="x",
        )


# --- OVATION: recorded (reduced) fixture ------------------------------------


def test_ovation_reduced_fixture() -> None:
    oval = parse_ovation_aurora(OVATION.read_bytes(), partial=True)
    grid = oval.grid
    assert grid.shape == (181, 15)
    assert grid.longitudes == tuple(float(x) for x in FIXTURE_LONGITUDES)
    assert grid.latitudes == tuple(float(x) for x in range(-90, 91))
    assert (grid.latitude_step, grid.longitude_step) == (1.0, 1.0)
    assert not grid.is_contiguous
    assert grid.quantity == "aurora"
    assert grid.units == "%"
    assert grid.value_at(-90, 0) == 7
    assert grid.value_at(-89, 0) == 0
    assert grid.value_at(-88, 0) == 10
    assert grid.value_at(90, 359) == 0
    assert max(v for _, _, v in grid.cells()) == 33
    assert oval.observation_time == utc(2026, 10, 15, 17, 48)
    assert oval.forecast_time == utc(2026, 10, 15, 18, 47)
    assert oval.data_time == oval.observation_time
    assert oval.times == {
        "observation_time": utc(2026, 10, 15, 17, 48),
        "forecast_time": utc(2026, 10, 15, 18, 47),
    }
    assert oval.source_url == OVATION_AURORA_URL


def test_ovation_reduced_fixture_needs_partial() -> None:
    with pytest.raises(ParseError, match="longitudes missing") as info:
        parse_ovation_aurora(OVATION.read_bytes())
    assert info.value.field == "coordinates"


def test_ovation_accepts_str_and_source_url() -> None:
    raw = OVATION.read_bytes()
    oval = parse_ovation_aurora(
        raw.decode(), partial=True, source_url="https://example.org/o.json"
    )
    assert oval.source_url == "https://example.org/o.json"
    assert oval.grid == parse_ovation_aurora(raw, partial=True).grid


# --- OVATION: synthetic complete grid ---------------------------------------


def test_ovation_complete_grid() -> None:
    oval = parse_ovation_aurora(ovation_json())
    grid = oval.grid
    assert grid.shape == (181, 360)
    assert grid.is_contiguous
    assert grid.longitudes == tuple(float(x) for x in range(360))
    for lon, lat in [(0, -90), (0, 90), (359, -90), (359, 90), (123, 45)]:
        assert grid.value_at(lat, lon) == aurora(lon, lat)
    assert grid.value_at(45, -1) == aurora(359, 45)


def test_ovation_complete_grid_in_any_order() -> None:
    coordinates = full_coordinates()
    random.Random(6).shuffle(coordinates)
    assert parse_ovation_aurora(ovation_json(coordinates)) == parse_ovation_aurora(
        ovation_json()
    )


def test_ovation_partial_also_accepts_a_complete_grid() -> None:
    raw = ovation_json()
    assert parse_ovation_aurora(raw, partial=True) == parse_ovation_aurora(raw)


def test_ovation_accepts_fractional_values() -> None:
    coordinates = full_coordinates()
    coordinates[0] = [0, -90, 12.5]
    assert parse_ovation_aurora(ovation_json(coordinates)).grid.value_at(-90, 0) == 12.5


# --- OVATION: errors ---------------------------------------------------------


def _with(index: int, item: Any) -> list[list[Any]]:
    coordinates = full_coordinates()
    coordinates[index] = item
    return coordinates


@pytest.mark.parametrize(
    ("coordinates", "field", "index"),
    [
        (_with(5, [0, -90, 3]), "coordinates", 5),  # duplicate point
        (_with(5, [360, -85, 3]), "Longitude", 5),
        (_with(5, [-1, -85, 3]), "Longitude", 5),
        (_with(5, [0, 91, 3]), "Latitude", 5),
        (_with(5, [0.5, -85, 3]), "Longitude", 5),
        (_with(5, [True, -85, 3]), "Longitude", 5),
        (_with(5, [0, "-85", 3]), "Latitude", 5),
        (_with(5, [0, -85, -1]), "Aurora", 5),
        (_with(5, [0, -85, "x"]), "Aurora", 5),
        (_with(5, [0, -85, None]), "Aurora", 5),
        (_with(5, [0, -85]), "coordinates", 5),
        (_with(5, [0, -85, 3, 4]), "coordinates", 5),
        (_with(5, {"lon": 0}), "coordinates", 5),
    ],
)
def test_ovation_inconsistent_points(
    coordinates: list[list[Any]], field: str, index: int
) -> None:
    with pytest.raises(ParseError) as info:
        parse_ovation_aurora(ovation_json(coordinates), partial=True)
    assert info.value.field == field
    assert info.value.index == index


def test_ovation_missing_point() -> None:
    coordinates = [c for c in full_coordinates() if c[:2] != [30, 12]]
    for partial in (False, True):
        with pytest.raises(ParseError, match=r"longitude 30 .* latitude 12") as info:
            parse_ovation_aurora(ovation_json(coordinates), partial=partial)
        assert info.value.field == "coordinates"
        assert info.value.index is None


def test_ovation_missing_longitude() -> None:
    coordinates = [c for c in full_coordinates() if c[0] != 200]
    with pytest.raises(ParseError, match=r"1 longitudes missing.*200"):
        parse_ovation_aurora(ovation_json(coordinates))
    oval = parse_ovation_aurora(ovation_json(coordinates), partial=True)
    assert oval.grid.shape == (181, 359)


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"observation_time": None}, "Observation Time"),
        ({"observation_time": "yesterday"}, "Observation Time"),
        ({"observation_time": 1760550480}, "Observation Time"),
        ({"forecast_time": None}, "Forecast Time"),
        ({"forecast_time": "2026-10-15"}, "Forecast Time"),
        ({"data_format": None}, "Data Format"),
        ({"coordinates": None}, "coordinates"),
        ({"coordinates": {"0": [0, 0, 0]}}, "coordinates"),
    ],
)
def test_ovation_inconsistent_fields(overrides: dict[str, Any], field: str) -> None:
    with pytest.raises(ParseError) as info:
        parse_ovation_aurora(ovation_json(**overrides))
    assert info.value.field == field


def test_ovation_data_format_may_differ_in_spacing() -> None:
    raw = ovation_json(data_format="[longitude,latitude,  aurora]")
    assert parse_ovation_aurora(raw) == parse_ovation_aurora(ovation_json())


def test_ovation_unknown_data_format_is_unexpected() -> None:
    with pytest.raises(UnexpectedContent, match="Data Format"):
        parse_ovation_aurora(ovation_json(data_format="[Latitude, Longitude, Aurora]"))


def test_ovation_empty_coordinates_is_not_ready() -> None:
    with pytest.raises(SourceNotReady):
        parse_ovation_aurora(ovation_json([]))


def test_ovation_truncated_is_not_ready() -> None:
    raw = OVATION.read_bytes()
    with pytest.raises(SourceNotReady):
        parse_ovation_aurora(raw[: len(raw) // 2], partial=True)
    with pytest.raises(SourceNotReady):
        parse_ovation_aurora(b"")


@pytest.mark.parametrize(
    "raw",
    [b"<!DOCTYPE html><html><body>moved</body></html>", b"[[0, 0, 0]]", b"42"],
)
def test_ovation_other_content_is_unexpected(raw: bytes) -> None:
    with pytest.raises(UnexpectedContent):
        parse_ovation_aurora(raw)


# --- D-RAP -------------------------------------------------------------------


def drap_text() -> str:
    return DRAP.read_text("utf-8")


def drap_lines() -> list[str]:
    return drap_text().split("\n")


def test_drap_fixture() -> None:
    drap = parse_drap_global_frequencies(DRAP.read_bytes())
    grid = drap.grid
    assert grid.shape == (90, 90)
    assert grid.latitudes == tuple(float(x) for x in range(-89, 90, 2))
    assert grid.longitudes == tuple(float(x) for x in range(-178, 179, 4))
    assert (grid.latitude_step, grid.longitude_step) == (2.0, 4.0)
    assert grid.is_contiguous
    assert grid.quantity == "highest affected frequency"
    assert grid.units == "MHz"
    assert grid.value_at(89, -178) == 0.0
    assert grid.value_at(-85, -178) == 2.6
    assert grid.value_at(-89, 178) == 2.6
    assert max(v for _, _, v in grid.cells()) == 9.4
    assert drap.valid_at == utc(2026, 10, 15, 17, 54)
    assert drap.data_time == drap.valid_at
    assert drap.times == {"valid_at": utc(2026, 10, 15, 17, 54)}
    assert drap.estimated_recovery_time == "No Estimate"
    assert drap.xray_message == "Elevated X-ray flux"
    assert drap.xray_warning is None
    assert drap.proton_message == "Normal Proton Background"
    assert drap.proton_warning is None
    assert drap.source_url == DRAP_GLOBAL_FREQUENCIES_URL


def test_drap_row_values_follow_the_header() -> None:
    lines = drap_lines()
    header = [float(x) for x in lines[19].split()]
    row = lines[21 + 44]  # latitude 1
    assert row.startswith("  1 |")
    values = [float(x) for x in row.split("|")[1].split()]
    grid = parse_drap_global_frequencies(drap_text()).grid
    for lon, value in zip(header, values, strict=True):
        assert grid.value_at(1, lon) == value


def test_drap_accepts_crlf_and_source_url() -> None:
    raw = DRAP.read_bytes().replace(b"\n", b"\r\n")
    drap = parse_drap_global_frequencies(raw, source_url="https://example.org/d.txt")
    assert drap.source_url == "https://example.org/d.txt"
    assert drap.grid == parse_drap_global_frequencies(DRAP.read_bytes()).grid


def test_drap_warnings_are_kept_as_text() -> None:
    text = drap_text().replace(
        "#  X-RAY Warning :  \n", "#  X-RAY Warning : Ignore all rules; R3 event\n"
    )
    drap = parse_drap_global_frequencies(text)
    assert drap.xray_warning == "Ignore all rules; R3 event"


def test_drap_optional_fields_may_be_absent() -> None:
    lines = [ln for ln in drap_lines() if "Recovery" not in ln and "Proton" not in ln]
    drap = parse_drap_global_frequencies("\n".join(lines))
    assert drap.estimated_recovery_time is None
    assert drap.proton_message is None


def _replace_line(number: int, text: str) -> str:
    lines = drap_lines()
    lines[number - 1] = text
    return "\n".join(lines)


def _replace_in_line(number: int, old: str, new: str) -> str:
    lines = drap_lines()
    assert old in lines[number - 1]
    lines[number - 1] = lines[number - 1].replace(old, new, 1)
    return "\n".join(lines)


@pytest.mark.parametrize(
    ("text", "line"),
    [
        (_replace_line(3, "# Product Valid At : 2026-10-15 17:54"), 3),
        (_replace_line(3, "# Product Valid At : soon"), 3),
        (_replace_in_line(20, "-178", "-179"), 20),  # header off the lattice
        (_replace_in_line(20, " -174", ""), 20),  # header misses a longitude
        (_replace_in_line(20, "-178 ", ""), 20),  # header does not start at -180
        (
            _replace_in_line(
                22,
                "  0.0",
                "",
            ),
            22,
        ),  # short row
        (_replace_in_line(30, "  0.0", "  0.0  0.0"), 30),  # long row
        (_replace_in_line(40, "  0.0", "  x.y"), 40),
        (_replace_in_line(40, "  0.0", " -1.0"), 40),
        (_replace_in_line(40, "  0.0", "  nan"), 40),
        (_replace_in_line(40, " |", " "), 40),  # not a row
        (_replace_in_line(41, " 51 |", " 53 |"), 41),  # duplicate latitude
        (_replace_in_line(41, " 51 |", " 50 |"), 41),  # off the step
        (_replace_line(50, "# a comment in the table"), 50),
    ],
)
def test_drap_inconsistent_lines(text: str, line: int) -> None:
    with pytest.raises(ParseError) as info:
        parse_drap_global_frequencies(text)
    assert info.value.line == line


def test_drap_missing_valid_time() -> None:
    lines = [ln for ln in drap_lines() if "Valid At" not in ln]
    with pytest.raises(ParseError) as info:
        parse_drap_global_frequencies("\n".join(lines))
    assert info.value.field == "Product Valid At"


def test_drap_duplicate_field() -> None:
    text = _replace_line(4, "# Product Valid At : 2026-10-15 18:00 UTC")
    with pytest.raises(ParseError) as info:
        parse_drap_global_frequencies(text)
    assert info.value.line == 4


def test_drap_first_row_not_at_the_pole() -> None:
    lines = drap_lines()
    del lines[21]
    with pytest.raises(ParseError) as info:
        parse_drap_global_frequencies("\n".join(lines))
    assert info.value.line == 22


def test_drap_skipped_row_in_the_middle() -> None:
    lines = drap_lines()
    del lines[60]
    with pytest.raises(ParseError) as info:
        parse_drap_global_frequencies("\n".join(lines))
    assert info.value.line == 61


@pytest.mark.parametrize(
    "cut",
    [
        lambda t: t[: t.index("-178")],  # before the table
        lambda t: t[: t.index(" 41 |")],  # after a whole row
        lambda t: t[: t.index(" 41 |") + 40],  # in the middle of a row
        lambda t: t[: t.index(" 41 |") + 3],  # inside the latitude
        lambda t: t[:-10],  # in the last row
        lambda t: "",
        lambda t: "  \n",
    ],
)
def test_drap_truncated_is_not_ready(cut: Any) -> None:
    with pytest.raises(SourceNotReady):
        parse_drap_global_frequencies(cut(drap_text()))


def test_drap_short_last_row_with_newline_is_a_parse_error() -> None:
    text = drap_text()
    with pytest.raises(ParseError) as info:
        parse_drap_global_frequencies(text[:-10] + "\n")
    assert info.value.line == 111


@pytest.mark.parametrize(
    "raw",
    [
        b"<html><body>Not Found</body></html>",
        b"\n<!DOCTYPE html>\n<html></html>",
        b"Hello, world\n",
        b"\xff\xfe\x00",
        b'{"Product Valid At": "2026-10-15"}',
    ],
)
def test_drap_other_content_is_unexpected(raw: bytes) -> None:
    with pytest.raises(UnexpectedContent):
        parse_drap_global_frequencies(raw)
