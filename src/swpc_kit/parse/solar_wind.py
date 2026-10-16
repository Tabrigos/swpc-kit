"""Parsers for the real-time solar wind (RTSW) products.

``rtsw_mag_1m.json`` and ``rtsw_wind_1m.json`` are arrays of objects, newest
first, with the records of every source mixed together. The parsers keep
every record, sort them oldest first (records with the same time keep the
file order) and turn ``null`` into ``None``. Choosing the active source is
left to the models (:meth:`~swpc_kit.models.solar_wind.RtswMag1m.active_series`
and friends).
"""

from swpc_kit.models.solar_wind import (
    RtswMag1m,
    RtswMagSample,
    RtswWind1m,
    RtswWindSample,
)
from swpc_kit.parse._common import Record, json_records

RTSW_MAG_1M_URL = "https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json"
RTSW_WIND_1M_URL = "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json"

_COMPONENTS = ("vx_gse", "vy_gse", "vz_gse", "vx_gsm", "vy_gsm", "vz_gsm")


def _mag_sample(r: Record) -> RtswMagSample:
    return RtswMagSample(
        time=r.get_time("time_tag"),
        source=r.get_str("source"),
        active=r.get_bool("active"),
        bt=r.get_optional_float("bt", minimum=0),
        bx_gse=r.get_optional_float("bx_gse"),
        by_gse=r.get_optional_float("by_gse"),
        bz_gse=r.get_optional_float("bz_gse"),
        theta_gse=r.get_optional_float("theta_gse", minimum=-90, maximum=90),
        phi_gse=r.get_optional_float("phi_gse", minimum=0, maximum=360),
        bx_gsm=r.get_optional_float("bx_gsm"),
        by_gsm=r.get_optional_float("by_gsm"),
        bz_gsm=r.get_optional_float("bz_gsm"),
        theta_gsm=r.get_optional_float("theta_gsm", minimum=-90, maximum=90),
        phi_gsm=r.get_optional_float("phi_gsm", minimum=0, maximum=360),
        manual_mode=r.get_optional_bool("manual_mode"),
        sample_size=r.get_optional_int("sample_size", minimum=0),
        max_telemetry_flag=r.get_optional_int("max_telemetry_flag"),
        max_data_flag=r.get_optional_int("max_data_flag"),
        overall_quality=r.get_optional_int("overall_quality"),
    )


def parse_rtsw_mag_1m(
    raw: str | bytes, *, source_url: str = RTSW_MAG_1M_URL
) -> RtswMag1m:
    """Parse ``rtsw_mag_1m.json`` (one-minute magnetic field, every source).

    The ``range``, ``scale`` and ``sensitivity`` fields are not read: they
    were ``null`` in every record seen and SWPC does not document them.

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If a value is missing or inconsistent (a negative field
            strength, an angle out of range, a non-boolean ``active``).
    """
    values = sorted((_mag_sample(r) for r in json_records(raw)), key=lambda v: v.time)
    return RtswMag1m(values=tuple(values), source_url=source_url)


def _wind_sample(r: Record) -> RtswWindSample:
    species = {}
    for name in ("proton", "alpha"):
        species[f"{name}_speed"] = r.get_optional_float(f"{name}_speed", minimum=0)
        species[f"{name}_temperature"] = r.get_optional_float(
            f"{name}_temperature", minimum=0
        )
        species[f"{name}_density"] = r.get_optional_float(f"{name}_density", minimum=0)
        for component in _COMPONENTS:
            species[f"{name}_{component}"] = r.get_optional_float(f"{name}_{component}")
    return RtswWindSample(
        time=r.get_time("time_tag"),
        source=r.get_str("source"),
        active=r.get_bool("active"),
        proton_speed=species["proton_speed"],
        proton_temperature=species["proton_temperature"],
        proton_density=species["proton_density"],
        proton_vx_gse=species["proton_vx_gse"],
        proton_vy_gse=species["proton_vy_gse"],
        proton_vz_gse=species["proton_vz_gse"],
        proton_vx_gsm=species["proton_vx_gsm"],
        proton_vy_gsm=species["proton_vy_gsm"],
        proton_vz_gsm=species["proton_vz_gsm"],
        proton_sample_size=r.get_optional_int("proton_sample_size", minimum=0),
        alpha_speed=species["alpha_speed"],
        alpha_temperature=species["alpha_temperature"],
        alpha_density=species["alpha_density"],
        alpha_vx_gse=species["alpha_vx_gse"],
        alpha_vy_gse=species["alpha_vy_gse"],
        alpha_vz_gse=species["alpha_vz_gse"],
        alpha_vx_gsm=species["alpha_vx_gsm"],
        alpha_vy_gsm=species["alpha_vy_gsm"],
        alpha_vz_gsm=species["alpha_vz_gsm"],
        alpha_sample_size=r.get_optional_int("alpha_sample_size", minimum=0),
        max_convergence_flag=r.get_optional_int("max_convergence_flag"),
        max_data_flag=r.get_optional_int("max_data_flag"),
        max_error_count_flag=r.get_optional_int("max_error_count_flag"),
        max_processing_flag=r.get_optional_int("max_processing_flag"),
        max_range_flag=r.get_optional_int("max_range_flag"),
        max_sample_count_flag=r.get_optional_int("max_sample_count_flag"),
        max_telemetry_flag=r.get_optional_int("max_telemetry_flag"),
        overall_quality=r.get_optional_int("overall_quality"),
    )


def parse_rtsw_wind_1m(
    raw: str | bytes, *, source_url: str = RTSW_WIND_1M_URL
) -> RtswWind1m:
    """Parse ``rtsw_wind_1m.json`` (one-minute plasma, every source).

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not this product.
        ParseError: If a value is missing or inconsistent (a negative speed,
            density or temperature, a non-boolean ``active``).
    """
    values = sorted((_wind_sample(r) for r in json_records(raw)), key=lambda v: v.time)
    return RtswWind1m(values=tuple(values), source_url=source_url)
