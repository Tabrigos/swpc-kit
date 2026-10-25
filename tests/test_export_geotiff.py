import importlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio

from swpc_kit.export.geotiff import write_geotiff
from swpc_kit.models.grids import DrapFrequencies, OvationAurora
from swpc_kit.parse.grids import (
    DRAP_GLOBAL_FREQUENCIES_URL,
    OVATION_AURORA_URL,
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
            [lon, lat, (lon * 7 + lat + 90) % 41]
            for lon in range(360)
            for lat in range(-90, 91)
        ],
    }
    return parse_ovation_aurora(json.dumps(document))


def test_drap_raster(tmp_path: Path) -> None:
    product = drap()
    path = tmp_path / "drap.tif"
    write_geotiff(product, path)
    with rasterio.open(path) as src:
        assert src.driver == "GTiff"
        assert src.crs.to_epsg() == 4326
        assert (src.count, src.height, src.width) == (1, 90, 90)
        assert src.dtypes == ("float32",)
        assert tuple(src.transform)[:6] == (4.0, 0.0, -180.0, 0.0, -2.0, 90.0)
        assert src.bounds == (-180.0, -90.0, 180.0, 90.0)
        assert math.isnan(src.nodata)
        assert src.descriptions == ("highest affected frequency",)
        assert src.units == ("MHz",)
        data = src.read(1)
        # Row 0 is the northernmost latitude; the grid is stored south first.
        expected = np.flipud(np.array(product.grid.values, dtype=np.float32))
        np.testing.assert_array_equal(data, expected)
        # rasterio 1.4.0 gives the indices as floats.
        row, col = map(int, src.index(-142, 1))
        assert data[row, col] == pytest.approx(product.grid.value_at(1, -142))
        assert src.xy(row, col) == (-142.0, 1.0)


def test_time_tags(tmp_path: Path) -> None:
    write_geotiff(drap(), tmp_path / "drap.tif")
    write_geotiff(reduced_ovation(), str(tmp_path / "oval.tif"))
    with rasterio.open(tmp_path / "drap.tif") as src:
        tags = src.tags()
    assert tags["VALID_AT"] == "2026-10-15T17:54:00Z"
    assert tags["DATA_TIME"] == "2026-10-15T17:54:00Z"
    assert tags["TIFFTAG_DATETIME"] == "2026:10:15 17:54:00"
    assert tags["SOURCE_URL"] == DRAP_GLOBAL_FREQUENCIES_URL
    assert tags["QUANTITY"] == "highest affected frequency"
    assert tags["UNITS"] == "MHz"
    assert tags["AREA_OR_POINT"] == "Area"
    with rasterio.open(tmp_path / "oval.tif") as src:
        tags = src.tags()
    assert tags["OBSERVATION_TIME"] == "2026-10-15T17:48:00Z"
    assert tags["FORECAST_TIME"] == "2026-10-15T18:47:00Z"
    assert tags["DATA_TIME"] == "2026-10-15T17:48:00Z"
    assert tags["TIFFTAG_DATETIME"] == "2026:10:15 17:48:00"
    assert tags["SOURCE_URL"] == OVATION_AURORA_URL
    assert tags["UNITS"] == "%"


def test_full_ovation_is_rotated_to_minus_180(tmp_path: Path) -> None:
    product = full_ovation()
    write_geotiff(product, tmp_path / "oval.tif")
    with rasterio.open(tmp_path / "oval.tif") as src:
        assert (src.height, src.width) == (181, 360)
        # Cell centres run from -180 to 179 and from 90 to -90.
        assert tuple(src.transform)[:6] == (1.0, 0.0, -180.5, 0.0, -1.0, 90.5)
        data = src.read(1)
        assert not np.isnan(data).any()
        for lon, lat in [(0, 0), (359, 45), (180, -90), (179, 90), (200, -60)]:
            row, col = map(int, src.index(((lon + 180) % 360) - 180, lat))
            assert data[row, col] == product.grid.value_at(lat, lon)
        assert data[0, 0] == product.grid.value_at(90, 180)
        assert data[-1, -1] == product.grid.value_at(-90, 179)


def test_reduced_ovation_leaves_missing_longitudes_empty(tmp_path: Path) -> None:
    product = reduced_ovation()
    write_geotiff(product, tmp_path / "oval.tif")
    with rasterio.open(tmp_path / "oval.tif") as src:
        # Wrapped longitudes run from -180 (180) to 150.
        assert (src.height, src.width) == (181, 331)
        assert src.bounds.left == -180.5
        assert src.bounds.right == 150.5
        masked = src.read(1, masked=True)
    present = {round(((lon + 180) % 360) - 180) for lon in product.grid.longitudes}
    for col in range(331):
        lon = col - 180
        column = masked[:, col]
        if lon in present:
            assert not column.mask.any()
            for row in (0, 90, 180):
                assert column[row] == product.grid.value_at(90 - row, lon)
        else:
            assert column.mask.all()


def test_nodata_can_be_chosen(tmp_path: Path) -> None:
    write_geotiff(reduced_ovation(), tmp_path / "oval.tif", nodata=-1.0)
    with rasterio.open(tmp_path / "oval.tif") as src:
        assert src.nodata == -1.0
        data = src.read(1)
    assert (data[:, 1] == -1.0).all()  # longitude -179 is not in the file


def test_nodata_must_not_be_a_value(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="nodata"):
        write_geotiff(drap(), tmp_path / "drap.tif", nodata=0.0)
    assert not (tmp_path / "drap.tif").exists()


def test_missing_geo_extra_gives_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "rasterio", None)
    monkeypatch.delitem(sys.modules, "swpc_kit.export.geotiff")
    with pytest.raises(ImportError, match=r"pip install 'swpc-kit\[geo\]'"):
        importlib.import_module("swpc_kit.export.geotiff")
