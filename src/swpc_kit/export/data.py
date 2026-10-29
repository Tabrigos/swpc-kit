"""Plain data from the models (standard library only).

:func:`to_dict` turns any model into dicts, lists and plain values, ready
for :func:`json.dumps`. :func:`to_records` turns a product into a list of
flat rows, one per record, ready for :class:`csv.DictWriter` or for
``pandas.DataFrame(...)``, without depending on pandas.

Both give the fields of the models, nothing computed: ``data_time``,
``flare_class`` and the other properties stay on the models.
"""

import types
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import UTC, date, datetime
from enum import Enum
from functools import cache
from typing import Any, Union, get_args, get_origin, get_type_hints

from swpc_kit.models.alerts import Alerts
from swpc_kit.models.bulletins import (
    GeomagneticForecast,
    ThreeDayForecast,
    TwentySevenDayOutlook,
)
from swpc_kit.models.goes import GoesLatestFlare
from swpc_kit.models.grids import Grid
from swpc_kit.models.indices import NoaaScales

__all__ = ["to_dict", "to_records"]

# The products whose rows are not in ``values``.
_ROWS: dict[type, str] = {
    Alerts: "messages",
    NoaaScales: "days",
    TwentySevenDayOutlook: "days",
    ThreeDayForecast: "kp",
    GeomagneticForecast: "kp",
}
# The products of one record, which is the product itself.
_ONE_ROW = (GoesLatestFlare,)


def _is_model(value: object) -> bool:
    return is_dataclass(value) and not isinstance(value, type)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _plain(value: Any) -> Any:
    if _is_model(value):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def to_dict(model: object) -> dict[str, Any]:
    """Return a model as plain data, ready for :func:`json.dumps`.

    Every field of the model becomes a key, in the order of the fields;
    nested models become dicts and tuples become lists. Times become ISO
    8601 text in UTC with ``Z`` (``"2026-10-15T12:00:00Z"``), dates
    ``"2026-10-15"``, and enum members their value.

    Args:
        model: Any model of :mod:`swpc_kit.models`: a product, a sample, a
            grid, a ``SkippedRecord``.

    Returns:
        A dict of str, int, float, bool, ``None``, lists and dicts.

    Raises:
        TypeError: If ``model`` is not a model.
    """
    if not _is_model(model):
        raise TypeError(f"to_dict takes a model, got {type(model).__name__}")
    data: dict[str, Any] = _plain(model)
    return data


@cache
def _nested(kind: type) -> dict[str, type]:
    """The fields of ``kind`` that hold a model (or ``None``), by name."""
    nested = {}
    for name, hint in get_type_hints(kind).items():
        if get_origin(hint) in (Union, types.UnionType):
            options = [a for a in get_args(hint) if a is not type(None)]
            hint = options[0] if len(options) == 1 else None
        if isinstance(hint, type) and is_dataclass(hint):
            nested[name] = hint
    return nested


def _flat(kind: type, value: object, prefix: str) -> Iterator[tuple[str, Any]]:
    nested = _nested(kind)
    for f in fields(kind):
        item = None if value is None else getattr(value, f.name)
        if f.name in nested:
            yield from _flat(nested[f.name], item, f"{prefix}{f.name}_")
        elif isinstance(item, Enum):
            yield prefix + f.name, item.value
        elif isinstance(item, (tuple, list)):
            yield prefix + f.name, [_plain(element) for element in item]
        else:
            yield prefix + f.name, item


def _rows(data: object) -> Sequence[Any]:
    if isinstance(data, _ONE_ROW):
        return (data,)
    if _is_model(data):
        rows = getattr(data, _ROWS.get(type(data), "values"), None)
        if isinstance(rows, tuple):
            return rows
    elif isinstance(data, (tuple, list)) and all(_is_model(row) for row in data):
        return data
    raise TypeError(
        "to_records takes a product, a grid or a sequence of records,"
        f" got {type(data).__name__}"
    )


def to_records(data: object) -> list[dict[str, Any]]:
    """Return the records of a product as flat rows.

    One dict per record, with the same keys in the same order for every
    row. Times stay aware UTC ``datetime`` objects (pandas reads them as
    ``datetime64[ns, UTC]``), dates stay ``date``, enum members become
    their value. A nested model is flattened with its field name as prefix
    (``g_scale``, ``noaa_scale_level``), with ``None`` in each column when
    it is absent. A field that holds a tuple, such as ``fields`` of an
    alert, becomes a list.

    The records of a product are its ``values``; for the alerts its
    ``messages``; for the NOAA scales and the 27-day outlook its ``days``;
    for the 3-day and geomagnetic forecasts the Kp periods (``kp``); for
    the latest flare one row, the product itself; for a grid or a gridded
    product its cells, ``latitude``, ``longitude`` and ``value``, with the
    longitudes as delivered.

    Args:
        data: A product, a grid, or a sequence of records of one kind (such
            as ``wind.active_series()`` or ``kp.skipped``).

    Returns:
        A list of dicts, empty if there are no records.

    Raises:
        TypeError: If ``data`` is none of these, or mixes kinds of record.
    """
    grid = data if isinstance(data, Grid) else getattr(data, "grid", None)
    if _is_model(data) and isinstance(grid, Grid):
        return [
            {"latitude": latitude, "longitude": longitude, "value": value}
            for latitude, longitude, value in grid.cells()
        ]
    rows = _rows(data)
    kinds = {type(row) for row in rows}
    if len(kinds) > 1:
        names = ", ".join(sorted(kind.__name__ for kind in kinds))
        raise TypeError(f"to_records wants records of one kind, got {names}")
    return [dict(_flat(type(row), row, "")) for row in rows]
