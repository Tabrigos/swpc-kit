"""Parsers for the gridded products: OVATION aurora and D-RAP.

``ovation_aurora_latest.json`` is a JSON object whose ``coordinates`` hold
``[longitude, latitude, aurora]`` triples, one per point of a 1-degree grid
(longitudes 0 to 359, latitudes -90 to 90). ``drap_global_frequencies.txt``
is a text table: comment lines with the times and messages, a header row of
longitudes, then one row per latitude. Both give a
:class:`~swpc_kit.models.grids.Grid` with latitudes from south to north.
"""

import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.models.grids import DrapFrequencies, Grid, OvationAurora
from swpc_kit.parse._common import decode, load_json, parse_time

OVATION_AURORA_URL = "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json"
DRAP_GLOBAL_FREQUENCIES_URL = (
    "https://services.swpc.noaa.gov/text/drap_global_frequencies.txt"
)

# --- OVATION -----------------------------------------------------------------

_OVATION_FORMAT = "[longitude,latitude,aurora]"
_OVATION_LONGITUDES = range(360)
_OVATION_LATITUDES = range(-90, 91)


def _ovation_time(document: dict[str, Any], field: str) -> datetime:
    value = document.get(field)
    if not isinstance(value, str):
        raise ParseError(f"expected a time, got {value!r}", field=field)
    try:
        return parse_time(value)
    except ValueError as exc:
        raise ParseError(str(exc), field=field) from None


def _ovation_integer(value: Any, field: str, index: int, axis: range) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ParseError(
            f"expected an integer, got {value!r}", field=field, index=index
        )
    if value not in axis:
        raise ParseError(
            f"{value} out of range [{axis[0]}, {axis[-1]}]", field=field, index=index
        )
    return value


def _ovation_value(value: Any, index: int) -> float:
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or value < 0
    ):
        raise ParseError(
            f"expected a non-negative number, got {value!r}",
            field="Aurora",
            index=index,
        )
    return float(value)


def parse_ovation_aurora(
    raw: str | bytes, *, source_url: str = OVATION_AURORA_URL, partial: bool = False
) -> OvationAurora:
    """Parse ``ovation_aurora_latest.json`` (the OVATION aurora nowcast).

    Points may come in any order. Every point of the grid must be present
    exactly once: 360 longitudes (0 to 359) by 181 latitudes (-90 to 90).
    With ``partial=True`` some longitudes may be missing altogether, as in a
    reduced copy of the file; each longitude present must still have all
    its latitudes. The grid keeps the longitudes as delivered (0 to 359).

    Errors about one triple name ``Longitude``, ``Latitude`` or ``Aurora``
    (or ``coordinates`` for the triple itself) and its index in
    ``coordinates``.

    Args:
        raw: The content.
        source_url: Where the content came from.
        partial: Accept a grid with whole longitudes missing.

    Raises:
        SourceNotReady: If the content is empty, truncated or has no points.
        UnexpectedContent: If the content is not a JSON object, or its
            ``Data Format`` is not ``[Longitude, Latitude, Aurora]``.
        ParseError: If a field or point is missing, duplicated or
            inconsistent.
    """
    document = load_json(raw)
    if not isinstance(document, dict):
        raise UnexpectedContent(
            f"expected a JSON object, got {type(document).__name__}"
        )
    observation_time = _ovation_time(document, "Observation Time")
    forecast_time = _ovation_time(document, "Forecast Time")
    data_format = document.get("Data Format")
    if not isinstance(data_format, str):
        raise ParseError(f"expected a string, got {data_format!r}", field="Data Format")
    if re.sub(r"\s+", "", data_format).lower() != _OVATION_FORMAT:
        raise UnexpectedContent(f"unknown Data Format {data_format!r}")
    coordinates = document.get("coordinates")
    if not isinstance(coordinates, list):
        raise ParseError(
            f"expected an array, got {coordinates!r:.40}", field="coordinates"
        )
    if not coordinates:
        raise SourceNotReady("no coordinates")

    columns: dict[int, dict[int, float]] = {}
    for index, item in enumerate(coordinates):
        if not isinstance(item, list) or len(item) != 3:
            raise ParseError(
                f"expected [longitude, latitude, aurora], got {item!r:.40}",
                field="coordinates",
                index=index,
            )
        lon = _ovation_integer(item[0], "Longitude", index, _OVATION_LONGITUDES)
        lat = _ovation_integer(item[1], "Latitude", index, _OVATION_LATITUDES)
        value = _ovation_value(item[2], index)
        column = columns.setdefault(lon, {})
        if lat in column:
            raise ParseError(
                f"duplicate point at longitude {lon}, latitude {lat}",
                field="coordinates",
                index=index,
            )
        column[lat] = value

    longitudes = sorted(columns)
    for lon in longitudes:
        missing = [lat for lat in _OVATION_LATITUDES if lat not in columns[lon]]
        if missing:
            raise ParseError(
                f"longitude {lon} has no value at latitude {missing[0]}"
                f" ({len(missing)} latitudes missing)",
                field="coordinates",
            )
    if not partial and len(longitudes) != len(_OVATION_LONGITUDES):
        absent = [lon for lon in _OVATION_LONGITUDES if lon not in columns]
        raise ParseError(
            f"{len(absent)} longitudes missing, first {absent[0]}"
            " (partial=True accepts a reduced grid)",
            field="coordinates",
        )
    grid = Grid(
        latitudes=tuple(float(lat) for lat in _OVATION_LATITUDES),
        longitudes=tuple(float(lon) for lon in longitudes),
        latitude_step=1.0,
        longitude_step=1.0,
        values=tuple(
            tuple(columns[lon][lat] for lon in longitudes) for lat in _OVATION_LATITUDES
        ),
        quantity="aurora",
        units="%",
    )
    return OvationAurora(
        grid=grid,
        observation_time=observation_time,
        forecast_time=forecast_time,
        source_url=source_url,
    )


