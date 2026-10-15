import json
from pathlib import Path

import build_old_format as bof
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def test_converts_objects_to_header_and_string_rows() -> None:
    raw = (
        b'[{"time_tag":"2026-10-08T00:00:00","Kp":1.00,"a_running":4,'
        b'"station_count":8},'
        b'{"time_tag":"2026-10-08T03:00:00","Kp":1.67,"a_running":6,'
        b'"station_count":7}]'
    )
    assert bof.to_old_format(raw, millis=True) == (
        b'[["time_tag","Kp","a_running","station_count"],'
        b'["2026-10-08 00:00:00.000","1.00","4","8"],'
        b'["2026-10-08 03:00:00.000","1.67","6","7"]]'
    )


def test_without_millis_and_with_null_and_strings() -> None:
    raw = b'[{"time_tag":"2026-10-08T00:00:00","kp":-1.5,"observed":"x","s":null}]'
    assert bof.to_old_format(raw, millis=False) == (
        b'[["time_tag","kp","observed","s"],["2026-10-08 00:00:00","-1.5","x",null]]'
    )


def test_rejects_records_with_different_keys() -> None:
    raw = b'[{"time_tag":"2026-10-08T00:00:00","a":1},{"time_tag":"x","b":2}]'
    with pytest.raises(ValueError, match="keys"):
        bof.to_old_format(raw, millis=False)


@pytest.mark.parametrize("raw", [b"[]", b'{"a": 1}', b"[[1, 2]]"])
def test_rejects_documents_that_are_not_arrays_of_objects(raw: bytes) -> None:
    with pytest.raises(ValueError, match="array of objects"):
        bof.to_old_format(raw, millis=False)


def test_rejects_bad_time_tag() -> None:
    with pytest.raises(ValueError, match="time_tag"):
        bof.to_old_format(b'[{"time_tag":"2026-10-08 00:00","a":1}]', millis=False)


@pytest.mark.parametrize(
    ("built", "recorded", "millis"),
    [
        ("kp-3h/2026-10-15-built.json", "kp-3h/2026-10-15.json", True),
        ("dst/2026-10-15-built.json", "dst/2026-10-15.json", False),
        ("f107-30-day/2026-10-15-built.json", "f107-30-day/2026-10-15.json", False),
    ],
)
def test_built_fixtures_match_their_recorded_source(
    built: str, recorded: str, millis: bool
) -> None:
    source = (FIXTURES / recorded).read_bytes()
    assert (FIXTURES / built).read_bytes() == bof.to_old_format(source, millis=millis)
    header, *rows = json.loads((FIXTURES / built).read_bytes())
    assert header[0] == "time_tag"
    assert len(rows) == len(json.loads(source))
