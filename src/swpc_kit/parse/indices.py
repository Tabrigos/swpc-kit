"""Parsers for the geomagnetic and solar indices.

Each parser accepts the current format (an array of objects) and, where SWPC
used one before 2026, the old format (an array of arrays with a header row
and quoted numbers). Both give the same model.
"""

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any, Protocol

from swpc_kit.errors import ParseError, SourceNotReady, SwpcError, UnexpectedContent
from swpc_kit.models.indices import (
    DstValue,
    F107Flux,
    F107Value,
    GeomagneticStormScale,
    Kp1mValue,
    KpForecastStatus,
    KpForecastValue,
    KpValue,
    KyotoDst,
    NoaaScales,
    NoaaScalesDay,
    PlanetaryKIndex,
    PlanetaryKIndex1m,
    PlanetaryKIndexForecast,
    RadioBlackoutScale,
    SolarRadiationScale,
)
from swpc_kit.parse._common import Record, json_records, load_json, parse_time

PLANETARY_K_INDEX_URL = (
    "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
)
PLANETARY_K_INDEX_FORECAST_URL = (
    "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
)
PLANETARY_K_INDEX_1M_URL = (
    "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"
)
KYOTO_DST_URL = "https://services.swpc.noaa.gov/products/kyoto-dst.json"
F107_FLUX_30_DAY_URL = "https://services.swpc.noaa.gov/products/10cm-flux-30-day.json"
NOAA_SCALES_URL = "https://services.swpc.noaa.gov/products/noaa-scales.json"

_KP_LABEL = re.compile(r"[0-9][ZPM]")
_SCALE_DAY = re.compile(r"-?[0-9]+")


class _Timed(Protocol):
    @property
    def time(self) -> datetime: ...


def _in_time_order[V: _Timed](values: Iterable[V]) -> tuple[V, ...]:
    """Sort the values oldest first; a time that appears twice is an error.

    SWPC writes these series oldest first, but nothing guarantees it, and
    callers read ``values[-1]`` as the latest value.
    """
    items = list(values)
    seen: dict[datetime, int] = {}
    for index, value in enumerate(items):
        first = seen.setdefault(value.time, index)
        if first != index:
            raise ParseError(
                f"time {value.time.isoformat()} appears twice"
                f" (records {first} and {index})",
                field="time_tag",
                index=index,
            )
    return tuple(sorted(items, key=lambda v: v.time))


def parse_planetary_k_index(
    raw: str | bytes, *, source_url: str = PLANETARY_K_INDEX_URL
) -> PlanetaryKIndex:
    """Parse ``noaa-planetary-k-index.json`` (3-hour Kp of the last days).

    Args:
        raw: The content, current or old format.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If a value is missing or inconsistent.
    """
    values = _in_time_order(
        KpValue(
            time=r.get_time("time_tag"),
            kp=r.get_float("Kp", minimum=0, maximum=9),
            a_running=r.get_int("a_running", minimum=0),
            station_count=r.get_int("station_count", minimum=0),
        )
        for r in json_records(raw)
    )
    return PlanetaryKIndex(values=values, source_url=source_url)


def _forecast_status(record: Record) -> KpForecastStatus:
    text = record.get_str("observed")
    try:
        return KpForecastStatus(text)
    except ValueError:
        raise record.error(f"unknown status {text!r}", "observed") from None


def parse_planetary_k_index_forecast(
    raw: str | bytes, *, source_url: str = PLANETARY_K_INDEX_FORECAST_URL
) -> PlanetaryKIndexForecast:
    """Parse ``noaa-planetary-k-index-forecast.json``.

    The product holds the observed Kp of the past week, a few estimated
    values and the forecast for the next three days, each flagged by its
    ``observed`` field.

    Args:
        raw: The content, current or old format.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If a value is missing or inconsistent.
    """
    values = _in_time_order(
        KpForecastValue(
            time=r.get_time("time_tag"),
            kp=r.get_float("kp", minimum=0, maximum=9),
            status=_forecast_status(r),
            noaa_scale=r.get_optional_str("noaa_scale"),
        )
        for r in json_records(raw)
    )
    return PlanetaryKIndexForecast(values=values, source_url=source_url)


def _kp_label(record: Record) -> str:
    label = record.get_str("kp")
    if not _KP_LABEL.fullmatch(label):
        raise record.error(f"expected a label like '3M', got {label!r}", "kp")
    return label


