"""Tolerance per record in the JSON products made of records (D-015).

A record that cannot be read goes to the model's ``skipped``, with its index,
the field and the reason, and the other records are read. The product fails
only when no record is good, or when a field is missing from every record (a
format no parser knows). Bulletins and grids stay strict.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from swpc_kit.errors import ParseError, UnexpectedContent
from swpc_kit.models import SkippedRecord
from swpc_kit.parse import (
    parse_alerts,
    parse_f107_flux_30_day,
    parse_goes_integral_electrons,
    parse_goes_integral_protons,
    parse_goes_xray_flares,
    parse_goes_xrays,
    parse_kyoto_dst,
    parse_planetary_k_index,
    parse_planetary_k_index_1m,
    parse_planetary_k_index_forecast,
    parse_rtsw_mag_1m,
    parse_rtsw_wind_1m,
    parse_three_day_forecast,
)

FIXTURES = Path(__file__).parent / "fixtures"


def records(name: str) -> list[dict[str, Any]]:
    document = json.loads((FIXTURES / name).read_text(encoding="utf-8-sig"))
    assert isinstance(document[0], dict), name
    return list(document)


def dump(items: list[Any]) -> bytes:
    return json.dumps(items).encode()


def items(model: Any) -> tuple[Any, ...]:
    return tuple(getattr(model, "values", None) or model.messages)


# (parser, fixture, field, a value that makes one record unreadable)
PRODUCTS = [
    (parse_planetary_k_index, "kp-3h/2026-10-15.json", "Kp", 12),
    (parse_planetary_k_index_forecast, "kp-forecast/2026-10-15.json", "kp", -1),
    (parse_planetary_k_index_1m, "kp-1m/2026-10-15.json", "kp", "3X"),
    (parse_kyoto_dst, "dst/2026-10-15.json", "dst", 1.5),
    (parse_f107_flux_30_day, "f107-30-day/2026-10-15.json", "flux", -1),
    (parse_rtsw_mag_1m, "rtsw-mag-1m/2026-10-15.json", "bt", -1),
    (parse_rtsw_wind_1m, "rtsw-wind-1m/2026-10-15.json", "proton_density", -1),
    (parse_goes_xrays, "goes-xrays-1-day/2026-10-15.json", "flux", "x"),
    (parse_goes_integral_protons, "goes-protons-1-day/2026-10-15.json", "energy", "x"),
    (
        parse_goes_integral_electrons,
        "goes-electrons-1-day/2026-10-29.json",
        "energy",
        "x",
    ),
    (parse_goes_xray_flares, "goes-flares-7-day/2026-10-29.json", "max_class", "Q1"),
    (parse_alerts, "alerts/2026-10-15.json", "issue_datetime", "13 Oct 2026"),
]
IDS = [name.split("/")[0] for _, name, _, _ in PRODUCTS]


@pytest.mark.parametrize(("parse", "name", "field", "bad"), PRODUCTS, ids=IDS)
def test_a_bad_record_is_skipped_and_the_others_are_read(
    parse: Callable[[bytes], Any], name: str, field: str, bad: object
) -> None:
    good = records(name)
    assert len(good) >= 3
    complete = parse(dump(good))
    assert complete.skipped == ()
    index = len(good) // 2
    broken = [dict(r) for r in good]
    broken[index][field] = bad
    model = parse(dump(broken))
    assert len(items(model)) == len(items(complete)) - 1
    assert len(model.skipped) == 1
    skipped = model.skipped[0]
    assert isinstance(skipped, SkippedRecord)
    assert skipped.index == index
    assert skipped.field == field
    assert skipped.reason


@pytest.mark.parametrize(("parse", "name", "field", "bad"), PRODUCTS, ids=IDS)
def test_no_good_record_is_a_parse_error(
    parse: Callable[[bytes], Any], name: str, field: str, bad: object
) -> None:
    broken = [{**r, field: bad} for r in records(name)[:3]]
    with pytest.raises(ParseError) as info:
        parse(dump(broken))
    assert info.value.field == field
    assert info.value.index == 0


@pytest.mark.parametrize(("parse", "name", "field", "bad"), PRODUCTS, ids=IDS)
def test_a_field_missing_from_every_record_is_a_new_format(
    parse: Callable[[bytes], Any], name: str, field: str, bad: object
) -> None:
    gone = [{k: v for k, v in r.items() if k != field} for r in records(name)[:3]]
    with pytest.raises(UnexpectedContent, match=f"'{field}' missing from every"):
        parse(dump(gone))


@pytest.mark.parametrize(("parse", "name", "field", "bad"), PRODUCTS, ids=IDS)
def test_a_field_missing_from_some_records_skips_them(
    parse: Callable[[bytes], Any], name: str, field: str, bad: object
) -> None:
    some = records(name)
    some[0] = {k: v for k, v in some[0].items() if k != field}
    model = parse(dump(some))
    assert [(s.index, s.field) for s in model.skipped] == [(0, field)]
    assert "missing" in model.skipped[0].reason


# --- repeated times and plausibility ----------------------------------------


def test_a_repeated_time_skips_the_second_record() -> None:
    kp = records("kp-3h/2026-10-15.json")
    model = parse_planetary_k_index(dump([*kp, {**kp[1], "Kp": 9.0}]))
    assert len(model.values) == len(kp)
    assert model.values[1].kp == kp[1]["Kp"]
    assert [(s.index, s.field) for s in model.skipped] == [(len(kp), "time_tag")]
    assert "twice" in model.skipped[0].reason


@pytest.mark.parametrize(
    ("parse", "name", "field", "value"),
    [
        (parse_kyoto_dst, "dst/2026-10-15.json", "dst", 99999),
        (parse_kyoto_dst, "dst/2026-10-15.json", "dst", -99999),
        (parse_f107_flux_30_day, "f107-30-day/2026-10-15.json", "flux", 0),
        (parse_f107_flux_30_day, "f107-30-day/2026-10-15.json", "flux", 9999.9),
        (parse_rtsw_mag_1m, "rtsw-mag-1m/2026-10-15.json", "bz_gsm", -99999.0),
        (parse_rtsw_mag_1m, "rtsw-mag-1m/2026-10-15.json", "bt", 99999.0),
        (parse_rtsw_wind_1m, "rtsw-wind-1m/2026-10-15.json", "proton_speed", 99999),
        (parse_goes_xrays, "goes-xrays-1-day/2026-10-15.json", "flux", 1.0),
        (
            parse_goes_integral_protons,
            "goes-protons-1-day/2026-10-15.json",
            "flux",
            1e9,
        ),
        (
            parse_goes_integral_electrons,
            "goes-electrons-1-day/2026-10-29.json",
            "flux",
            1e9,
        ),
        (
            parse_goes_xray_flares,
            "goes-flares-7-day/2026-10-29.json",
            "max_xrlong",
            1.0,
        ),
    ],
)
def test_implausible_values_are_skipped(
    parse: Callable[[bytes], Any], name: str, field: str, value: float
) -> None:
    good = records(name)
    broken = [dict(r) for r in good]
    broken[2][field] = value
    model = parse(dump(broken))
    assert [(s.index, s.field) for s in model.skipped] == [(2, field)]


@pytest.mark.parametrize(
    "changes",
    [
        {"kp_index": 7},  # the digit of "3M" is 3
        {"estimated_kp": 2.0},  # "3M" is 2.67
        {"kp": "3Z"},  # with estimated_kp 2.67
    ],
)
def test_incoherent_one_minute_kp_is_skipped(changes: dict[str, Any]) -> None:
    good = records("kp-1m/2026-10-15.json")
    index = next(i for i, r in enumerate(good) if r["kp"] == "3M")
    broken = [dict(r) for r in good]
    broken[index].update(changes)
    model = parse_planetary_k_index_1m(dump(broken))
    assert [s.index for s in model.skipped] == [index]


@pytest.mark.parametrize("text", ["0_5", "1_0.5", "+5", "5.", ".5", "nan", "inf"])
def test_quoted_numbers_must_be_plain_decimals(text: str) -> None:
    kp = records("kp-3h/2026-10-15.json")
    broken = [dict(r) for r in kp]
    broken[3]["Kp"] = text
    model = parse_planetary_k_index(dump(broken))
    assert [(s.index, s.field) for s in model.skipped] == [(3, "Kp")]


def test_rtsw_flags_absent_from_the_format_become_none() -> None:
    flags = ("max_data_flag", "max_telemetry_flag", "overall_quality")
    mag = [
        {k: v for k, v in r.items() if k not in flags}
        for r in records("rtsw-mag-1m/2026-10-15.json")
    ]
    model = parse_rtsw_mag_1m(dump(mag))
    assert model.skipped == ()
    assert all(v.max_data_flag is None for v in model.values)


def test_alerts_message_without_serial_number_is_skipped() -> None:
    alerts = records("alerts/2026-10-15.json")
    index = next(i for i, r in enumerate(alerts) if "Serial Number:" in r["message"])
    broken = [dict(r) for r in alerts]
    lines = broken[index]["message"].splitlines()
    broken[index]["message"] = "\r\n".join(
        line for line in lines if not line.startswith("Serial Number:")
    )
    model = parse_alerts(dump(broken))
    assert len(model.messages) == len(alerts) - 1
    assert [s.index for s in model.skipped] == [index]


# --- what stays strict -------------------------------------------------------


def test_bulletins_stay_strict_and_check_the_g_scale() -> None:
    text = (FIXTURES / "3-day-forecast/2022-09-22-sample.txt").read_text()
    assert "5.33 (G1)" in text
    with pytest.raises(ParseError, match="G1"):
        parse_three_day_forecast(text.replace("5.33 (G1)", "2.00 (G1)"))
