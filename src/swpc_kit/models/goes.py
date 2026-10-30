"""Models for the GOES X-ray flux, integral particle flux and flare lists.

The GOES flux products of SWPC hold one record per time and per band: two
X-ray bands every minute, eight integral proton energy thresholds and one
electron threshold every five minutes. The models keep the records as they
come and give access by band or threshold. The flare class (A, B, C, M, X)
is computed from the flux of the 0.1-0.8 nm band.

The flare lists hold one record per ended flare, with the classes as SWPC
writes them. Only the latest flare can be in progress, and then it has no
end yet; its peak, even when already written, is not read (D-027).

Times are UTC (the source writes them with ``Z``).
"""

import math
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum
from itertools import pairwise
from typing import Protocol

from swpc_kit.models._checks import check_utc, check_values
from swpc_kit.models.records import SkippedRecord

# --- Flare class -------------------------------------------------------------

_LETTERS = ("A", "B", "C", "M", "X")
_BASE = {letter: Decimal(f"1e-{8 - i}") for i, letter in enumerate(_LETTERS)}
_TENTH = Decimal("0.1")
_CLASS_TEXT = re.compile(r"([ABCMX])([0-9]+(?:\.[0-9]+)?)")


@dataclass(frozen=True, slots=True, order=True)
class FlareClass:
    """A solar flare class, such as ``M2.5`` (a flux of 2.5e-5 W/m²).

    The letter gives the decade of the 0.1-0.8 nm flux in W/m² (A from
    10⁻⁸, B from 10⁻⁷, C from 10⁻⁶, M from 10⁻⁵, X from 10⁻⁴) and the
    multiplier the flux within it. X has no upper bound (X12 is
    1.2e-3 W/m²). Classes compare by flux.

    Attributes:
        letter: ``"A"``, ``"B"``, ``"C"``, ``"M"`` or ``"X"``.
        multiplier: Flux divided by the lower bound of the letter's decade,
            0 to 9.9 for A to M, 0 or more for X.

    Raises:
        ValueError: If the letter is unknown or the multiplier is out of
            range.
    """

    letter: str
    multiplier: float

    def __post_init__(self) -> None:
        if self.letter not in _LETTERS:
            raise ValueError(f"unknown flare class letter {self.letter!r}")
        upper = math.inf if self.letter == "X" else 10.0
        if not (0 <= self.multiplier < upper):
            raise ValueError(
                f"flare class multiplier {self.multiplier} out of range for "
                f"{self.letter}"
            )

    @classmethod
    def from_flux(cls, flux: float) -> "FlareClass":
        """Return the class of a 0.1-0.8 nm flux in W/m².

        The multiplier is truncated to one decimal (3.96e-6 is C3.9, and
        9.99e-6 is C9.9, not C10.0). The flux is read through its
        shortest decimal form, so 2.3e-5 gives M2.3 despite binary rounding.

        Raises:
            ValueError: If the flux is not a positive finite number.
        """
        if not (math.isfinite(flux) and flux > 0):
            raise ValueError(f"flux must be positive and finite, got {flux!r}")
        exact = Decimal(repr(flux))
        letter = next(
            (letter for letter, upper in pairwise(_LETTERS) if exact < _BASE[upper]),
            "X",
        )
        multiplier = (exact / _BASE[letter]).quantize(_TENTH, rounding=ROUND_FLOOR)
        return cls(letter, float(multiplier))

    @classmethod
    def parse(cls, text: str) -> "FlareClass":
        """Return the class written as text, such as ``"M2.5"``.

        This is how the flare lists of SWPC write classes: a letter, then
        the multiplier.

        Raises:
            ValueError: If the text is not a flare class.
        """
        match = _CLASS_TEXT.fullmatch(text)
        if match is None:
            raise ValueError(f"not a flare class: {text!r}")
        return cls(match.group(1), float(match.group(2)))

    @property
    def flux(self) -> float:
        """The flux the class stands for, in W/m² (M2.5 is 2.5e-5)."""
        return float(Decimal(repr(self.multiplier)) * _BASE[self.letter])

    def __str__(self) -> str:
        return f"{self.letter}{self.multiplier:.1f}"


# --- X-rays ------------------------------------------------------------------


class XrayBand(StrEnum):
    """The two GOES X-ray bands, as written in the ``energy`` field.

    Samples keep ``energy`` as a plain string, so a band SWPC adds later
    does not break parsing; these members compare equal to those strings.
    """

    SHORT = "0.05-0.4nm"
    """Short band, 0.05-0.4 nm."""
    LONG = "0.1-0.8nm"
    """Long band, 0.1-0.8 nm: the one flare classes are defined on."""


