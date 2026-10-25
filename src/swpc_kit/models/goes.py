"""Models for the GOES X-ray flux and integral proton flux.

The GOES products of SWPC hold one record per time and per band: two X-ray
bands every minute, eight integral proton energy thresholds every five
minutes. The models keep the records as they come and give access by band
or threshold. The flare class (A, B, C, M, X) is computed from the flux of
the 0.1-0.8 nm band.

Times are UTC (the source writes them with ``Z``).
"""

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum
from itertools import pairwise

from swpc_kit.models._checks import check_utc, check_values
from swpc_kit.models.records import SkippedRecord

# --- Flare class -------------------------------------------------------------

_LETTERS = ("A", "B", "C", "M", "X")
_BASE = {letter: Decimal(f"1e-{8 - i}") for i, letter in enumerate(_LETTERS)}
_TENTH = Decimal("0.1")


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


@dataclass(frozen=True, slots=True)
class GoesIntegralProtons:
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

    @property
    def data_time(self) -> datetime:
        """Time of the most recent value, of any threshold."""
        return max(v.time for v in self.values)

    @property
    def thresholds(self) -> tuple[float, ...]:
        """The energy thresholds in the content, in MeV, ascending."""
        return tuple(sorted({v.threshold_mev for v in self.values}))

    def series(self, threshold_mev: float) -> tuple[ProtonSample, ...]:
        """Return the values above ``threshold_mev``, oldest first."""
        return tuple(v for v in self.values if v.threshold_mev == threshold_mev)

    def latest(self, threshold_mev: float) -> ProtonSample | None:
        """Return the most recent value above ``threshold_mev``, or ``None``."""
        series = self.series(threshold_mev)
        return max(series, key=lambda v: v.time) if series else None