# --- D-RAP -------------------------------------------------------------------

_DRAP_FIELDS = {
    "Product Valid At": "valid_at",
    "Estimated Recovery Time": "estimated_recovery_time",
    "X-RAY Message": "xray_message",
    "X-RAY Warning": "xray_warning",
    "Proton Message": "proton_message",
    "Proton Warning": "proton_warning",
}
_DRAP_FIELD = re.compile(r"#\s*([A-Za-z][A-Za-z -]*?)\s*:(.*)")
_DRAP_VALID_AT = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?) UTC")
_DRAP_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_DRAP_FREQUENCY = re.compile(r"\d+(?:\.\d+)?")
_DRAP_ROW = re.compile(r"\s*(-?\d+(?:\.\d+)?)\s*\|(.*)")
_DRAP_RULE = re.compile(r"\s*-+\s*")


@dataclass(slots=True)
class _Row:
    line: int
    latitude: float
    values: tuple[float, ...]


def _regular_axis(values: list[float], line: int, name: str) -> float:
    """Return the constant step of ``values``, which span the whole globe."""
    if len(values) < 2:
        raise ParseError(f"expected at least two {name}", line=line)
    step = values[1] - values[0]
    for i, value in enumerate(values):
        if not math.isclose(value, values[0] + i * step, abs_tol=1e-6):
            raise ParseError(f"{name} are not evenly spaced at {value}", line=line)
    return step


def _drap_header(text: str, line: int) -> tuple[float, ...]:
    tokens = text.split()
    if not all(_DRAP_NUMBER.fullmatch(t) for t in tokens):
        raise ParseError(
            f"expected a row of longitudes, got {text.strip()!r:.40}", line=line
        )
    longitudes = [float(t) for t in tokens]
    step = _regular_axis(longitudes, line, "longitudes")
    if step <= 0:
        raise ParseError("longitudes must increase", line=line)
    west, east = longitudes[0] - step / 2, longitudes[-1] + step / 2
    if not (math.isclose(west, -180) and math.isclose(east, 180)):
        raise ParseError(
            f"longitudes cover {west} to {east}, not -180 to 180", line=line
        )
    return tuple(longitudes)


def _drap_row(text: str, line: int, width: int) -> _Row:
    match = _DRAP_ROW.fullmatch(text)
    if match is None:
        raise ParseError(
            f"expected 'latitude | values', got {text.strip()!r:.40}", line=line
        )
    tokens = match.group(2).split()
    if len(tokens) != width:
        raise ParseError(
            f"{len(tokens)} values for {width} longitudes", field="frequency", line=line
        )
    for token in tokens:
        if not _DRAP_FREQUENCY.fullmatch(token):
            raise ParseError(
                f"expected a frequency, got {token!r}", field="frequency", line=line
            )
    return _Row(line, float(match.group(1)), tuple(float(t) for t in tokens))


