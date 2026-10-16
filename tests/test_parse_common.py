from datetime import UTC, datetime

import pytest

from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.parse._common import Record, json_records, load_json, parse_time

# --- load_json --------------------------------------------------------------


def test_load_json_accepts_str_bytes_and_bom() -> None:
    assert load_json('[{"a": 1}]') == [{"a": 1}]
    assert load_json(b'[{"a": 1}]') == [{"a": 1}]
    assert load_json(b'\xef\xbb\xbf[{"a": 1}]') == [{"a": 1}]
    assert load_json("﻿[1]") == [1]


@pytest.mark.parametrize("raw", [b"", b"   \n", ""])
def test_empty_content_is_not_ready(raw: bytes | str) -> None:
    with pytest.raises(SourceNotReady, match="empty"):
        load_json(raw)


@pytest.mark.parametrize(
    "raw",
    [
        b'[{"time_tag":"2026-10-08T00:00:00","Kp":1.00},{"time_tag":"2026-10-08T03',
        b'[{"time_tag":"2026-10-08T00:00:00","Kp":1.00},',
        b'[{"time_tag":"2026-10-08T00:00:00","Kp":1.0',
        b"[",
    ],
)
def test_truncated_json_is_not_ready(raw: bytes) -> None:
    with pytest.raises(SourceNotReady, match="truncated"):
        load_json(raw)


@pytest.mark.parametrize(
    "raw",
    [
        b"<!DOCTYPE html><html><body>Moved</body></html>",
        b"\n  <html>",
        b"<?xml version='1.0'?><error/>",
    ],
)
def test_markup_is_unexpected(raw: bytes) -> None:
    with pytest.raises(UnexpectedContent, match="HTML"):
        load_json(raw)


def test_invalid_json_in_the_middle_is_unexpected() -> None:
    with pytest.raises(UnexpectedContent, match="not valid JSON"):
        load_json(b'[{"a": 1} {"a": 2}]')


def test_undecodable_bytes_are_unexpected() -> None:
    with pytest.raises(UnexpectedContent, match="UTF-8"):
        load_json(b"\xff\xfe[\x00")


# --- json_records -----------------------------------------------------------


def test_records_from_array_of_objects() -> None:
    records = json_records(b'[{"t": "a", "v": 1}, {"t": "b", "v": 2, "x": 0}]')
    assert [(r.index, r.data) for r in records] == [
        (0, {"t": "a", "v": 1}),
        (1, {"t": "b", "v": 2, "x": 0}),
    ]


def test_records_from_array_of_arrays_with_header() -> None:
    records = json_records(b'[["t","v"],["a","1"],["b",null]]')
    assert [(r.index, r.data) for r in records] == [
        (1, {"t": "a", "v": "1"}),
        (2, {"t": "b", "v": None}),
    ]


@pytest.mark.parametrize("raw", [b"[]", b'[["t","v"]]'])
def test_no_records_is_not_ready(raw: bytes) -> None:
    with pytest.raises(SourceNotReady, match="no records"):
        json_records(raw)


@pytest.mark.parametrize("raw", [b'{"a": 1}', b"[1, 2]", b'"text"', b"[[1, 2]]"])
def test_unknown_shapes_are_unexpected(raw: bytes) -> None:
    with pytest.raises(UnexpectedContent):
        json_records(raw)


def test_row_length_mismatch_names_the_row() -> None:
    with pytest.raises(ParseError, match="record 2") as info:
        json_records(b'[["t","v"],["a","1"],["b"]]')
    assert info.value.index == 2


def test_mixed_rows_name_the_record() -> None:
    with pytest.raises(ParseError) as info:
        json_records(b'[{"t": "a"}, ["b"]]')
    assert info.value.index == 1


# --- Record accessors -------------------------------------------------------


def _rec(**data: object) -> Record:
    return Record(3, data)


def test_missing_field_names_field_and_record() -> None:
    with pytest.raises(ParseError, match="missing") as info:
        _rec(a=1).get_float("Kp")
    assert info.value.field == "Kp"
    assert info.value.index == 3


@pytest.mark.parametrize(
    ("value", "expected"), [(1, 1.0), (2.67, 2.67), ("2.67", 2.67)]
)
def test_get_float_accepts_numbers_and_numeric_strings(
    value: object, expected: float
) -> None:
    assert _rec(v=value).get_float("v") == expected


