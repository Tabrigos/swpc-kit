"""Models for the SWPC text bulletins.

The 3-day forecast (``3-day-forecast.txt``), the geomagnetic forecast
(``3-day-geomag-forecast.txt``) and the 27-day outlook (``27-day-outlook.txt``).
Each one carries the ``:Issued:`` time of its header, which is also its
``data_time``.

The bulletins write their days as month and day without a year; the parsers
place them in the year that puts them closest to the issue time, so a
forecast issued on 31 December runs into January of the next year.

Free text (summaries and rationales) is kept as written, with the line
wrapping undone: wrapped lines are joined with a space and paragraphs are
separated by a blank line. It is data to read, never instructions.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import pairwise

KP_PERIOD = timedelta(hours=3)
"""Length of one interval of a Kp table."""

KP_PERIODS_PER_DAY = 8
"""Rows of a Kp table: ``00-03UT`` to ``21-00UT``."""


def _check_utc(name: str, value: datetime) -> None:
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an aware datetime in UTC, got {value!r}")


def _check_days(days: Sequence[date]) -> None:
    if not days:
        raise ValueError("days must not be empty")
    for before, after in pairwise(days):
        if after - before != timedelta(days=1):
            raise ValueError(f"days must follow each other, got {before} then {after}")


def _check_aligned(name: str, values: Sequence[object], days: Sequence[date]) -> None:
    if len(values) != len(days):
        raise ValueError(f"{name} has {len(values)} values for {len(days)} days")


def _check_kp(kp: Sequence["KpPeriod"], days: Sequence[date]) -> None:
    if len(kp) != KP_PERIODS_PER_DAY * len(days):
        raise ValueError(
            f"kp has {len(kp)} periods, expected {KP_PERIODS_PER_DAY} per day "
            f"for {len(days)} days"
        )


@dataclass(frozen=True, slots=True)
class KpPeriod:
    """One 3-hour interval of a Kp forecast table.

    Attributes:
        start: Start of the interval.
        kp: Kp in thirds, as a decimal (2.67 is 3-), from 0 to 9.
        noaa_scale: NOAA geomagnetic storm level written next to the value,
            such as ``"G1"`` for ``5.33 (G1)``, or ``None``.
    """

    start: datetime
    kp: float
    noaa_scale: str | None

    def __post_init__(self) -> None:
        _check_utc("start", self.start)

    @property
    def end(self) -> datetime:
        """End of the interval, three hours after ``start``."""
        return self.start + KP_PERIOD


@dataclass(frozen=True, slots=True)
class ThreeDayForecast:
    """The 3-day forecast: geomagnetic activity, radiation storms, blackouts.

    Every per-day tuple is aligned with ``days``.

    Attributes:
        issued: The ``:Issued:`` time.
        days: The three forecast days.
        greatest_observed_kp: Greatest 3-hour Kp observed over the 24 hours
            before the issue time.
        greatest_observed_scale: NOAA scale level of that value, such as
            ``"G1"``, or ``None`` when below the scale levels.
        greatest_expected_kp: Greatest 3-hour Kp expected over ``days``.
        greatest_expected_scale: NOAA scale level of that value, or ``None``.
        geomagnetic_summary: The sentences on the greatest Kp, as text.
        kp: Kp forecast for every 3-hour interval of ``days``, in time order.
        geomagnetic_rationale: Rationale of section A.
        solar_radiation_summary: Observation paragraph of section B.
        s1_or_greater: Probability of an S1 or greater radiation storm, in
            percent, per day.
        solar_radiation_rationale: Rationale of section B.
        radio_blackout_summary: Observation paragraph of section C.
        r1_r2: Probability of an R1-R2 radio blackout, in percent, per day.
        r3_or_greater: Probability of an R3 or greater radio blackout, in
            percent, per day.
        radio_blackout_rationale: Rationale of section C.
        source_url: Where the content came from.
    """

    issued: datetime
    days: tuple[date, ...]
    greatest_observed_kp: float
    greatest_observed_scale: str | None
    greatest_expected_kp: float
    greatest_expected_scale: str | None
    geomagnetic_summary: str
    kp: tuple[KpPeriod, ...]
    geomagnetic_rationale: str
    solar_radiation_summary: str
    s1_or_greater: tuple[int, ...]
    solar_radiation_rationale: str
    radio_blackout_summary: str
    r1_r2: tuple[int, ...]
    r3_or_greater: tuple[int, ...]
    radio_blackout_rationale: str
    source_url: str

    def __post_init__(self) -> None:
        _check_utc("issued", self.issued)
        _check_days(self.days)
        _check_kp(self.kp, self.days)
        _check_aligned("s1_or_greater", self.s1_or_greater, self.days)
        _check_aligned("r1_r2", self.r1_r2, self.days)
        _check_aligned("r3_or_greater", self.r3_or_greater, self.days)

    @property
    def data_time(self) -> datetime:
        """The ``:Issued:`` time."""
        return self.issued


@dataclass(frozen=True, slots=True)
class DailyAp:
    """The planetary A index of one day.

    Attributes:
        day: The UTC day.
        ap: The Ap index.
    """

    day: date
    ap: int


@dataclass(frozen=True, slots=True)
class GeomagneticForecast:
    """The geomagnetic forecast: Ap, storm probabilities and Kp.

    Every per-day tuple is aligned with ``days``.

    Attributes:
        issued: The ``:Issued:`` time.
        observed_ap: Ap observed on the day before ``estimated_ap``.
        estimated_ap: Ap estimated for the day of issue.
        days: The three forecast days.
        predicted_ap: Ap predicted for each of ``days``.
        active: Probability of active conditions, in percent, per day.
        minor_storm: Probability of a minor storm, in percent, per day.
        moderate_storm: Probability of a moderate storm, in percent, per day.
        strong_extreme_storm: Probability of a strong to extreme storm, in
            percent, per day.
        kp: Kp forecast for every 3-hour interval of ``days``, in time order.
        source_url: Where the content came from.
    """

    issued: datetime
    observed_ap: DailyAp
    estimated_ap: DailyAp
    days: tuple[date, ...]
    predicted_ap: tuple[DailyAp, ...]
    active: tuple[int, ...]
    minor_storm: tuple[int, ...]
    moderate_storm: tuple[int, ...]
    strong_extreme_storm: tuple[int, ...]
    kp: tuple[KpPeriod, ...]
    source_url: str

    def __post_init__(self) -> None:
        _check_utc("issued", self.issued)
        _check_days(self.days)
        if tuple(a.day for a in self.predicted_ap) != self.days:
            raise ValueError("predicted_ap must give one value for each of days")
        _check_aligned("active", self.active, self.days)
        _check_aligned("minor_storm", self.minor_storm, self.days)
        _check_aligned("moderate_storm", self.moderate_storm, self.days)
        _check_aligned("strong_extreme_storm", self.strong_extreme_storm, self.days)
        _check_kp(self.kp, self.days)

    @property
    def data_time(self) -> datetime:
        """The ``:Issued:`` time."""
        return self.issued


@dataclass(frozen=True, slots=True)
class OutlookDay:
    """One day of the 27-day outlook.

    Attributes:
        day: The UTC day.
        radio_flux: Predicted 10.7 cm radio flux, in solar flux units.
        ap: Predicted planetary A index.
        largest_kp: Predicted largest Kp of the day, from 0 to 9.
    """

    day: date
    radio_flux: float
    ap: int
    largest_kp: int


@dataclass(frozen=True, slots=True)
class TwentySevenDayOutlook:
    """The 27-day space weather outlook.

    Attributes:
        issued: The ``:Issued:`` time.
        days: One entry per day, in date order, on consecutive days.
        source_url: Where the content came from.
    """

    issued: datetime
    days: tuple[OutlookDay, ...]
    source_url: str

    def __post_init__(self) -> None:
        _check_utc("issued", self.issued)
        _check_days([d.day for d in self.days])

    @property
    def data_time(self) -> datetime:
        """The ``:Issued:`` time."""
        return self.issued
