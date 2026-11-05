"""Models for the solar flare probabilities and the solar active regions.

``solar_probabilities.json`` gives, for each day of issue, the probabilities
of C, M and X flares and of a proton event for three days. ``solar_regions.json``
gives, for each day of observation, the numbered active regions with their
sunspots, flares and flare probabilities.

Days are UTC days (``date``); the other times are UTC (the source writes them
without a zone).
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from swpc_kit.models._checks import check_utc, check_values
from swpc_kit.models.records import SkippedRecord

# --- Probabilities -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SolarProbability:
    """The probabilities issued on one day, in percent, for three days.

    Each tuple holds the values of the first, second and third day, in the
    order of ``_1_day``, ``_2_day``, ``_3_day``. Which dates these are the
    file does not say (``docs/FONTI.md``).

    Attributes:
        day: The day of issue (``date``).
        c_class: Probability of a C-class flare, per day.
        m_class: Probability of an M-class flare, per day.
        x_class: Probability of an X-class flare, per day.
        proton_10mev: Probability of a proton event at 10 MeV, per day.
        polar_cap_absorption: The polar cap absorption as SWPC writes it, a
            colour such as ``"green"``.
    """

    day: date
    c_class: tuple[int, int, int]
    m_class: tuple[int, int, int]
    x_class: tuple[int, int, int]
    proton_10mev: tuple[int, int, int]
    polar_cap_absorption: str

    def __post_init__(self) -> None:
        for name in ("c_class", "m_class", "x_class", "proton_10mev"):
            if len(getattr(self, name)) != 3:
                raise ValueError(f"{name} must give three days")


@dataclass(frozen=True, slots=True)
class SolarProbabilities:
    """The flare and proton probabilities of the last days of issue.

    Attributes:
        values: One entry per day of issue, oldest first.
        source_url: Where the content came from.
        skipped: The records that could not be read, in source order.
    """

    values: tuple[SolarProbability, ...]
    source_url: str
    skipped: tuple[SkippedRecord, ...] = ()

    def __post_init__(self) -> None:
        check_values(self.values)

    def latest(self) -> SolarProbability:
        """Return the probabilities of the latest day of issue."""
        return self.values[-1]

    @property
    def data_time(self) -> datetime:
        """The start (00:00 UTC) of the latest day of issue."""
        return datetime.combine(self.values[-1].day, time(), UTC)


# --- Regions -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SolarRegion:
    """One numbered active region as observed on one day.

    The five sunspot fields, ``spot_class`` to ``number_spots``, are all
    ``None`` for a region without spots on that day, and all set otherwise
    (D-025, D-028). The JSON file has no documentation of its own: the
    meanings below marked as in the SRS report are a hypothesis
    (``docs/FONTI.md``). Fields of the source whose meaning SWPC does not
    document, or that are always ``null``, are left out.

    Attributes:
        day: The day of observation (``observed_date``).
        region: The NOAA region number, such as 4566.
        latitude: Heliographic latitude in degrees, north positive.
        longitude: Longitude from the central meridian in degrees, east
            positive, as SWPC writes it: ``S06E40`` is 40, ``N17W41`` is -41.
        location: The location as written, such as ``"S06E40"``; beyond 99
            degrees west it is cut, such as ``"S19W0*"`` for -108.
        carrington_longitude: Carrington longitude in degrees.
        status: The status letter as written, such as ``"f"`` or ``"d"``, or
            ``None``.
        spot_class: The class of the spot group as written, such as
            ``"Fai"`` (the McIntosh class, as in the SRS report).
        mag_class: The magnetic class as written, such as ``"BGD"`` (the
            Mount Wilson class, as in the SRS report).
        area: The area of the spot group (in millionths of the solar
            hemisphere, as in the SRS report).
        extent: The extent of the group (in degrees of longitude, as in
            the SRS report).
        number_spots: The number of spots.
        c_xray_events: C-class X-ray events of the region on that day.
        m_xray_events: M-class X-ray events of the region on that day.
        x_xray_events: X-class X-ray events of the region on that day.
        c_flare_probability: Probability of a C-class flare, in percent.
        m_flare_probability: Probability of an M-class flare, in percent.
        x_flare_probability: Probability of an X-class flare, in percent.
        proton_probability: Probability of a proton event, in percent.
        first_date: The ``first_date`` of the source, the same for every day
            of a region (when it was first seen, by its name).
    """

    day: date
    region: int
    latitude: int
    longitude: int
    location: str
    carrington_longitude: int
    status: str | None
    spot_class: str | None
    mag_class: str | None
    area: int | None
    extent: int | None
    number_spots: int | None
    c_xray_events: int
    m_xray_events: int
    x_xray_events: int
    c_flare_probability: int
    m_flare_probability: int
    x_flare_probability: int
    proton_probability: int
    first_date: datetime

    def __post_init__(self) -> None:
        check_utc("first_date", self.first_date)


@dataclass(frozen=True, slots=True)
class SolarRegions:
    """The active regions of the last days of observation.

    Attributes:
        values: The regions of every day, by day and then by region number.
        source_url: Where the content came from.
        skipped: The records that could not be read, in source order.
    """

    values: tuple[SolarRegion, ...]
    source_url: str
    skipped: tuple[SkippedRecord, ...] = ()

    def __post_init__(self) -> None:
        check_values(self.values)

    def days(self) -> tuple[date, ...]:
        """Return the days of observation, oldest first."""
        return tuple(sorted({r.day for r in self.values}))

    def on(self, day: date) -> tuple[SolarRegion, ...]:
        """Return the regions observed on ``day``, by region number."""
        return tuple(r for r in self.values if r.day == day)

    def latest_day(self) -> tuple[SolarRegion, ...]:
        """Return the regions of the latest day of observation."""
        return self.on(self.values[-1].day)

    @property
    def data_time(self) -> datetime:
        """The start (00:00 UTC) of the latest day of observation."""
        return datetime.combine(self.values[-1].day, time(), UTC)
