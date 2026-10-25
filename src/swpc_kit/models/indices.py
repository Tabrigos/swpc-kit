"""Models for the geomagnetic and solar indices.

Planetary K index (3-hour values, forecast and 1-minute estimates), Kyoto Dst,
the 10.7 cm solar radio flux (F10.7) and the NOAA space weather scales.

Times are UTC. SWPC writes most of these ``time_tag`` values without a time
zone; they are read as UTC.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from swpc_kit.models._checks import check_utc, check_values
from swpc_kit.models.records import SkippedRecord

# --- Planetary K index, 3-hour values ---------------------------------------


@dataclass(frozen=True, slots=True)
class KpValue:
    """One 3-hour planetary K index value.

    Attributes:
        time: Start of the 3-hour interval.
        kp: Kp in thirds, as a decimal (2.67 is 3-), from 0 to 9.
        a_running: Running a index (``a_running`` in the source).
        station_count: Number of magnetometer stations used.
    """

    time: datetime
    kp: float
    a_running: int
    station_count: int

    def __post_init__(self) -> None:
        check_utc("time", self.time)


@dataclass(frozen=True, slots=True)
class PlanetaryKIndex:
    """The 3-hour planetary K index of the last days.

    Attributes:
        values: The values, oldest first, one per time.
        source_url: Where the content came from.
        skipped: The records that could not be read, in source order.
    """

    values: tuple[KpValue, ...]
    source_url: str
    skipped: tuple[SkippedRecord, ...] = ()

    def __post_init__(self) -> None:
        check_values(self.values)

    @property
    def data_time(self) -> datetime:
        """Start of the most recent 3-hour interval."""
        return max(v.time for v in self.values)


# --- Planetary K index forecast ---------------------------------------------


class KpForecastStatus(StrEnum):
    """Whether a forecast value is measured, estimated or predicted.

    Values match the ``observed`` field of the source.
    """

    OBSERVED = "observed"
    ESTIMATED = "estimated"
    PREDICTED = "predicted"


@dataclass(frozen=True, slots=True)
class KpForecastValue:
    """One 3-hour value of the Kp forecast.

    Attributes:
        time: Start of the 3-hour interval.
        kp: Kp as a decimal, from 0 to 9.
        status: Whether the value is observed, estimated or predicted.
        noaa_scale: NOAA geomagnetic storm level reached, such as ``"G1"``,
            or ``None``.
    """

    time: datetime
    kp: float
    status: KpForecastStatus
    noaa_scale: str | None

    def __post_init__(self) -> None:
        check_utc("time", self.time)


@dataclass(frozen=True, slots=True)
class PlanetaryKIndexForecast:
    """Kp of the past week followed by the forecast for the next days.

    Attributes:
        values: The values, oldest first, one per time.
        source_url: Where the content came from.
        skipped: The records that could not be read, in source order.
    """

    values: tuple[KpForecastValue, ...]
    source_url: str
    skipped: tuple[SkippedRecord, ...] = ()

    def __post_init__(self) -> None:
        check_values(self.values)

    @property
    def data_time(self) -> datetime:
        """Start of the most recent observed interval.

        Estimated values can lie in the future, so they do not count. When
        there is no observed value, this is the earliest time in the content.
        """
        observed = [
            v.time for v in self.values if v.status is KpForecastStatus.OBSERVED
        ]
        if observed:
            return max(observed)
        return min(v.time for v in self.values)


# --- Planetary K index, 1-minute estimates ----------------------------------


@dataclass(frozen=True, slots=True)
class Kp1mValue:
    """One 1-minute estimate of the planetary K index.

    Attributes:
        time: Time of the estimate.
        kp_index: Kp rounded to an integer, from 0 to 9.
        estimated_kp: Kp in thirds, as a decimal.
        kp: Kp as a label: digit plus ``Z`` (exact), ``P`` (plus a third) or
            ``M`` (minus a third), such as ``"3M"`` for 2.67.
    """

    time: datetime
    kp_index: int
    estimated_kp: float
    kp: str

    def __post_init__(self) -> None:
        check_utc("time", self.time)


@dataclass(frozen=True, slots=True)
class PlanetaryKIndex1m:
    """The 1-minute planetary K index estimates of the last hours.

    Attributes:
        values: The values, oldest first, one per time.
        source_url: Where the content came from.
        skipped: The records that could not be read, in source order.
    """

    values: tuple[Kp1mValue, ...]
    source_url: str
    skipped: tuple[SkippedRecord, ...] = ()

    def __post_init__(self) -> None:
        check_values(self.values)

    @property
    def data_time(self) -> datetime:
        """Time of the most recent estimate."""
        return max(v.time for v in self.values)


# --- Kyoto Dst ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DstValue:
    """One hourly value of the Kyoto Dst index.

    Attributes:
        time: Time of the value.
        dst: Dst in nT.
    """

    time: datetime
    dst: int

    def __post_init__(self) -> None:
        check_utc("time", self.time)


@dataclass(frozen=True, slots=True)
class KyotoDst:
    """Hourly Kyoto Dst of the last week.

    Attributes:
        values: The values, oldest first, one per time.
        source_url: Where the content came from.
        skipped: The records that could not be read, in source order.
    """

    values: tuple[DstValue, ...]
    source_url: str
    skipped: tuple[SkippedRecord, ...] = ()

    def __post_init__(self) -> None:
        check_values(self.values)

    @property
    def data_time(self) -> datetime:
        """Time of the most recent value."""
        return max(v.time for v in self.values)


# --- F10.7 -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class F107Value:
    """One daily value of the 10.7 cm solar radio flux.

    Attributes:
        time: Time of the measurement.
        flux: Flux in solar flux units (10⁻²² W m⁻² Hz⁻¹).
    """

    time: datetime
    flux: float

    def __post_init__(self) -> None:
        check_utc("time", self.time)


@dataclass(frozen=True, slots=True)
class F107Flux:
    """Daily 10.7 cm solar radio flux of the last 30 days.

    Attributes:
        values: The values, oldest first, one per time.
        source_url: Where the content came from.
        skipped: The records that could not be read, in source order.
    """

    values: tuple[F107Value, ...]
    source_url: str
    skipped: tuple[SkippedRecord, ...] = ()

    def __post_init__(self) -> None:
        check_values(self.values)

    @property
    def data_time(self) -> datetime:
        """Time of the most recent value."""
        return max(v.time for v in self.values)


# --- NOAA scales -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RadioBlackoutScale:
    """Radio blackout (R) entry of a day of ``noaa-scales.json``.

    Attributes:
        scale: Level reached, 0 to 5, or ``None`` (forecast days).
        text: Description of the level, such as ``"none"``, or ``None``.
        minor_prob: Probability of R1-R2 in percent, or ``None``.
        major_prob: Probability of R3 or greater in percent, or ``None``.
    """

    scale: int | None
    text: str | None
    minor_prob: int | None
    major_prob: int | None


@dataclass(frozen=True, slots=True)
class SolarRadiationScale:
    """Solar radiation storm (S) entry of a day of ``noaa-scales.json``.

    Attributes:
        scale: Level reached, 0 to 5, or ``None`` (forecast days).
        text: Description of the level, or ``None``.
        prob: Probability of S1 or greater in percent, or ``None``.
    """

    scale: int | None
    text: str | None
    prob: int | None


@dataclass(frozen=True, slots=True)
class GeomagneticStormScale:
    """Geomagnetic storm (G) entry of a day of ``noaa-scales.json``.

    Attributes:
        scale: Level reached or expected, 0 to 5, or ``None``.
        text: Description of the level, or ``None``.
    """

    scale: int | None
    text: str | None


@dataclass(frozen=True, slots=True)
class NoaaScalesDay:
    """One entry of ``noaa-scales.json``.

    Attributes:
        day: The key of the entry. From the dates it carries, -1 looks like
            the past 24 hours, 0 the current levels and 1 to 3 the forecast
            for today and the next two days; SWPC does not document it.
        time: ``DateStamp`` and ``TimeStamp`` of the entry.
        r: Radio blackouts.
        s: Solar radiation storms.
        g: Geomagnetic storms.
    """

    day: int
    time: datetime
    r: RadioBlackoutScale
    s: SolarRadiationScale
    g: GeomagneticStormScale

    def __post_init__(self) -> None:
        check_utc("time", self.time)


@dataclass(frozen=True, slots=True)
class NoaaScales:
    """The NOAA space weather scales: recent, current and forecast levels.

    Attributes:
        days: The entries, sorted by ``day``.
        source_url: Where the content came from.
    """

    days: tuple[NoaaScalesDay, ...]
    source_url: str

    def __post_init__(self) -> None:
        if not any(d.day <= 0 for d in self.days):
            raise ValueError("days must include an observed entry (day <= 0)")

    def day(self, day: int) -> NoaaScalesDay | None:
        """Return the entry with key ``day``, or ``None``."""
        return next((d for d in self.days if d.day == day), None)

    @property
    def data_time(self) -> datetime:
        """Most recent time among the observed entries (``day`` <= 0)."""
        return max(d.time for d in self.days if d.day <= 0)
