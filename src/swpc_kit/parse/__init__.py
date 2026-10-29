"""Parsers: pure functions from raw SWPC content to models.

Each parser takes ``str`` or ``bytes`` and returns a model from
:mod:`swpc_kit.models`. Parsers do no I/O and use only the standard library.
They accept every documented format of a product, old and new, and raise the
errors of :mod:`swpc_kit.errors` on bad input.
"""

from swpc_kit.parse.alerts import parse_alerts
from swpc_kit.parse.bulletins import (
    parse_27_day_outlook,
    parse_geomagnetic_forecast,
    parse_three_day_forecast,
)
from swpc_kit.parse.goes import (
    parse_goes_integral_electrons,
    parse_goes_integral_protons,
    parse_goes_xray_flare_latest,
    parse_goes_xray_flares,
    parse_goes_xrays,
)
from swpc_kit.parse.grids import (
    parse_drap_global_frequencies,
    parse_ovation_aurora,
)
from swpc_kit.parse.indices import (
    parse_f107_flux_30_day,
    parse_kyoto_dst,
    parse_noaa_scales,
    parse_planetary_k_index,
    parse_planetary_k_index_1m,
    parse_planetary_k_index_forecast,
)
from swpc_kit.parse.solar_wind import (
    parse_rtsw_mag_1m,
    parse_rtsw_wind_1m,
)

__all__ = [
    "parse_27_day_outlook",
    "parse_alerts",
    "parse_drap_global_frequencies",
    "parse_f107_flux_30_day",
    "parse_geomagnetic_forecast",
    "parse_goes_integral_electrons",
    "parse_goes_integral_protons",
    "parse_goes_xray_flare_latest",
    "parse_goes_xray_flares",
    "parse_goes_xrays",
    "parse_kyoto_dst",
    "parse_noaa_scales",
    "parse_ovation_aurora",
    "parse_planetary_k_index",
    "parse_planetary_k_index_1m",
    "parse_planetary_k_index_forecast",
    "parse_rtsw_mag_1m",
    "parse_rtsw_wind_1m",
    "parse_three_day_forecast",
]
