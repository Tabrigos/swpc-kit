"""GeoJSON export of the gridded products (standard library only).

:func:`to_geojson` turns an OVATION or D-RAP product into a GeoJSON
``FeatureCollection`` (RFC 7946): one feature per grid cell, as the cell's
polygon or its centre point, optionally only for cells at or above a
threshold. Longitudes are moved into -180 to 180; a cell that straddles the
antimeridian becomes a ``MultiPolygon`` of its two halves, and cells at the
poles stop at ±90.
"""

import math
from datetime import UTC, datetime
from typing import Any, Literal

from swpc_kit.models.grids import GridProduct

Geometry = Literal["polygon", "point"]


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _ring(west: float, south: float, east: float, north: float) -> list[list[float]]:
    # Counter-clockwise, as RFC 7946 asks for exterior rings.
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


def _cell(
    latitude: float, longitude: float, half_height: float, half_width: float
) -> dict[str, Any]:
    south = max(latitude - half_height, -90.0)
    north = min(latitude + half_height, 90.0)
    west, east = longitude - half_width, longitude + half_width
    if west < -180:
        parts = [(west + 360, 180.0), (-180.0, east)]
    elif east > 180:
        parts = [(west, 180.0), (-180.0, east - 360)]
    else:
        return {"type": "Polygon", "coordinates": [_ring(west, south, east, north)]}
    return {
        "type": "MultiPolygon",
        "coordinates": [[_ring(w, south, e, north)] for w, e in parts],
    }


def to_geojson(
    product: GridProduct,
    *,
    threshold: float | None = None,
    geometry: Geometry = "polygon",
) -> dict[str, Any]:
    """Return the cells of a gridded product as a GeoJSON FeatureCollection.

    Each feature has the properties ``latitude`` and ``longitude`` (the cell
    centre, longitude in [-180, 180)) and ``value``. Features come row by
    row, from south to north and from west to east. The collection carries a
    ``metadata`` member (a foreign member in RFC 7946 terms) with
    ``quantity``, ``units``, ``source_url``, ``data_time``, each time of
    ``product.times`` as ISO 8601 text, and ``threshold``.

    Args:
        product: An OVATION or D-RAP model, or any :class:`GridProduct`.
        threshold: Keep only cells whose value is at least this; ``None``
            keeps every cell.
        geometry: ``"polygon"`` for the cell outline, ``"point"`` for its
            centre.

    Returns:
        A dict ready for :func:`json.dumps`.

    Raises:
        ValueError: If ``geometry`` is unknown or ``threshold`` is not a
            finite number.
    """
    if geometry not in ("polygon", "point"):
        raise ValueError(f"geometry must be 'polygon' or 'point', got {geometry!r}")
    if threshold is not None and not math.isfinite(threshold):
        raise ValueError(f"threshold must be a finite number, got {threshold!r}")
    grid = product.grid.wrapped()
    half_height = grid.latitude_step / 2
    half_width = grid.longitude_step / 2
    features = []
    for latitude, longitude, value in grid.cells():
        if threshold is not None and value < threshold:
            continue
        shape = (
            _cell(latitude, longitude, half_height, half_width)
            if geometry == "polygon"
            else {"type": "Point", "coordinates": [longitude, latitude]}
        )
        features.append(
            {
                "type": "Feature",
                "geometry": shape,
                "properties": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "value": value,
                },
            }
        )
    metadata: dict[str, Any] = {
        "quantity": grid.quantity,
        "units": grid.units,
        "source_url": product.source_url,
        "data_time": _iso(product.data_time),
    }
    metadata.update({name: _iso(time) for name, time in product.times.items()})
    metadata["threshold"] = threshold
    return {"type": "FeatureCollection", "metadata": metadata, "features": features}
