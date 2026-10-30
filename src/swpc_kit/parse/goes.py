"""Parsers for the GOES X-ray, integral proton and electron, and flare products.

The flux files are arrays of objects, oldest first, one object per time and
per band (X-rays) or energy threshold (protons, electrons). The parsers keep
every record, sort them oldest first (records with the same time keep the
file order) and turn ``null`` into ``None``.

The flare files are arrays of objects, one per flare: the flares of 7 days,
or one record with the latest flare and the class of the flux now. The list
holds ended flares only; the latest flare can be in progress, and then its
peak and end do not exist yet: they are read as absent only in the forms
seen in a real file, all together (D-026).

The default URLs are the files of the primary satellite: the one-day files
for the fluxes. The ``6-hour``, ``3-day`` and ``7-day`` flux files and the
``secondary`` folder are expected to share the format, but only the files
named here have been checked (see ``docs/FONTI.md``).
"""

import re
from dataclasses import replace

from swpc_kit.errors import UnexpectedContent
from swpc_kit.models.goes import (
    ElectronSample,
    FlareClass,
    GoesFlare,
    GoesFlares,
    GoesIntegralElectrons,
    GoesIntegralProtons,
    GoesLatestFlare,
    GoesXrays,
    ProtonSample,
    XraySample,
)
from swpc_kit.parse._common import Record, json_records, load_json, read_records

GOES_XRAYS_1_DAY_URL = (
    "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"
)
GOES_INTEGRAL_PROTONS_1_DAY_URL = (
    "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json"
)
GOES_INTEGRAL_ELECTRONS_1_DAY_URL = (
    "https://services.swpc.noaa.gov/json/goes/primary/integral-electrons-1-day.json"
)
GOES_XRAY_FLARES_7_DAY_URL = (
    "https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json"
)
GOES_XRAY_FLARE_LATEST_URL = (
    "https://services.swpc.noaa.gov/json/goes/primary/xray-flares-latest.json"
)

_THRESHOLD = re.compile(r">=\s*([0-9]+(?:\.[0-9]+)?)\s*MeV")

# Plausibility limits, far above anything measured: a value beyond them
# skips the record (docs/FONTI.md, "Plausibility limits").
_MAX_XRAY_FLUX = 0.1  # W/m² (X1000), about 35 times the strongest flare
_MAX_PROTON_FLUX = 1e8  # pfu
_MAX_ELECTRON_FLUX = 1e8  # pfu, as for protons; the fixtures stay below 3e3

# The peak and end of a flare in progress, which do not exist yet (D-026),
# as seen in the live `latest` file of 2026-10-30 (docs/FONTI.md).
_IN_PROGRESS = {
    "max_time": "Unk",
    "max_class": None,
    "max_xrlong": None,
    "end_time": "Unk",
    "end_class": None,
}


def _xray_sample(r: Record) -> XraySample:
    return XraySample(
        time=r.get_time("time_tag"),
        satellite=r.get_int("satellite", minimum=0),
        energy=r.get_str("energy"),
        flux=r.get_optional_float("flux", maximum=_MAX_XRAY_FLUX),
        observed_flux=r.get_optional_float("observed_flux", maximum=_MAX_XRAY_FLUX),
        electron_correction=r.get_optional_float("electron_correction"),
        electron_contamination=r.get_optional_bool("electron_contaminaton"),
    )


def parse_goes_xrays(
    raw: str | bytes, *, source_url: str = GOES_XRAYS_1_DAY_URL
) -> GoesXrays:
    """Parse a GOES X-ray flux file, such as ``xrays-1-day.json``.

    Bands are kept as written in ``energy``, including unknown ones. Fluxes
    are not range-checked: the corrected flux is the observed one minus the
    electron correction.

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If a value is missing or inconsistent.
    """
    read, skipped = read_records(json_records(raw), _xray_sample)
    values = sorted((v for _, v in read), key=lambda v: v.time)
    return GoesXrays(
        values=tuple(values), source_url=source_url, skipped=tuple(skipped)
    )


def _threshold(r: Record) -> tuple[str, float]:
    """The ``energy`` of an integral flux record, and its threshold in MeV."""
    energy = r.get_str("energy")
    match = _THRESHOLD.fullmatch(energy)
    if match is None:
        raise r.error(f"expected a threshold like '>=10 MeV', got {energy!r}", "energy")
    return energy, float(match.group(1))


def _proton_sample(r: Record) -> ProtonSample:
    time = r.get_time("time_tag")
    satellite = r.get_int("satellite", minimum=0)
    energy, threshold_mev = _threshold(r)
    return ProtonSample(
        time=time,
        satellite=satellite,
        energy=energy,
        threshold_mev=threshold_mev,
        flux=r.get_optional_float("flux", maximum=_MAX_PROTON_FLUX),
    )


def parse_goes_integral_protons(
    raw: str | bytes, *, source_url: str = GOES_INTEGRAL_PROTONS_1_DAY_URL
) -> GoesIntegralProtons:
    """Parse a GOES integral proton file, such as ``integral-protons-1-day.json``.

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If a value is missing or inconsistent, or an ``energy``
            is not a threshold like ``">=10 MeV"``.
    """
    read, skipped = read_records(json_records(raw), _proton_sample)
    values = sorted((v for _, v in read), key=lambda v: v.time)
    return GoesIntegralProtons(
        values=tuple(values), source_url=source_url, skipped=tuple(skipped)
    )