@dataclass(frozen=True, slots=True)
class XraySample:
    """One GOES X-ray flux value of one band.

    Attributes:
        time: Time of the value.
        satellite: GOES satellite number, such as 18.
        energy: Band, such as ``"0.1-0.8nm"`` (see :class:`XrayBand`).
        flux: Flux in W/m², after the electron correction, or ``None``.
        observed_flux: Flux in W/m² before the correction, or ``None``.
        electron_correction: Correction subtracted, in W/m², or ``None``.
        electron_contamination: Whether the value is flagged as contaminated
            by electrons (``electron_contaminaton``, so spelled, in the
            source), or ``None``.
    """

    time: datetime
    satellite: int
    energy: str
    flux: float | None
    observed_flux: float | None
    electron_correction: float | None
    electron_contamination: bool | None

    def __post_init__(self) -> None:
        check_utc("time", self.time)

    @property
    def flare_class(self) -> FlareClass | None:
        """Flare class of the flux, for the 0.1-0.8 nm band only.

        ``None`` for the other bands and when the flux is missing, zero or
        negative.
        """
        if self.energy != XrayBand.LONG or self.flux is None or self.flux <= 0:
            return None
        return FlareClass.from_flux(self.flux)


@dataclass(frozen=True, slots=True)
class GoesXrays:
    """GOES X-ray flux in both bands.

    Attributes:
        values: The values of every band, oldest first; values with the same
            time keep the order of the source file.
        source_url: Where the content came from.
        skipped: The records that could not be read, in source order.
    """

    values: tuple[XraySample, ...]
    source_url: str
    skipped: tuple[SkippedRecord, ...] = ()

    def __post_init__(self) -> None:
        check_values(self.values)

    @property
    def data_time(self) -> datetime:
        """Time of the most recent value, of any band."""
        return max(v.time for v in self.values)

    @property
    def energies(self) -> tuple[str, ...]:
        """The bands in the content, sorted."""
        return tuple(sorted({v.energy for v in self.values}))

    def band(self, energy: str) -> tuple[XraySample, ...]:
        """Return the values of one band, oldest first (empty if none)."""
        return tuple(v for v in self.values if v.energy == energy)

    def latest(self, energy: str = XrayBand.LONG) -> XraySample | None:
        """Return the most recent value of a band, or ``None``."""
        band = self.band(energy)
        return max(band, key=lambda v: v.time) if band else None

    def peak(self, energy: str = XrayBand.LONG) -> XraySample | None:
        """Return the value of a band with the highest flux, or ``None``.

        Values without a flux are ignored; on a tie the earliest one wins.
        """
        band = [v for v in self.band(energy) if v.flux is not None]
        return max(band, key=lambda v: v.flux or 0.0) if band else None


# --- Integral protons --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProtonSample:
    """One GOES integral proton flux value above one energy threshold.

    Attributes:
        time: Time of the value.
        satellite: GOES satellite number, such as 18.
        energy: Threshold as written in the source, such as ``">=10 MeV"``.
        threshold_mev: The threshold in MeV, such as 10.0.
        flux: Integral flux in pfu (particles cm⁻² s⁻¹ sr⁻¹), or ``None``.
    """

    time: datetime
    satellite: int
    energy: str
    threshold_mev: float
    flux: float | None

    def __post_init__(self) -> None:
        check_utc("time", self.time)


class _ThresholdSample(Protocol):
    @property
    def time(self) -> datetime: ...

    @property
    def threshold_mev(self) -> float: ...


class _IntegralSeries[S: _ThresholdSample]:
    """Access by energy threshold, shared by the GOES integral products."""

    __slots__ = ()

    values: tuple[S, ...]

    @property
    def data_time(self) -> datetime:
        """Time of the most recent value, of any threshold."""
        return max(v.time for v in self.values)

    @property
    def thresholds(self) -> tuple[float, ...]:
        """The energy thresholds in the content, in MeV, ascending."""
        return tuple(sorted({v.threshold_mev for v in self.values}))

    def series(self, threshold_mev: float) -> tuple[S, ...]:
        """Return the values above ``threshold_mev``, oldest first."""
        return tuple(v for v in self.values if v.threshold_mev == threshold_mev)

    def latest(self, threshold_mev: float) -> S | None:
        """Return the most recent value above ``threshold_mev``, or ``None``."""
        series = self.series(threshold_mev)
        return max(series, key=lambda v: v.time) if series else None


@dataclass(frozen=True, slots=True)
class GoesIntegralProtons(_IntegralSeries[ProtonSample]):
    """GOES integral proton flux above each energy threshold.

    Attributes:
        values: The values of every threshold, oldest first; values with the
            same time keep the order of the source file.
        source_url: Where the content came from.
        skipped: The records that could not be read, in source order.
    """

    values: tuple[ProtonSample, ...]
    source_url: str
    skipped: tuple[SkippedRecord, ...] = ()

    def __post_init__(self) -> None:
        check_values(self.values)


