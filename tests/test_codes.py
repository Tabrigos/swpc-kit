import json
import re
from pathlib import Path

import pytest

from swpc_kit.codes import (
    CATALOGUE,
    MessageCode,
    Verification,
    by_long,
    by_short,
    lookup,
)

FIXTURE = Path(__file__).parent / "fixtures" / "alerts" / "2026-10-15.json"

VERIFIED_PAIRS = {
    "K04W": "WARK04",
    "K05W": "WARK05",
    "K06W": "WARK06",
    "K07W": "WARK07",
    "K04A": "ALTK04",
    "K05A": "ALTK05",
    "K06A": "ALTK06",
    "K07A": "ALTK07",
    "A20F": "WATA20",
    "A30F": "WATA30",
    "EF3A": "ALTEF3",
    "MSIS": "SUMSUD",
    "TIIA": "ALTTP2",
    "TIVA": "ALTTP4",
    "XM5A": "ALTXMF",
    "XM5S": "SUMXM5",
    "SGIW": "WARSUD",
    "BHIS": "SUM10R",
}


def test_verified_entries_are_the_pairs_seen_in_the_fixture() -> None:
    verified = {
        c.short: c.long for c in CATALOGUE if c.verification is Verification.VERIFIED
    }
    assert verified == VERIFIED_PAIRS


def test_fixture_codes_match_the_catalogue() -> None:
    for item in json.loads(FIXTURE.read_bytes()):
        long = re.search(r"Space Weather Message Code: (\S+)", item["message"])
        assert long is not None
        entry = by_short(item["product_id"])
        assert entry is not None
        assert entry.long == long.group(1)
        assert entry.verification is Verification.VERIFIED


def test_codes_are_unique() -> None:
    longs = [c.long for c in CATALOGUE]
    shorts = [c.short for c in CATALOGUE if c.short is not None]
    assert len(set(longs)) == len(longs)
    assert len(set(shorts)) == len(shorts)


def test_entries_are_well_formed() -> None:
    for c in CATALOGUE:
        assert re.fullmatch(r"(ALT|WAR|WAT|SUM)[A-Z0-9]{3}", c.long), c
        assert c.short is None or re.fullmatch(r"[A-Z0-9]{4}", c.short), c
        assert c.scale is None or re.fullmatch(r"[GSR][1-5]", c.scale), c
        assert c.meaning.split(":")[0] in {"Alert", "Warning", "Watch", "Summary"}


def test_deduced_entries_exist_and_are_flagged() -> None:
    deduced = [c for c in CATALOGUE if c.verification is Verification.DEDUCED]
    assert deduced
    assert all(c.short not in VERIFIED_PAIRS for c in deduced)
    k9 = by_long("ALTK09")
    assert k9 is not None
    assert k9.verification is Verification.DEDUCED
    assert k9.scale == "G5"


@pytest.mark.parametrize(
    ("short", "scale"),
    [
        ("K04W", None),
        ("K05W", "G1"),
        ("K06W", "G2"),
        ("K07W", "G3"),
        ("K04A", None),
        ("K05A", "G1"),
        ("K06A", "G2"),
        ("K07A", "G3"),
        ("A20F", "G1"),
        ("A30F", "G2"),
        ("XM5A", "R2"),
        ("XM5S", "R2"),
        ("EF3A", None),
    ],
)
def test_scale_of_verified_codes(short: str, scale: str | None) -> None:
    entry = by_short(short)
    assert entry is not None
    assert entry.scale == scale


def test_lookups() -> None:
    entry = by_short("K04W")
    assert entry == MessageCode(
        long="WARK04",
        short="K04W",
        meaning="Warning: Geomagnetic K-index of 4 expected",
        scale=None,
        verification=Verification.VERIFIED,
    )
    assert by_long("WARK04") is entry
    assert lookup("K04W") is entry
    assert lookup("WARK04") is entry
    assert lookup(" wark04 ") is entry
    assert by_short("k04w") is entry


def test_unknown_codes_are_none() -> None:
    assert by_short("ZZZZ") is None
    assert by_long("ALTZZZ") is None
    assert lookup("") is None
    assert by_short("WARK04") is None
    assert by_long("K04W") is None


def test_entries_are_frozen() -> None:
    entry = CATALOGUE[0]
    with pytest.raises(AttributeError):
        entry.long = "X"  # type: ignore[misc]
    assert isinstance(CATALOGUE, tuple)
