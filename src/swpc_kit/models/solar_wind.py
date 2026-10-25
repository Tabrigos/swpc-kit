"""Models for the real-time solar wind (RTSW) at L1.

SWPC publishes one-minute averages of the interplanetary magnetic field
(``rtsw_mag_1m.json``) and of the solar wind plasma (``rtsw_wind_1m.json``)
from several spacecraft at once. Each record names its ``source`` and says
whether it is the ``active`` one, the source SWPC uses for its products. A
minute can have records from several sources, from inactive sources only,
or none at all.

Times are UTC. SWPC writes the ``time_tag`` values without a time zone; they
are read as UTC.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from swpc_kit.models._checks import check_utc, check_values


class RtswSource(StrEnum):
    """Spacecraft names seen in the ``source`` field (October 2026).

    Samples keep ``source`` as a plain string, so a name SWPC adds later does
    not break parsing; these members compare equal to those strings.
    """

    SOLAR1 = "SOLAR1"
    """SWFO-L1 (SOLAR-1), the primary source since 2026-06-30."""
    ACE = "ACE"
    """ACE, the backup source."""
    IMAP = "IMAP"
    """IMAP, published but inactive in October 2026."""


@dataclass(frozen=True, slots=True)
class RtswMagSample:
    """One one-minute record of the interplanetary magnetic field.

    Field names follow the source. Physical values are ``None`` when the
    source writes ``null``.

    Attributes:
        time: Time of the record. Not always on the minute (IMAP).
        source: Spacecraft, such as ``"SOLAR1"`` (see :class:`RtswSource`).
        active: Whether this source is the one SWPC uses at this time.
        bt: Total field strength in nT.
        bx_gse: X component in GSE coordinates, nT.
        by_gse: Y component in GSE coordinates, nT.
        bz_gse: Z component in GSE coordinates, nT.
        theta_gse: Latitude of the field in GSE, degrees, -90 to 90.
        phi_gse: Longitude of the field in GSE, degrees, 0 to 360.
        bx_gsm: X component in GSM coordinates, nT.
        by_gsm: Y component in GSM coordinates, nT.
        bz_gsm: Z component in GSM coordinates, nT.
        theta_gsm: Latitude of the field in GSM, degrees, -90 to 90.
        phi_gsm: Longitude of the field in GSM, degrees, 0 to 360.
        manual_mode: ``manual_mode`` flag of the source.
        sample_size: Number of measurements averaged.
        max_telemetry_flag: Worst telemetry flag in the minute.
        max_data_flag: Worst data flag in the minute, as written; SOLAR1 and
            ACE write ``-9999``, which looks like a fill value.
        overall_quality: Overall quality flag (0 in every record seen).
    """

    time: datetime
    source: str
    active: bool
    bt: float | None
    bx_gse: float | None
    by_gse: float | None
    bz_gse: float | None
    theta_gse: float | None
    phi_gse: float | None
    bx_gsm: float | None
    by_gsm: float | None
    bz_gsm: float | None
    theta_gsm: float | None
    phi_gsm: float | None
    manual_mode: bool | None
    sample_size: int | None
    max_telemetry_flag: int | None
    max_data_flag: int | None
    overall_quality: int | None

    def __post_init__(self) -> None:
        check_utc("time", self.time)


@dataclass(frozen=True, slots=True)
class RtswWindSample:
    """One one-minute record of the solar wind plasma.

    Field names follow the source. Physical values are ``None`` when the
    source writes ``null``: in October 2026 ACE and IMAP give no velocity
    components and no source gives alpha particle values.

    Attributes:
        time: Time of the record. Not always on the minute (IMAP).
        source: Spacecraft, such as ``"SOLAR1"`` (see :class:`RtswSource`).
        active: Whether this source is the one SWPC uses at this time.
        proton_speed: Bulk proton speed in km/s.
        proton_temperature: Proton temperature in K.
        proton_density: Proton density in cm⁻³.
        proton_vx_gse: Proton velocity, X in GSE, km/s.
        proton_vy_gse: Proton velocity, Y in GSE, km/s.
        proton_vz_gse: Proton velocity, Z in GSE, km/s.
        proton_vx_gsm: Proton velocity, X in GSM, km/s.
        proton_vy_gsm: Proton velocity, Y in GSM, km/s.
        proton_vz_gsm: Proton velocity, Z in GSM, km/s.
        proton_sample_size: Number of proton measurements averaged.
        alpha_speed: Alpha particle speed in km/s.
        alpha_temperature: Alpha particle temperature in K.
        alpha_density: Alpha particle density in cm⁻³.
        alpha_vx_gse: Alpha velocity, X in GSE, km/s.
        alpha_vy_gse: Alpha velocity, Y in GSE, km/s.
        alpha_vz_gse: Alpha velocity, Z in GSE, km/s.
        alpha_vx_gsm: Alpha velocity, X in GSM, km/s.
        alpha_vy_gsm: Alpha velocity, Y in GSM, km/s.
        alpha_vz_gsm: Alpha velocity, Z in GSM, km/s.
        alpha_sample_size: Number of alpha measurements averaged.
        max_convergence_flag: Worst convergence flag in the minute.
        max_data_flag: Worst data flag in the minute.
        max_error_count_flag: Worst error count flag in the minute.
        max_processing_flag: Worst processing flag in the minute.
        max_range_flag: Worst range flag in the minute.
        max_sample_count_flag: Worst sample count flag in the minute.
        max_telemetry_flag: Worst telemetry flag in the minute.
        overall_quality: Overall quality flag (0 in every record seen).
    """

    time: datetime
    source: str
    active: bool
    proton_speed: float | None
    proton_temperature: float | None
    proton_density: float | None
    proton_vx_gse: float | None
    proton_vy_gse: float | None
    proton_vz_gse: float | None
    proton_vx_gsm: float | None
    proton_vy_gsm: float | None
    proton_vz_gsm: float | None
    proton_sample_size: int | None
    alpha_speed: float | None
    alpha_temperature: float | None
    alpha_density: float | None
    alpha_vx_gse: float | None
    alpha_vy_gse: float | None
    alpha_vz_gse: float | None
    alpha_vx_gsm: float | None
    alpha_vy_gsm: float | None
    alpha_vz_gsm: float | None
    alpha_sample_size: int | None
    max_convergence_flag: int | None
    max_data_flag: int | None
    max_error_count_flag: int | None
    max_processing_flag: int | None
    max_range_flag: int | None
    max_sample_count_flag: int | None
    max_telemetry_flag: int | None
    overall_quality: int | None

    def __post_init__(self) -> None:
        check_utc("time", self.time)


class _Sample(Protocol):
    @property
    def time(self) -> datetime: ...

    @property
    def source(self) -> str: ...

    @property
    def active(self) -> bool: ...


class _RtswSeries[S: _Sample]:
    """Access by source and by active record, shared by the RTSW products."""

    __slots__ = ()

    values: tuple[S, ...]

    @property
    def data_time(self) -> datetime:
        """Time of the most recent active record.

        Freshness follows the active source, the only one to read as "the
        solar wind now": a backup that keeps running after the active source
        stopped does not make the data look new. With no active record at
        all, the time of the oldest record, since no time of the file has
        active data.
        """
        active = [v.time for v in self.values if v.active]
        return max(active) if active else min(v.time for v in self.values)

    @property
    def sources(self) -> tuple[str, ...]:
        """Names of the sources in the content, sorted."""
        return tuple(sorted({v.source for v in self.values}))

    def series(self, source: str) -> tuple[S, ...]:
        """Return the records of ``source``, oldest first (empty if none)."""
        return tuple(v for v in self.values if v.source == source)

    def active_series(self) -> tuple[S, ...]:
        """Return the active record of each time that has one, oldest first.

        Times with inactive records only are left out. If a time had more
        than one active record (not seen so far), the first one in the
        source file is taken.
        """
        chosen: dict[datetime, S] = {}
        for v in self.values:
            if v.active and v.time not in chosen:
                chosen[v.time] = v
        return tuple(chosen.values())

    def active_at(self, time: datetime) -> S | None:
        """Return the active record at exactly ``time``, or ``None``.

        ``None`` means there is no record at that time or only inactive ones.
        """
        return next((v for v in self.values if v.time == time and v.active), None)

    def latest_active(self) -> S | None:
        """Return the most recent active record, or ``None`` if there is none."""
        active = [v for v in self.values if v.active]
        if not active:
            return None
        latest = max(v.time for v in active)
        return next(v for v in active if v.time == latest)


@dataclass(frozen=True, slots=True)
class RtswMag1m(_RtswSeries[RtswMagSample]):
    """One-minute interplanetary magnetic field of the last 24 hours.

    Attributes:
        values: The records of every source, oldest first; records with the
            same time keep the order of the source file.
        source_url: Where the content came from.
    """

    values: tuple[RtswMagSample, ...]
    source_url: str

    def __post_init__(self) -> None:
        check_values(self.values)


@dataclass(frozen=True, slots=True)
class RtswWind1m(_RtswSeries[RtswWindSample]):
    """One-minute solar wind plasma of the last 24 hours.

    Attributes:
        values: The records of every source, oldest first; records with the
            same time keep the order of the source file.
        source_url: Where the content came from.
    """

    values: tuple[RtswWindSample, ...]
    source_url: str

    def __post_init__(self) -> None:
        check_values(self.values)
