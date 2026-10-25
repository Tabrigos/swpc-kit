"""Exports of the models: plain data, and the gridded products as maps.

:func:`to_dict` and :func:`to_records` (plain data for JSON and for tables)
and :func:`to_geojson` (OVATION, D-RAP) use only the standard library and
are re-exported here. GeoTIFF export needs the ``geo`` extra and lives in
:mod:`swpc_kit.export.geotiff` (``write_geotiff``), so that importing this
package never requires numpy or rasterio.
"""

from swpc_kit.export.data import to_dict, to_records
from swpc_kit.export.geojson import to_geojson

__all__ = ["to_dict", "to_geojson", "to_records"]