def _drap_latitudes(rows: list[_Row]) -> float:
    """Check the rows run evenly from one pole to the other; return the step."""
    if len(rows) < 2:
        raise SourceNotReady("the table stops after its first row")
    step = rows[1].latitude - rows[0].latitude
    if step == 0:
        raise ParseError("duplicate latitude", field="latitude", line=rows[1].line)
    for i, row in enumerate(rows):
        expected = rows[0].latitude + i * step
        if not math.isclose(row.latitude, expected, abs_tol=1e-6):
            raise ParseError(
                f"expected latitude {expected:g}, got {row.latitude:g}",
                field="latitude",
                line=row.line,
            )
    edge = abs(rows[0].latitude) + abs(step) / 2
    if not math.isclose(edge, 90) or math.copysign(
        1, rows[0].latitude
    ) == math.copysign(1, step):
        raise ParseError(
            f"the table does not start at a pole (latitude {rows[0].latitude:g})",
            field="latitude",
            line=rows[0].line,
        )
    if not math.isclose(rows[-1].latitude, -rows[0].latitude):
        raise SourceNotReady(f"the table stops at latitude {rows[-1].latitude:g}")
    return abs(step)


def parse_drap_global_frequencies(
    raw: str | bytes, *, source_url: str = DRAP_GLOBAL_FREQUENCIES_URL
) -> DrapFrequencies:
    """Parse ``drap_global_frequencies.txt`` (D-RAP, global frequencies).

    The table must cover the globe: header longitudes from one cell after
    -180 to one cell before 180, evenly spaced, and rows evenly spaced from
    one pole to the other (the source goes from north to south; the grid
    is stored from south to north). The comment fields are kept as text;
    only ``Product Valid At`` is required. Errors name the 1-based line.

    Args:
        raw: The content. Unix and Windows line ends are accepted.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or stops before the end of
            the table.
        UnexpectedContent: If the content is HTML, not UTF-8, or does not
            start with comment lines.
        ParseError: If a field, the header or a row is missing or
            inconsistent.
    """
    text = decode(raw)
    stripped = text.strip()
    if not stripped:
        raise SourceNotReady("empty content")
    if stripped.startswith("<"):
        raise UnexpectedContent("got HTML or XML instead of the D-RAP table")
    if not stripped.startswith("#"):
        raise UnexpectedContent("expected the D-RAP comment header ('# ...')")
    complete = text.endswith("\n")
    lines = text.splitlines()

    fields: dict[str, tuple[str, int]] = {}
    longitudes: tuple[float, ...] | None = None
    rows: list[_Row] = []
    for number, line in enumerate(lines, start=1):
        try:
            if longitudes is None:
                if not line.strip():
                    continue
                if line.startswith("#"):
                    _drap_comment(line, number, fields)
                    continue
                if number == len(lines) and not complete:
                    break
                longitudes = _drap_header(line, number)
            elif not line.strip() or (not rows and _DRAP_RULE.fullmatch(line)):
                continue
            else:
                rows.append(_drap_row(line, number, len(longitudes)))
        except ParseError:
            if number == len(lines) and not complete:
                raise SourceNotReady(f"the content stops in line {number}") from None
            raise
    if longitudes is None or not rows:
        raise SourceNotReady("the content stops before the table")
    latitude_step = _drap_latitudes(rows)
    if rows[0].latitude > rows[-1].latitude:
        rows.reverse()

    if "valid_at" not in fields:
        raise ParseError("missing field", field="Product Valid At")
    valid_text, valid_line = fields["valid_at"]
    match = _DRAP_VALID_AT.fullmatch(valid_text)
    try:
        if match is None:
            raise ValueError(f"expected 'YYYY-MM-DD HH:MM UTC', got {valid_text!r}")
        valid_at = parse_time(match.group(1))
    except ValueError as exc:
        raise ParseError(str(exc), field="Product Valid At", line=valid_line) from None

    def text_field(name: str) -> str | None:
        value = fields.get(name, ("", 0))[0]
        return value or None

    grid = Grid(
        latitudes=tuple(row.latitude for row in rows),
        longitudes=longitudes,
        latitude_step=latitude_step,
        longitude_step=longitudes[1] - longitudes[0],
        values=tuple(row.values for row in rows),
        quantity="highest affected frequency",
        units="MHz",
    )
    return DrapFrequencies(
        grid=grid,
        valid_at=valid_at,
        estimated_recovery_time=text_field("estimated_recovery_time"),
        xray_message=text_field("xray_message"),
        xray_warning=text_field("xray_warning"),
        proton_message=text_field("proton_message"),
        proton_warning=text_field("proton_warning"),
        source_url=source_url,
    )


def _drap_comment(line: str, number: int, fields: dict[str, tuple[str, int]]) -> None:
    match = _DRAP_FIELD.fullmatch(line)
    if match is None or match.group(1) not in _DRAP_FIELDS:
        return
    name = _DRAP_FIELDS[match.group(1)]
    if name in fields:
        raise ParseError("duplicate field", field=match.group(1), line=number)
    fields[name] = (match.group(2).strip(), number)
