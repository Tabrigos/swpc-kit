"""Parsers for the solar flare probabilities and the solar active regions.

Both files are arrays of objects, newest first: one object per day of issue
(``solar_probabilities.json``), one per region and day of observation
(``solar_regions.json``). The parsers sort them oldest first and keep one
value per day, or per region and day: a record that repeats one is skipped.

A region without spots has its five sunspot fields empty: they are read as
absent only all together and in the forms seen in a real file (D-025,
D-028, ``docs/FONTI.md``).
"""

import re
from collections.abc import Callable, Hashable
from datetime import date

from swpc_kit.models.records import SkippedRecord
from swpc_kit.models.solar import (
    SolarProbabilities,
    SolarProbability,
    SolarRegion,
    SolarRegions,
)
from swpc_kit.parse._common import Record, json_records, read_records

SOLAR_PROBABILITIES_URL = "https://services.swpc.noaa.gov/json/solar_probabilities.json"
SOLAR_REGIONS_URL = "https://services.swpc.noaa.gov/json/solar_regions.json"

_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
# The day of issue is written as its midnight, without a zone.
_ISSUE_DAY = re.compile(r"(\d{4}-\d{2}-\d{2})T00:00:00")

# The sunspot fields of a region without spots, as seen in the file of
# 2026-11-04 (docs/FONTI.md): null, or "" in the two classes; always all
# five together (D-028).
_NO_SPOTS: dict[str, tuple[object, ...]] = {
    "spot_class": (None, ""),
    "mag_class": (None, ""),
    "area": (None,),
    "extent": (None,),
    "number_spots": (None,),
}


def _day(r: Record, field: str, pattern: re.Pattern[str]) -> date:
    text = r.get_str(field)
    match = pattern.fullmatch(text)
    try:
        if match is None:
            raise ValueError
        return date.fromisoformat(match.group(match.re.groups))
    except ValueError:
        raise r.error(f"not a day: {text!r}", field) from None


def _text(r: Record, field: str) -> str:
    text = r.get_str(field)
    if not text:
        raise r.error("expected a non-empty string", field)
    return text


def _percent(r: Record, field: str) -> int:
    return r.get_int(field, minimum=0, maximum=100)


def _three_days(r: Record, prefix: str) -> tuple[int, int, int]:
    return (
        _percent(r, f"{prefix}_1_day"),
        _percent(r, f"{prefix}_2_day"),
        _percent(r, f"{prefix}_3_day"),
    )


def _once[V](
    read: list[tuple[int, V]],
    skipped: list[SkippedRecord],
    key: Callable[[V], Hashable],
    field: str,
) -> list[V]:
    """Keep the first value of each key; skip the records that repeat one."""
    first: dict[Hashable, int] = {}
    values = []
    for index, value in read:
        earlier = first.setdefault(key(value), index)
        if earlier == index:
            values.append(value)
        else:
            skipped.append(
                SkippedRecord(
                    index=index,
                    field=field,
                    reason=f"{key(value)} appears twice (first in record {earlier})",
                )
            )
    skipped.sort(key=lambda s: s.index)
    return values


def _probability(r: Record) -> SolarProbability:
    return SolarProbability(
        day=_day(r, "date", _ISSUE_DAY),
        c_class=_three_days(r, "c_class"),
        m_class=_three_days(r, "m_class"),
        x_class=_three_days(r, "x_class"),
        proton_10mev=_three_days(r, "10mev_protons"),
        polar_cap_absorption=_text(r, "polar_cap_absorption"),
    )


def parse_solar_probabilities(
    raw: str | bytes, *, source_url: str = SOLAR_PROBABILITIES_URL
) -> SolarProbabilities:
    """Parse ``solar_probabilities.json``: flare and proton probabilities.

    One entry per day of issue, about 30 days, oldest first in the model.

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If no record can be read (the error of the first one).
    """
    read, skipped = read_records(json_records(raw), _probability)
    values = _once(read, skipped, lambda v: v.day.isoformat(), "date")
    values.sort(key=lambda v: v.day)
    return SolarProbabilities(
        values=tuple(values), source_url=source_url, skipped=tuple(skipped)
    )


type _Spots = tuple[str | None, str | None, int | None, int | None, int | None]


def _spots(r: Record) -> _Spots:
    """The five sunspot fields: all ``None`` only if all are empty (D-028).

    Any other mix is read as a region with spots, so the first empty field
    is the error.
    """
    if all(r.is_empty(field, forms) for field, forms in _NO_SPOTS.items()):
        return None, None, None, None, None
    return (
        _text(r, "spot_class"),
        _text(r, "mag_class"),
        r.get_int("area", minimum=0),
        r.get_int("extent", minimum=0),
        r.get_int("number_spots", minimum=0),
    )


def _region(r: Record) -> SolarRegion:
    day = _day(r, "observed_date", _DAY)
    region = r.get_int("region", minimum=0)
    latitude = r.get_int("latitude", minimum=-90, maximum=90)
    longitude = r.get_int("longitude", minimum=-180, maximum=180)
    location = _text(r, "location")
    carrington_longitude = r.get_int("carrington_longitude", minimum=0, maximum=360)
    status = None if r.is_empty("status", (None,)) else _text(r, "status")
    spot_class, mag_class, area, extent, number_spots = _spots(r)
    return SolarRegion(
        day=day,
        region=region,
        latitude=latitude,
        longitude=longitude,
        location=location,
        carrington_longitude=carrington_longitude,
        status=status,
        spot_class=spot_class,
        mag_class=mag_class,
        area=area,
        extent=extent,
        number_spots=number_spots,
        c_xray_events=r.get_int("c_xray_events", minimum=0),
        m_xray_events=r.get_int("m_xray_events", minimum=0),
        x_xray_events=r.get_int("x_xray_events", minimum=0),
        c_flare_probability=_percent(r, "c_flare_probability"),
        m_flare_probability=_percent(r, "m_flare_probability"),
        x_flare_probability=_percent(r, "x_flare_probability"),
        proton_probability=_percent(r, "proton_probability"),
        first_date=r.get_time("first_date"),
    )


def parse_solar_regions(
    raw: str | bytes, *, source_url: str = SOLAR_REGIONS_URL
) -> SolarRegions:
    """Parse ``solar_regions.json``: the active regions of about 30 days.

    A region without spots on a day has ``spot_class``, ``mag_class``,
    ``area``, ``extent`` and ``number_spots`` ``None``. They are read as
    absent only all five together, each ``null`` or ``""`` for the two
    classes; with only some of them empty the record is skipped (D-028).

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If no record can be read (the error of the first one).
    """
    read, skipped = read_records(json_records(raw), _region)
    values = _once(
        read, skipped, lambda v: f"region {v.region} on {v.day.isoformat()}", "region"
    )
    values.sort(key=lambda v: (v.day, v.region))
    return SolarRegions(
        values=tuple(values), source_url=source_url, skipped=tuple(skipped)
    )
