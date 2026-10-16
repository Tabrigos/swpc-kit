import json
import subprocess
import sys
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from swpc_kit.export.geojson import to_geojson
from swpc_kit.models.grids import DrapFrequencies, OvationAurora
from swpc_kit.parse.grids import (
    DRAP_GLOBAL_FREQUENCIES_URL,
    parse_drap_global_frequencies,
    parse_ovation_aurora,
)

FIXTURES = Path(__file__).parent / "fixtures"


def drap() -> DrapFrequencies:
    return parse_drap_global_frequencies(
        (FIXTURES / "drap/2026-10-15.txt").read_bytes()
    )


def reduced_ovation() -> OvationAurora:
    raw = (FIXTURES / "ovation-aurora/2026-10-15.json").read_bytes()
    return parse_ovation_aurora(raw, partial=True)


def full_ovation() -> OvationAurora:
    document = {
        "Observation Time": "2026-10-15T17:48:00Z",
        "Forecast Time": "2026-10-15T18:47:00Z",
        "Data Format": "[Longitude, Latitude, Aurora]",
        "coordinates": [
            [lon, lat, (lon + lat + 90) % 30]
            for lon in range(360)
            for lat in range(-90, 91)
        ],
    }
    return parse_ovation_aurora(json.dumps(document))


def rings(geometry: dict[str, Any]) -> list[list[list[float]]]:
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    assert geometry["type"] == "MultiPolygon"
    return [polygon[0] for polygon in geometry["coordinates"]]


def signed_area(ring: list[list[float]]) -> float:
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in pairwise(ring)) / 2


def test_drap_polygons() -> None:
    product = drap()
    collection = to_geojson(product)
    assert collection["type"] == "FeatureCollection"
    features = collection["features"]
    assert len(features) == 90 * 90
    first = features[0]
    assert first["type"] == "Feature"
    assert first["properties"] == {"latitude": -89.0, "longitude": -178.0, "value": 2.6}
    assert first["geometry"] == {
        "type": "Polygon",
        "coordinates": [
            [
                [-180.0, -90.0],
                [-176.0, -90.0],
                [-176.0, -88.0],
                [-180.0, -88.0],
                [-180.0, -90.0],
            ]
        ],
    }
    for feature in features:
        for ring in rings(feature["geometry"]):
            assert ring[0] == ring[-1]
            assert signed_area(ring) > 0  # counter-clockwise (RFC 7946)


def test_metadata() -> None:
    collection = to_geojson(drap(), threshold=1.5)
    assert collection["metadata"] == {
        "quantity": "highest affected frequency",
        "units": "MHz",
        "source_url": DRAP_GLOBAL_FREQUENCIES_URL,
        "data_time": "2026-10-15T17:54:00Z",
        "valid_at": "2026-10-15T17:54:00Z",
        "threshold": 1.5,
    }
    oval = to_geojson(reduced_ovation())["metadata"]
    assert oval["observation_time"] == "2026-10-15T17:48:00Z"
    assert oval["forecast_time"] == "2026-10-15T18:47:00Z"
    assert oval["data_time"] == "2026-10-15T17:48:00Z"
    assert oval["threshold"] is None


@pytest.mark.parametrize("threshold", [0.0, 0.1, 5.0, 9.4, 9.5])
def test_threshold_keeps_cells_at_or_above_it(threshold: float) -> None:
    product = drap()
    features = to_geojson(product, threshold=threshold)["features"]
    expected = [c for c in product.grid.cells() if c[2] >= threshold]
    assert len(features) == len(expected)
    assert all(f["properties"]["value"] >= threshold for f in features)


def test_points() -> None:
    product = full_ovation()
    features = to_geojson(product, geometry="point")["features"]
    assert len(features) == 360 * 181
    coordinates = [f["geometry"]["coordinates"] for f in features]
    assert all(f["geometry"]["type"] == "Point" for f in features)
    assert all(-180 <= lon < 180 and -90 <= lat <= 90 for lon, lat in coordinates)
    by_place = {
        tuple(c): f["properties"] for c, f in zip(coordinates, features, strict=True)
    }
    assert by_place[(-1.0, 45.0)] == {
        "latitude": 45.0,
        "longitude": -1.0,
        "value": product.grid.value_at(45, 359),
    }
    assert by_place[(-180.0, 0.0)]["value"] == product.grid.value_at(0, 180)


def test_ovation_polygons_are_wrapped_and_split_at_the_antimeridian() -> None:
    product = full_ovation()
    features = to_geojson(product)["features"]
    assert len(features) == 360 * 181
    for feature in features:
        for ring in rings(feature["geometry"]):
            assert all(-180 <= x <= 180 and -90 <= y <= 90 for x, y in ring)
            assert signed_area(ring) > 0
    split = [f for f in features if f["geometry"]["type"] == "MultiPolygon"]
    assert len(split) == 181
    assert all(f["properties"]["longitude"] == -180.0 for f in split)
    equator = next(f for f in split if f["properties"]["latitude"] == 0.0)
    assert equator["geometry"]["coordinates"] == [
        [[[179.5, -0.5], [180.0, -0.5], [180.0, 0.5], [179.5, 0.5], [179.5, -0.5]]],
        [
            [
                [-180.0, -0.5],
                [-179.5, -0.5],
                [-179.5, 0.5],
                [-180.0, 0.5],
                [-180.0, -0.5],
            ]
        ],
    ]


def test_polar_cells_stop_at_the_pole() -> None:
    features = to_geojson(full_ovation())["features"]
    north = next(
        f
        for f in features
        if f["properties"]["latitude"] == 90.0 and f["properties"]["longitude"] == 0.0
    )
    assert north["geometry"]["coordinates"] == [
        [[-0.5, 89.5], [0.5, 89.5], [0.5, 90.0], [-0.5, 90.0], [-0.5, 89.5]]
    ]


def test_reduced_ovation_exports_only_its_longitudes() -> None:
    features = to_geojson(reduced_ovation(), geometry="point")["features"]
    assert len(features) == 15 * 181
    longitudes = sorted({f["properties"]["longitude"] for f in features})
    assert longitudes == [
        -180.0,
        -150.0,
        -120.0,
        -90.0,
        -60.0,
        -30.0,
        -2.0,
        -1.0,
        0.0,
        1.0,
        30.0,
        60.0,
        90.0,
        120.0,
        150.0,
    ]


def test_output_is_plain_json() -> None:
    collection = to_geojson(reduced_ovation(), threshold=10)
    text = json.dumps(collection, allow_nan=False)
    assert json.loads(text) == collection
    assert collection["features"]


@pytest.mark.parametrize(
    "kwargs",
    [{"geometry": "line"}, {"threshold": float("nan")}, {"threshold": float("inf")}],
)
def test_bad_arguments(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        to_geojson(drap(), **kwargs)


def test_core_needs_only_the_standard_library() -> None:
    code = (
        "import sys\n"
        "import swpc_kit.export.geojson, swpc_kit.parse.grids, swpc_kit.models.grids\n"
        "print(sorted({'numpy', 'rasterio'} & set(sys.modules)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