# --- Integral electrons ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ElectronSample:
    """One GOES integral electron flux value above one energy threshold.

    Attributes:
        time: Time of the value.
        satellite: GOES satellite number, such as 19.
        energy: Threshold as written in the source, such as ``">=2 MeV"``.
        threshold_mev: The threshold in MeV, such as 2.0.
        flux: Integral flux in pfu (particles cm⁻² s⁻¹ sr⁻¹), or ``None``.
    """

    time: datetime
    satellite: int
    energy: str
    threshold_mev: float
    flux: float | None

    def __post_init__(self) -> None:
        check_utc("time", self.time)


@dataclass(frozen=True, slots=True)
class GoesIntegralElectrons(_IntegralSeries[ElectronSample]):
    """GOES integral electron flux above each energy threshold.

    Attributes:
        values: The values of every threshold, oldest first; values with the
            same time keep the order of the source file.
        source_url: Where the content came from.
        skipped: The records that could not be read, in source order.
    """

    values: tuple[ElectronSample, ...]
    source_url: str
    skipped: tuple[SkippedRecord, ...] = ()

    def __post_init__(self) -> None:
        check_values(self.values)


# --- Flares ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GoesFlare:
    """One ended X-ray flare seen by GOES, with its classes as SWPC writes them.

    Attributes:
        begin_time: When the flare began.
        begin_class: The class of the flux when it began.
        max_time: When the 0.1-0.8 nm flux peaked.
        max_class: The class of the peak, such as ``M6.9``.
        max_flux: The 0.1-0.8 nm flux at the peak, in W/m² (``max_xrlong``).
        end_time: When the flare ended.
        end_class: The class of the flux when it ended.
        satellite: GOES satellite number, such as 18.
    """

    begin_time: datetime
    begin_class: FlareClass
    max_time: datetime
    max_class: FlareClass
    max_flux: float
    end_time: datetime
    end_class: FlareClass
    satellite: int

    def __post_init__(self) -> None:
        check_utc("begin_time", self.begin_time)
        check_utc("max_time", self.max_time)
        check_utc("end_time", self.end_time)


@dataclass(frozen=True, slots=True)
class GoesFlares:
    """The X-ray flares of the last days, such as ``xray-flares-7-day.json``.

    Attributes:
        values: The flares, oldest first by ``begin_time``; empty when no
            flare happened in the period.
        source_url: Where the content came from.
        skipped: The records that could not be read, in source order.
    """

    values: tuple[GoesFlare, ...]
    source_url: str
    skipped: tuple[SkippedRecord, ...] = ()

    @property
    def data_time(self) -> datetime | None:
        """When the most recent flare began, or ``None`` with no flares.

        The file holds no other time: a quiet Sun makes it look old, so a
        ``max_age`` on this product measures the time since the last flare.
        """
        return max((f.begin_time for f in self.values), default=None)

    def latest(self) -> GoesFlare | None:
        """Return the flare that began last, or ``None`` with no flares."""
        return max(self.values, key=lambda f: f.begin_time, default=None)

    def strongest(self) -> GoesFlare | None:
        """Return the flare with the highest peak, or ``None`` with no flares.

        On a tie the earliest one wins.
        """
        return max(self.values, key=lambda f: f.max_flux, default=None)


@dataclass(frozen=True, slots=True)
class GoesLatestFlare:
    """The latest flare and the class of the flux now (``xray-flares-latest.json``).

    While a flare is in progress SWPC has not written its end yet, and its
    peak can be empty or already written: only the beginning is read
    (D-027).

    Attributes:
        time: When the file was written, the time of ``current_class``.
        satellite: GOES satellite number, such as 18.
        current_class: The class of the 0.1-0.8 nm flux at ``time``.
        begin_time: When the latest flare began, in progress or not.
        begin_class: The class of the flux when it began.
        flare: The latest flare once it has ended, or ``None`` while it is
            in progress.
        source_url: Where the content came from.
    """

    time: datetime
    satellite: int
    current_class: FlareClass
    begin_time: datetime
    begin_class: FlareClass
    flare: GoesFlare | None
    source_url: str

    def __post_init__(self) -> None:
        check_utc("time", self.time)
        check_utc("begin_time", self.begin_time)
        flare = self.flare
        if flare is not None and (flare.begin_time, flare.begin_class) != (
            self.begin_time,
            self.begin_class,
        ):
            raise ValueError("begin_time and begin_class must be those of flare")

    @property
    def ongoing(self) -> bool:
        """Whether the latest flare is still in progress (no end yet)."""
        return self.flare is None

    @property
    def data_time(self) -> datetime:
        """When the file was written (its ``time_tag``)."""
        return self.time
