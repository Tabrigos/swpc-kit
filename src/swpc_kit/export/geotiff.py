"""GeoTIFF export of the gridded products (needs the ``geo`` extra).

:func:`write_geotiff` writes an OVATION or D-RAP product as a one-band
``float32`` GeoTIFF in EPSG:4326 (WGS 84 latitude/longitude). The raster is
north-up, with longitudes moved into -180 to 180, and each pixel is a grid
cell: the transform puts pixel edges half a step around the cell centres,
so OVATION, whose centres reach the poles and -180, spans -180.5 to 179.5
and -90.5 to 90.5.

The times the content declares go into the dataset tags as ISO 8601 text
(``DATA_TIME``, then one tag per time, such as ``OBSERVATION_TIME``,
``FORECAST_TIME`` or ``VALID_AT``), with ``SOURCE_URL``, ``QUANTITY`` and
``UNITS``; ``TIFFTAG_DATETIME`` holds the data time in the TIFF format.

Install the extra with ``pip install 'swpc-kit[geo]'``.
"""

import math
import os
from datetime import UTC, datetime

from swpc_kit.models.grids import GridProduct

try:
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
except ImportError as exc:
    raise ImportError(
        "swpc_kit.export.geotiff needs numpy and rasterio: pip install 'swpc-kit[geo]'"
    ) from exc

__all__ = ["write_geotiff"]


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def write_geotiff(
    product: GridProduct,
    path: str | os.PathLike[str],
    *,
    nodata: float = math.nan,
) -> None:
    """Write a gridded product to a GeoTIFF file.

    Cells the grid does not have (the missing longitudes of a reduced
    OVATION file) are set to ``nodata``.

    Args:
        product: An OVATION or D-RAP model, or any :class:`GridProduct`.
        path: Where to write the file; an existing file is replaced.
        nodata: Value of the cells without data, declared as the nodata
            value of the band. It must not be one of the grid's values.

    Raises:
        ValueError: If ``nodata`` is one of the grid's values.
    """
    grid = product.grid.wrapped()
    values = np.array(grid.values, dtype=np.float32)
    nodata_32 = np.float32(nodata)
    if not math.isnan(nodata) and (values == nodata_32).any():
        raise ValueError(f"nodata {nodata} is also a value of the grid")
    dy, dx = grid.latitude_step, grid.longitude_step
    south, north = grid.latitudes[0], grid.latitudes[-1]
    west, east = grid.longitudes[0], grid.longitudes[-1]
    height = round((north - south) / dy) + 1
    width = round((east - west) / dx) + 1
    rows = [height - 1 - round((lat - south) / dy) for lat in grid.latitudes]
    cols = [round((lon - west) / dx) for lon in grid.longitudes]
    data = np.full((height, width), nodata_32, dtype=np.float32)
    data[np.ix_(rows, cols)] = values

    data_time = product.data_time
    tags = {
        "SOURCE_URL": product.source_url,
        "QUANTITY": grid.quantity,
        "UNITS": grid.units,
        "DATA_TIME": _iso(data_time),
        "TIFFTAG_DATETIME": data_time.strftime("%Y:%m:%d %H:%M:%S"),
    }
    tags.update({name.upper(): _iso(time) for name, time in product.times.items()})
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(west - dx / 2, north + dy / 2, dx, dy),
        nodata=nodata,
        compress="deflate",
    ) as dst:
        dst.write(data, 1)
        dst.update_tags(**tags)
        dst.set_band_description(1, grid.quantity)
        dst.set_band_unit(1, grid.units)