def _electron_sample(r: Record) -> ElectronSample:
    time = r.get_time("time_tag")
    satellite = r.get_int("satellite", minimum=0)
    energy, threshold_mev = _threshold(r)
    return ElectronSample(
        time=time,
        satellite=satellite,
        energy=energy,
        threshold_mev=threshold_mev,
        flux=r.get_optional_float("flux", maximum=_MAX_ELECTRON_FLUX),
    )


def parse_goes_integral_electrons(
    raw: str | bytes, *, source_url: str = GOES_INTEGRAL_ELECTRONS_1_DAY_URL
) -> GoesIntegralElectrons:
    """Parse a GOES integral electron file, such as ``integral-electrons-1-day.json``.

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If a value is missing or inconsistent, or an ``energy``
            is not a threshold like ``">=2 MeV"``.
    """
    read, skipped = read_records(json_records(raw), _electron_sample)
    values = sorted((v for _, v in read), key=lambda v: v.time)
    return GoesIntegralElectrons(
        values=tuple(values), source_url=source_url, skipped=tuple(skipped)
    )


def _class(r: Record, field: str) -> FlareClass:
    text = r.get_str(field)
    try:
        return FlareClass.parse(text)
    except ValueError as exc:
        raise r.error(str(exc), field) from None


def _flare(r: Record) -> GoesFlare:
    begin_time = r.get_time("begin_time")
    begin_class = _class(r, "begin_class")
    max_time = r.get_time("max_time")
    max_class = _class(r, "max_class")
    max_flux = r.get_float("max_xrlong", maximum=_MAX_XRAY_FLUX)
    if max_flux <= 0:
        raise r.error(f"expected a positive flux, got {max_flux}", "max_xrlong")
    end_time = r.get_time("end_time")
    end_class = _class(r, "end_class")
    satellite = r.get_int("satellite", minimum=0)
    if max_time < begin_time:
        raise r.error(f"peak at {max_time} before the beginning", "max_time")
    if end_time < max_time:
        raise r.error(f"end at {end_time} before the peak", "end_time")
    return GoesFlare(
        begin_time=begin_time,
        begin_class=begin_class,
        max_time=max_time,
        max_class=max_class,
        max_flux=max_flux,
        end_time=end_time,
        end_class=end_class,
        satellite=satellite,
    )


def parse_goes_xray_flares(
    raw: str | bytes, *, source_url: str = GOES_XRAY_FLARES_7_DAY_URL
) -> GoesFlares:
    """Parse a GOES flare list, such as ``xray-flares-7-day.json``.

    The list holds ended flares only: a record without a peak or an end, or
    whose peak comes before its beginning, or its end before its peak, is
    skipped.

    Args:
        raw: The content. An empty array gives a model without flares.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If no flare can be read (the error of the first one).
    """
    if load_json(raw) == []:
        return GoesFlares(values=(), source_url=source_url)
    read, skipped = read_records(json_records(raw), _flare)
    values = sorted((v for _, v in read), key=lambda v: v.begin_time)
    return GoesFlares(
        values=tuple(values), source_url=source_url, skipped=tuple(skipped)
    )


def _latest(r: Record) -> GoesLatestFlare:
    time = r.get_time("time_tag")
    satellite = r.get_int("satellite", minimum=0)
    current_class = _class(r, "current_class")
    begin_time = r.get_time("begin_time")
    begin_class = _class(r, "begin_class")
    # In progress only with every field empty: any other mix is read as an
    # ended flare, so the first empty field is the error.
    in_progress = all(r.is_empty(f, (form,)) for f, form in _IN_PROGRESS.items())
    return GoesLatestFlare(
        time=time,
        satellite=satellite,
        current_class=current_class,
        begin_time=begin_time,
        begin_class=begin_class,
        flare=None if in_progress else _flare(r),
        source_url="",  # set by the parser, which knows it
    )


def parse_goes_xray_flare_latest(
    raw: str | bytes, *, source_url: str = GOES_XRAY_FLARE_LATEST_URL
) -> GoesLatestFlare:
    """Parse ``xray-flares-latest.json``: the latest flare and the class now.

    The file holds one record: the flare in progress, or the last one if
    none is, with the class of the flux when the file was written. A flare
    in progress has ``flare`` ``None``: its ``max_time``, ``max_class``,
    ``max_xrlong``, ``end_time`` and ``end_class`` are ``"Unk"`` or
    ``null``, all of them; a record with only some of them empty is a
    ``ParseError``.

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty, truncated or has no record.
        UnexpectedContent: If the content is not this product, holds more
            than one record, or its record lacks a field (with one record,
            a missing field is missing from every record).
        ParseError: If a value of the record is inconsistent.
    """
    records = json_records(raw)
    if len(records) != 1:
        raise UnexpectedContent(f"expected one record, got {len(records)}")
    ((_, latest),), _ = read_records(records, _latest)
    return replace(latest, source_url=source_url)
