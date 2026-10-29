"""The products the clients fetch: URL and parser of each."""

from typing import Any

from swpc_kit.client._core import Product
from swpc_kit.parse.alerts import (
    ALERTS_URL,
    parse_alerts,
)
from swpc_kit.parse.bulletins import (
    GEOMAGNETIC_FORECAST_URL,
    THREE_DAY_FORECAST_URL,
    TWENTY_SEVEN_DAY_OUTLOOK_URL,
    parse_27_day_outlook,
    parse_geomagnetic_forecast,
    parse_three_day_forecast,
)
from swpc_kit.parse.goes import (
    GOES_INTEGRAL_ELECTRONS_1_DAY_URL,
    GOES_INTEGRAL_PROTONS_1_DAY_URL,
    GOES_XRAY_FLARE_LATEST_URL,
    GOES_XRAY_FLARES_7_DAY_URL,
    GOES_XRAYS_1_DAY_URL,
    parse_goes_integral_electrons,
    parse_goes_integral_protons,
    parse_goes_xray_flare_latest,
    parse_goes_xray_flares,
    parse_goes_xrays,
)
from swpc_kit.parse.grids import (
    DRAP_GLOBAL_FREQUENCIES_URL,
    OVATION_AURORA_URL,
    parse_drap_global_frequencies,
    parse_ovation_aurora,
)
from swpc_kit.parse.indices import (
    F107_FLUX_30_DAY_URL,
    KYOTO_DST_URL,
    NOAA_SCALES_URL,
    PLANETARY_K_INDEX_1M_URL,
    PLANETARY_K_INDEX_FORECAST_URL,
    PLANETARY_K_INDEX_URL,
    parse_f107_flux_30_day,
    parse_kyoto_dst,
    parse_noaa_scales,
    parse_planetary_k_index,
    parse_planetary_k_index_1m,
    parse_planetary_k_index_forecast,
)
from swpc_kit.parse.solar_wind import (
    RTSW_MAG_1M_URL,
    RTSW_WIND_1M_URL,
    parse_rtsw_mag_1m,
    parse_rtsw_wind_1m,
)

PLANETARY_K_INDEX = Product(
    "planetary_k_index",
    PLANETARY_K_INDEX_URL,
    lambda raw, url: parse_planetary_k_index(raw, source_url=url),
)
PLANETARY_K_INDEX_FORECAST = Product(
    "planetary_k_index_forecast",
    PLANETARY_K_INDEX_FORECAST_URL,
    lambda raw, url: parse_planetary_k_index_forecast(raw, source_url=url),
)
PLANETARY_K_INDEX_1M = Product(
    "planetary_k_index_1m",
    PLANETARY_K_INDEX_1M_URL,
    lambda raw, url: parse_planetary_k_index_1m(raw, source_url=url),
)
KYOTO_DST = Product(
    "kyoto_dst", KYOTO_DST_URL, lambda raw, url: parse_kyoto_dst(raw, source_url=url)
)
F107_FLUX_30_DAY = Product(
    "f107_flux_30_day",
    F107_FLUX_30_DAY_URL,
    lambda raw, url: parse_f107_flux_30_day(raw, source_url=url),
)
NOAA_SCALES = Product(
    "noaa_scales",
    NOAA_SCALES_URL,
    lambda raw, url: parse_noaa_scales(raw, source_url=url),
)
RTSW_MAG_1M = Product(
    "rtsw_mag_1m",
    RTSW_MAG_1M_URL,
    lambda raw, url: parse_rtsw_mag_1m(raw, source_url=url),
)
RTSW_WIND_1M = Product(
    "rtsw_wind_1m",
    RTSW_WIND_1M_URL,
    lambda raw, url: parse_rtsw_wind_1m(raw, source_url=url),
)
GOES_XRAYS = Product(
    "goes_xrays",
    GOES_XRAYS_1_DAY_URL,
    lambda raw, url: parse_goes_xrays(raw, source_url=url),
)
GOES_INTEGRAL_PROTONS = Product(
    "goes_integral_protons",
    GOES_INTEGRAL_PROTONS_1_DAY_URL,
    lambda raw, url: parse_goes_integral_protons(raw, source_url=url),
)
GOES_INTEGRAL_ELECTRONS = Product(
    "goes_integral_electrons",
    GOES_INTEGRAL_ELECTRONS_1_DAY_URL,
    lambda raw, url: parse_goes_integral_electrons(raw, source_url=url),
)
GOES_XRAY_FLARES = Product(
    "goes_xray_flares",
    GOES_XRAY_FLARES_7_DAY_URL,
    lambda raw, url: parse_goes_xray_flares(raw, source_url=url),
)
GOES_XRAY_FLARE_LATEST = Product(
    "goes_xray_flare_latest",
    GOES_XRAY_FLARE_LATEST_URL,
    lambda raw, url: parse_goes_xray_flare_latest(raw, source_url=url),
)
ALERTS = Product(
    "alerts", ALERTS_URL, lambda raw, url: parse_alerts(raw, source_url=url)
)
THREE_DAY_FORECAST = Product(
    "three_day_forecast",
    THREE_DAY_FORECAST_URL,
    lambda raw, url: parse_three_day_forecast(raw, source_url=url),
)
GEOMAGNETIC_FORECAST = Product(
    "geomagnetic_forecast",
    GEOMAGNETIC_FORECAST_URL,
    lambda raw, url: parse_geomagnetic_forecast(raw, source_url=url),
)
TWENTY_SEVEN_DAY_OUTLOOK = Product(
    "twenty_seven_day_outlook",
    TWENTY_SEVEN_DAY_OUTLOOK_URL,
    lambda raw, url: parse_27_day_outlook(raw, source_url=url),
)
OVATION_AURORA = Product(
    "ovation_aurora",
    OVATION_AURORA_URL,
    lambda raw, url: parse_ovation_aurora(raw, source_url=url),
)
DRAP_GLOBAL_FREQUENCIES = Product(
    "drap_global_frequencies",
    DRAP_GLOBAL_FREQUENCIES_URL,
    lambda raw, url: parse_drap_global_frequencies(raw, source_url=url),
)

PRODUCTS: tuple[Product[Any], ...] = (
    PLANETARY_K_INDEX,
    PLANETARY_K_INDEX_FORECAST,
    PLANETARY_K_INDEX_1M,
    KYOTO_DST,
    F107_FLUX_30_DAY,
    NOAA_SCALES,
    RTSW_MAG_1M,
    RTSW_WIND_1M,
    GOES_XRAYS,
    GOES_INTEGRAL_PROTONS,
    GOES_INTEGRAL_ELECTRONS,
    GOES_XRAY_FLARES,
    GOES_XRAY_FLARE_LATEST,
    ALERTS,
    THREE_DAY_FORECAST,
    GEOMAGNETIC_FORECAST,
    TWENTY_SEVEN_DAY_OUTLOOK,
    OVATION_AURORA,
    DRAP_GLOBAL_FREQUENCIES,
)
"""Every product, in the order of ``docs/TAPPE.md``."""
