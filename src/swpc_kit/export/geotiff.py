"""GeoTIFF export of the gridded products, with the standard library only.

:func:`write_geotiff` writes an OVATION or D-RAP product as a one-band
``float32`` GeoTIFF in EPSG:4326 (WGS 84 latitude/longitude), compressed
with deflate. The raster is north-up, with longitudes moved into -180 to
180, and each pixel is a grid cell: the transform puts pixel edges half a
step around the cell centres, so OVATION, whose centres reach the poles and
-180, spans -180.5 to 179.5 and -90.5 to 90.5.

The times the content declares go into the dataset tags as ISO 8601 text
(``DATA_TIME``, then one tag per time, such as ``OBSERVATION_TIME``,
``FORECAST_TIME`` or ``VALID_AT``), with ``SOURCE_URL``, ``QUANTITY`` and
``UNITS``; ``TIFFTAG_DATETIME`` holds the data time in the TIFF format.
They are written as GDAL writes them, so GDAL, rasterio and QGIS read them
back as dataset metadata.
"""

import math
import os
import struct
import zlib
from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import escape

from swpc_kit.export._tiff import ASCII, DOUBLE, LONG, SHORT, Entry, encode
from swpc_kit.models.grids import GridProduct

__all__ = ["write_geotiff"]

_STRIP_BYTES = 8192
"""About how much raw data goes in one strip, as GDAL chooses."""


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _float32(value: float) -> float:
    return float(struct.unpack("<f", struct.pack("<f", value))[0])


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
        ValueError: If ``nodata`` is one of the grid's values, or does not
            fit in a ``float32``.
    """
    grid = product.grid.wrapped()
    try:
        nodata_32 = _float32(nodata)
    except OverflowError:
        raise ValueError(f"nodata {nodata} does not fit in float32") from None
    if not math.isnan(nodata) and any(
        _float32(value) == nodata_32 for row in grid.values for value in row
    ):
        raise ValueError(f"nodata {nodata} is also a value of the grid")
    dy, dx = grid.latitude_step, grid.longitude_step
    south, north = grid.latitudes[0], grid.latitudes[-1]
    west, east = grid.longitudes[0], grid.longitudes[-1]
    height = round((north - south) / dy) + 1
    width = round((east - west) / dx) + 1
    raster = [[nodata] * width for _ in range(height)]
    cols = [round((lon - west) / dx) for lon in grid.longitudes]
    for lat, values in zip(grid.latitudes, grid.values, strict=True):
        # Row 0 is the northernmost latitude; the grid is stored south first.
        row = raster[height - 1 - round((lat - south) / dy)]
        for col, value in zip(cols, values, strict=True):
            row[col] = value
    rows_per_strip = max(1, _STRIP_BYTES // (4 * width))
    strips = [
        zlib.compress(
            b"".join(
                struct.pack(f"<{width}f", *row)
                for row in raster[top : top + rows_per_strip]
            )
        )
        for top in range(0, height, rows_per_strip)
    ]

    data_time = product.data_time
    tags = {
        "SOURCE_URL": product.source_url,
        "QUANTITY": grid.quantity,
        "UNITS": grid.units,
        "DATA_TIME": _iso(data_time),
    }
    tags.update({name.upper(): _iso(time) for name, time in product.times.items()})
    items = [f'<Item name="{key}">{escape(text)}</Item>' for key, text in tags.items()]
    items.append(
        f'<Item name="DESCRIPTION" sample="0" role="description">'
        f"{escape(grid.quantity)}</Item>"
    )
    items.append(
        f'<Item name="UNITTYPE" sample="0" role="unittype">{escape(grid.units)}</Item>'
    )

    entries: list[Entry] = [
        (256, LONG, [width]),  # ImageWidth
        (257, LONG, [height]),  # ImageLength
        (258, SHORT, [32]),  # BitsPerSample
        (259, SHORT, [8]),  # Compression: deflate
        (262, SHORT, [1]),  # PhotometricInterpretation: min is black
        (277, SHORT, [1]),  # SamplesPerPixel
        (278, LONG, [rows_per_strip]),  # RowsPerStrip
        (279, LONG, [len(strip) for strip in strips]),  # StripByteCounts
        (284, SHORT, [1]),  # PlanarConfiguration: contiguous
        (306, ASCII, data_time.strftime("%Y:%m:%d %H:%M:%S")),  # DateTime
        (339, SHORT, [3]),  # SampleFormat: IEEE floating point
        (33550, DOUBLE, [dx, dy, 0.0]),  # ModelPixelScale
        # ModelTiepoint: pixel (0, 0) is the north-west corner of the grid.
        (33922, DOUBLE, [0.0, 0.0, 0.0, west - dx / 2, north + dy / 2, 0.0]),
        # GeoKeyDirectory, version 1.1.0 with three keys: a geographic model
        # (1024 = 2), pixels that are areas (1025 = 1), and EPSG:4326 (2048).
        (34735, SHORT, [1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 1, 2048, 0, 1, 4326]),
        (42112, ASCII, f"<GDALMetadata>{''.join(items)}</GDALMetadata>"),
        (42113, ASCII, repr(nodata)),  # GDAL_NODATA
    ]
    Path(path).write_bytes(encode(entries, strips))
