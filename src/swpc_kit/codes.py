"""Catalogue of the SWPC space weather message codes.

Each message of ``alerts.json`` carries two codes: a short ``product_id``
such as ``K04W``, and a long code in its first line
(``Space Weather Message Code: WARK04``), the one SWPC uses in its table of
products (https://www.spaceweather.gov/content/subscription-services).

Every entry says how it is known (see ``docs/FONTI.md``, section "Avvisi"):

- :attr:`Verification.VERIFIED`: everything in the entry is confirmed,
  either by the text of the messages of the recorded fixture (the pair of
  codes, meaning and scale) or by the official SWPC table of products (long
  code, meaning and scale; the short code is then ``None`` if no message
  showed it);
- :attr:`Verification.DEDUCED`: long code, meaning and scale come from the
  official table, but the short code was not seen in a message: it follows
  the pattern of the verified ones and may be wrong.

An unknown code is not an error: lookups return ``None`` and the message
keeps its raw text.
"""

from dataclasses import dataclass
from enum import StrEnum


class Verification(StrEnum):
    """How a catalogue entry is known."""

    VERIFIED = "verified"
    DEDUCED = "deduced"


@dataclass(frozen=True, slots=True)
class MessageCode:
    """One kind of space weather message.

    Attributes:
        long: Long code, as in ``Space Weather Message Code:``, e.g. ``WARK04``.
        short: Short code, as in the ``product_id`` of ``alerts.json``, e.g.
            ``K04W``; ``None`` when not known.
        meaning: What the message announces, e.g.
            ``"Warning: Geomagnetic K-index of 4 expected"``.
        scale: NOAA scale level the message is about, e.g. ``"G1"``, or
            ``None`` when the message has no scale level.
        verification: Whether the entry was verified or deduced.
    """

    long: str
    short: str | None
    meaning: str
    scale: str | None
    verification: Verification


_V = Verification.VERIFIED
_D = Verification.DEDUCED