@pytest.mark.parametrize(
    "value", [None, True, "", "abc", "nan", "inf", [1], float("nan")]
)
def test_get_float_rejects_non_numbers(value: object) -> None:
    with pytest.raises(ParseError, match="number") as info:
        _rec(v=value).get_float("v")
    assert info.value.field == "v"


def test_get_float_range() -> None:
    assert _rec(v=9).get_float("v", minimum=0, maximum=9) == 9
    with pytest.raises(ParseError, match="out of range"):
        _rec(v=9.33).get_float("v", minimum=0, maximum=9)
    with pytest.raises(ParseError, match="out of range"):
        _rec(v="-0.1").get_float("v", minimum=0)


@pytest.mark.parametrize(("value", "expected"), [(4, 4), ("-17", -17), (" 8 ", 8)])
def test_get_int(value: object, expected: int) -> None:
    assert _rec(v=value).get_int("v") == expected


@pytest.mark.parametrize("value", [None, False, 4.5, "4.5", "x", 4.0])
def test_get_int_rejects_non_integers(value: object) -> None:
    with pytest.raises(ParseError, match="integer"):
        _rec(v=value).get_int("v")


def test_get_int_range() -> None:
    with pytest.raises(ParseError, match="out of range"):
        _rec(v=-1).get_int("v", minimum=0)


def test_optional_accessors() -> None:
    rec = _rec(a=None, b="G1", c="20")
    assert rec.get_optional_str("a") is None
    assert rec.get_optional_str("b") == "G1"
    assert rec.get_optional_int("a") is None
    assert rec.get_optional_int("c") == 20
    with pytest.raises(ParseError, match="missing"):
        rec.get_optional_str("zzz")


def test_get_str() -> None:
    assert _rec(v="3Z").get_str("v") == "3Z"
    with pytest.raises(ParseError, match="string"):
        _rec(v=3).get_str("v")
    with pytest.raises(ParseError, match="string"):
        _rec(v=None).get_str("v")


def test_get_time() -> None:
    expected = datetime(2026, 10, 8, 3, 0, tzinfo=UTC)
    assert _rec(t="2026-10-08T03:00:00").get_time("t") == expected
    with pytest.raises(ParseError, match="time") as info:
        _rec(t="yesterday").get_time("t")
    assert info.value.field == "t"


def test_get_optional_float() -> None:
    rec = _rec(a=None, b=4.75, c="1.5", d=-9999)
    assert rec.get_optional_float("a") is None
    assert rec.get_optional_float("b") == 4.75
    assert rec.get_optional_float("c") == 1.5
    assert rec.get_optional_float("a", minimum=0) is None
    with pytest.raises(ParseError, match="out of range") as info:
        rec.get_optional_float("d", minimum=0)
    assert info.value.field == "d"
    with pytest.raises(ParseError, match="missing"):
        rec.get_optional_float("zzz")
    with pytest.raises(ParseError, match="number"):
        _rec(v=True).get_optional_float("v")


def test_get_bool() -> None:
    rec = _rec(a=True, b=False, c=None, d="true", e=1)
    assert rec.get_bool("a") is True
    assert rec.get_bool("b") is False
    assert rec.get_optional_bool("c") is None
    assert rec.get_optional_bool("a") is True
    for field in ("c", "d", "e"):
        with pytest.raises(ParseError, match="boolean") as info:
            rec.get_bool(field)
        assert info.value.field == field
    with pytest.raises(ParseError, match="missing"):
        rec.get_optional_bool("zzz")


# --- parse_time -------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "2026-10-08T03:00:00",
        "2026-10-08 03:00:00",
        "2026-10-08 03:00:00.000",
        "2026-10-08T03:00:00Z",
        "2026-10-08T03:00:00+00:00",
        "2026-10-08T05:00:00+02:00",
        "2026-10-08T03:00",
    ],
)
def test_parse_time_forms(text: str) -> None:
    value = parse_time(text)
    assert value == datetime(2026, 10, 8, 3, 0, tzinfo=UTC)
    assert value.tzinfo is UTC


@pytest.mark.parametrize(
    "text",
    ["2026-10-08", "20261008T030000", "2026-13-08T00:00:00", "", " 2026-10-08T03:00"],
)
def test_parse_time_rejects(text: str) -> None:
    with pytest.raises(ValueError, match="time"):
        parse_time(text)
