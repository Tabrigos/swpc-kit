"""Parsers for the GOES X-ray and integral proton products.

The JSON files are arrays of objects, oldest first, one object per time and
per band (X-rays) or energy threshold (protons). The parsers keep every
record, sort them oldest first (records with the same time keep the file
order) and turn ``null`` into ``None``.

The default URLs are the one-day files of the primary satellite. The
``6-hour``, ``3-day`` and ``7-day`` files and the ``secondary`` folder are
expected to share the format, but only the one-day primary files have been
checked (see ``docs/FONTI.md``).
"""

import re

from swpc_kit.models.goes import (
    GoesIntegralProtons,
    GoesXrays,
    ProtonSample,
    XraySample,
)
from swpc_kit.parse._common import Record, json_records, read_records

GOES_XRAYS_1_DAY_URL = (
    "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json"
)
GOES_INTEGRAL_PROTONS_1_DAY_URL = (
    "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json"
)

_THRESHOLD = re.compile(r">=\s*([0-9]+(?:\.[0-9]+)?)\s*MeV")

# Plausibility limits, far above anything measured: a value beyond them
# skips the record (docs/FONTI.md, "Plausibility limits").
_MAX_XRAY_FLUX = 0.1  # W/m² (X1000), about 35 times the strongest flare
_MAX_PROTON_FLUX = 1e8  # pfu


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


def _proton_sample(r: Record) -> ProtonSample:
    time = r.get_time("time_tag")
    satellite = r.get_int("satellite", minimum=0)
    energy = r.get_str("energy")
    match = _THRESHOLD.fullmatch(energy)
    if match is None:
        raise r.error(f"expected a threshold like '>=10 MeV', got {energy!r}", "energy")
    return ProtonSample(
        time=time,
        satellite=satellite,
        energy=energy,
        threshold_mev=float(match.group(1)),
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