def parse_planetary_k_index_1m(
    raw: str | bytes, *, source_url: str = PLANETARY_K_INDEX_1M_URL
) -> PlanetaryKIndex1m:
    """Parse ``planetary_k_index_1m.json`` (1-minute Kp estimates).

    Args:
        raw: The content. A leading byte order mark is accepted.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If a value is missing or inconsistent.
    """
    values = _in_time_order(
        Kp1mValue(
            time=r.get_time("time_tag"),
            kp_index=r.get_int("kp_index", minimum=0, maximum=9),
            estimated_kp=r.get_float("estimated_kp", minimum=0, maximum=9),
            kp=_kp_label(r),
        )
        for r in json_records(raw)
    )
    return PlanetaryKIndex1m(values=values, source_url=source_url)


def parse_kyoto_dst(raw: str | bytes, *, source_url: str = KYOTO_DST_URL) -> KyotoDst:
    """Parse ``kyoto-dst.json`` (hourly Dst of the last week).

    Args:
        raw: The content, current or old format.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If a value is missing or inconsistent.
    """
    values = _in_time_order(
        DstValue(time=r.get_time("time_tag"), dst=r.get_int("dst"))
        for r in json_records(raw)
    )
    return KyotoDst(values=values, source_url=source_url)


def parse_f107_flux_30_day(
    raw: str | bytes, *, source_url: str = F107_FLUX_30_DAY_URL
) -> F107Flux:
    """Parse ``10cm-flux-30-day.json`` (daily F10.7 of the last 30 days).

    Args:
        raw: The content, current or old format.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If a value is missing or inconsistent.
    """
    values = _in_time_order(
        F107Value(time=r.get_time("time_tag"), flux=r.get_float("flux", minimum=0))
        for r in json_records(raw)
    )
    return F107Flux(values=values, source_url=source_url)


def _group(day: str, entry: dict[str, Any], name: str) -> Record:
    group = entry.get(name)
    if not isinstance(group, dict):
        raise ParseError(f"expected an object, got {group!r}", field=f"{day}.{name}")
    return _ScalesRecord(f"{day}.{name}.", group)


class _ScalesRecord(Record):
    """A group of ``noaa-scales.json``, whose errors name ``day.group.key``."""

    __slots__ = ("prefix",)

    def __init__(self, prefix: str, data: dict[str, Any]) -> None:
        super().__init__(0, data)
        self.prefix = prefix

    def error(self, message: str, field: str) -> ParseError:
        return ParseError(message, field=f"{self.prefix}{field}")

    def missing(self, field: str) -> SwpcError:
        return self.error("missing field", field)


def _scales_day(day: str, entry: object) -> NoaaScalesDay:
    if not isinstance(entry, dict):
        raise ParseError(f"expected an object, got {entry!r}", field=day)
    stamp = _ScalesRecord(f"{day}.", entry)
    try:
        time = parse_time(f"{stamp.get_str('DateStamp')}T{stamp.get_str('TimeStamp')}")
    except ValueError as exc:
        raise ParseError(str(exc), field=f"{day}.DateStamp") from None
    r, s, g = (_group(day, entry, name) for name in ("R", "S", "G"))
    return NoaaScalesDay(
        day=int(day),
        time=time,
        r=RadioBlackoutScale(
            scale=r.get_optional_int("Scale", minimum=0, maximum=5),
            text=r.get_optional_str("Text"),
            minor_prob=r.get_optional_int("MinorProb", minimum=0, maximum=100),
            major_prob=r.get_optional_int("MajorProb", minimum=0, maximum=100),
        ),
        s=SolarRadiationScale(
            scale=s.get_optional_int("Scale", minimum=0, maximum=5),
            text=s.get_optional_str("Text"),
            prob=s.get_optional_int("Prob", minimum=0, maximum=100),
        ),
        g=GeomagneticStormScale(
            scale=g.get_optional_int("Scale", minimum=0, maximum=5),
            text=g.get_optional_str("Text"),
        ),
    )


def parse_noaa_scales(
    raw: str | bytes, *, source_url: str = NOAA_SCALES_URL
) -> NoaaScales:
    """Parse ``noaa-scales.json`` (recent, current and forecast scale levels).

    Errors name the field as ``day.group.key``, for example ``0.G.Scale``.

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty, truncated or has no days.
        UnexpectedContent: If the content is not a JSON object.
        ParseError: If an entry is missing or inconsistent, or no entry
            is observed (key 0 or below).
    """
    document = load_json(raw)
    if not isinstance(document, dict):
        raise UnexpectedContent(
            f"expected a JSON object of days, got {type(document).__name__}"
        )
    if not document:
        raise SourceNotReady("no days")
    days = []
    for key, entry in document.items():
        if not _SCALE_DAY.fullmatch(key):
            raise ParseError(f"expected a day number, got {key!r}", field=key)
        days.append(_scales_day(key, entry))
    if not any(d.day <= 0 for d in days):
        raise ParseError("no observed entry (day 0 or below)")
    return NoaaScales(
        days=tuple(sorted(days, key=lambda d: d.day)), source_url=source_url
    )
