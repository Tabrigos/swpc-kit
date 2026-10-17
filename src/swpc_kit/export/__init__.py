"""Exports of the gridded products (OVATION, D-RAP).

:func:`to_geojson` uses only the standard library and is re-exported here.
GeoTIFF export needs the ``geo`` extra and lives in
:mod:`swpc_kit.export.geotiff` (``write_geotiff``), so that importing this
package never requires numpy or rasterio.
"""

from swpc_kit.export.geojson import to_geojson

__all__ = ["to_geojson"]