CATALOGUE: tuple[MessageCode, ...] = (
    # Geomagnetic K-index warnings and alerts.
    MessageCode(
        "WARK04", "K04W", "Warning: Geomagnetic K-index of 4 expected", None, _V
    ),
    MessageCode(
        "WARK05", "K05W", "Warning: Geomagnetic K-index of 5 expected", "G1", _V
    ),
    MessageCode(
        "WARK06", "K06W", "Warning: Geomagnetic K-index of 6 expected", "G2", _V
    ),
    MessageCode(
        "WARK07",
        "K07W",
        "Warning: Geomagnetic K-index of 7 or greater expected",
        "G3",
        _V,
    ),
    MessageCode("ALTK04", "K04A", "Alert: Geomagnetic K-index of 4", None, _V),
    MessageCode("ALTK05", "K05A", "Alert: Geomagnetic K-index of 5", "G1", _V),
    MessageCode("ALTK06", "K06A", "Alert: Geomagnetic K-index of 6", "G2", _V),
    MessageCode("ALTK07", "K07A", "Alert: Geomagnetic K-index of 7", "G3", _V),
    MessageCode("ALTK08", "K08A", "Alert: Geomagnetic K-index of 8", "G4", _D),
    MessageCode("ALTK09", "K09A", "Alert: Geomagnetic K-index of 9", "G5", _D),
    # Geomagnetic storm watches.
    MessageCode(
        "WATA20", "A20F", "Watch: Geomagnetic Storm Category G1 Predicted", "G1", _V
    ),
    MessageCode(
        "WATA30", "A30F", "Watch: Geomagnetic Storm Category G2 Predicted", "G2", _V
    ),
    MessageCode(
        "WATA50", "A50F", "Watch: Geomagnetic Storm Category G3 Predicted", "G3", _D
    ),
    MessageCode(
        "WATA99",
        "A99F",
        "Watch: Geomagnetic Storm Category G4 or Greater Predicted",
        "G4",
        _D,
    ),
    # Geomagnetic sudden impulse.
    MessageCode(
        "WARSUD", "SGIW", "Warning: Geomagnetic Sudden Impulse expected", None, _V
    ),
    MessageCode("SUMSUD", "MSIS", "Summary: Geomagnetic Sudden Impulse", None, _V),
    # Electrons.
    MessageCode(
        "ALTEF3",
        "EF3A",
        "Alert: Electron 2MeV Integral Flux exceeded 1,000pfu",
        None,
        _V,
    ),
    # Protons (official table; short codes not seen in a message).
    MessageCode(
        "WARPX1",
        None,
        "Warning: Proton 10MeV Integral Flux above 10pfu expected",
        "S1",
        _V,
    ),
    MessageCode(
        "WARPC0",
        None,
        "Warning: Proton 100MeV Integral Flux above 1pfu expected",
        None,
        _V,
    ),
    MessageCode(
        "ALTPX1",
        None,
        "Alert: Proton Event 10MeV Integral Flux exceeded 10pfu",
        "S1",
        _V,
    ),
    MessageCode(
        "SUMPX1",
        None,
        "Summary: Proton Event 10MeV Integral Flux exceeded 10pfu",
        "S1",
        _V,
    ),
    MessageCode(
        "ALTPX2",
        None,
        "Alert: Proton Event 10MeV Integral Flux exceeded 100pfu",
        "S2",
        _V,
    ),
    MessageCode(
        "SUMPX2",
        None,
        "Summary: Proton Event 10MeV Integral Flux exceeded 100pfu",
        "S2",
        _V,
    ),
    MessageCode(
        "ALTPX3",
        None,
        "Alert: Proton Event 10MeV Integral Flux exceeded 1,000pfu",
        "S3",
        _V,
    ),
    MessageCode(
        "SUMPX3",
        None,
        "Summary: Proton Event 10MeV Integral Flux exceeded 1,000pfu",
        "S3",
        _V,
    ),
    MessageCode(
        "ALTPX4",
        None,
        "Alert: Proton Event 10MeV Integral Flux exceeded 10,000pfu",
        "S4",
        _V,
    ),
    MessageCode(
        "SUMPX4",
        None,
        "Summary: Proton Event 10MeV Integral Flux exceeded 10,000pfu",
        "S4",
        _V,
    ),
    MessageCode(
        "ALTPX5",
        None,
        "Alert: Proton Event 10MeV Integral Flux exceeded 100,000pfu",
        "S5",
        _V,
    ),
    MessageCode(
        "SUMPX5",
        None,
        "Summary: Proton Event 10MeV Integral Flux exceeded 100,000pfu",
        "S5",
        _V,
    ),
    MessageCode(
        "ALTPC0",
        None,
        "Alert: Proton Event 100MeV Integral Flux exceeded 1pfu",
        None,
        _V,
    ),
    MessageCode(
        "SUMPC0",
        None,
        "Summary: Proton Event 100MeV Integral Flux exceeded 1pfu",
        None,
        _V,
    ),
    # X-rays.
    MessageCode("ALTXMF", "XM5A", "Alert: X-Ray Flux exceeded M5", "R2", _V),
    MessageCode("SUMXM5", "XM5S", "Summary: X-ray Event exceeded M5", "R2", _V),
    MessageCode("SUMX01", None, "Summary: X-ray Event exceeded X1", "R3", _V),
    MessageCode("SUMX10", None, "Summary: X-ray Event exceeded X10", "R4", _V),
    MessageCode("SUMX20", None, "Summary: X-ray Event exceeded X20", "R5", _V),
    # Radio.
    MessageCode("ALTTP2", "TIIA", "Alert: Type II Radio Emission", None, _V),
    MessageCode("ALTTP4", "TIVA", "Alert: Type IV Radio Emission", None, _V),
    MessageCode("SUM10R", "BHIS", "Summary: 10cm Radio Burst", None, _V),
)

_BY_LONG = {c.long: c for c in CATALOGUE}
_BY_SHORT = {c.short: c for c in CATALOGUE if c.short is not None}


def by_long(code: str) -> MessageCode | None:
    """Return the entry with long code ``code`` (e.g. ``WARK04``), or ``None``.

    Case and surrounding spaces are ignored.
    """
    return _BY_LONG.get(code.strip().upper())


def by_short(code: str) -> MessageCode | None:
    """Return the entry with short code ``code`` (e.g. ``K04W``), or ``None``.

    Case and surrounding spaces are ignored.
    """
    return _BY_SHORT.get(code.strip().upper())


def lookup(code: str) -> MessageCode | None:
    """Return the entry with ``code`` as its short or long code, or ``None``."""
    return by_short(code) or by_long(code)
