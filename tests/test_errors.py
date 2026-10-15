from datetime import UTC, datetime, timedelta, timezone

import pytest

from swpc_kit.errors import (
    ParseError,
    SourceNotReady,
    StaleData,
    SwpcError,
    UnexpectedContent,
)


@pytest.mark.parametrize(
    "cls", [SourceNotReady, UnexpectedContent, ParseError, StaleData]
)
def test_every_error_is_a_swpc_error(cls: type[SwpcError]) -> None:
    assert issubclass(cls, SwpcError)
    assert issubclass(cls, Exception)


def test_errors_are_distinct() -> None:
    classes = [SourceNotReady, UnexpectedContent, ParseError, StaleData]
    for a in classes:
        for b in classes:
            if a is not b:
                assert not issubclass(a, b)


def test_errors_are_exported_from_package() -> None:
    import swpc_kit

    assert swpc_kit.SwpcError is SwpcError
    assert swpc_kit.SourceNotReady is SourceNotReady
    assert swpc_kit.UnexpectedContent is UnexpectedContent
    assert swpc_kit.ParseError is ParseError
    assert swpc_kit.StaleData is StaleData


def test_source_not_ready_message() -> None:
    err = SourceNotReady("JSON ends before the closing bracket")
    assert str(err) == "JSON ends before the closing bracket"


def test_unexpected_content_message() -> None:
    err = UnexpectedContent("got an HTML page instead of JSON")
    assert str(err) == "got an HTML page instead of JSON"


def test_parse_error_without_location() -> None:
    err = ParseError("bad value")
    assert err.field is None
    assert err.line is None
    assert err.index is None
    assert str(err) == "bad value"


def test_parse_error_names_field_and_line() -> None:
    err = ParseError("not a number", field="Kp", line=4)
    assert err.field == "Kp"
    assert err.line == 4
    assert err.index is None
    assert str(err) == "not a number (field 'Kp', line 4)"


def test_parse_error_names_field_and_record_index() -> None:
    err = ParseError("missing", field="time_tag", index=0)
    assert err.index == 0
    assert str(err) == "missing (field 'time_tag', record 0)"


def test_parse_error_line_only() -> None:
    assert str(ParseError("unknown section", line=12)) == "unknown section (line 12)"


@pytest.mark.parametrize("line", [0, -1])
def test_parse_error_rejects_non_positive_line(line: int) -> None:
    with pytest.raises(ValueError, match="1-based"):
        ParseError("x", line=line)


def test_parse_error_rejects_negative_index() -> None:
    with pytest.raises(ValueError, match="index"):
        ParseError("x", index=-1)


def test_parse_error_can_be_raised_and_caught_as_swpc_error() -> None:
    with pytest.raises(SwpcError, match="field 'flux'"):
        raise ParseError("negative flux", field="flux", index=3)


def test_stale_data_attributes_and_message() -> None:
    data_time = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    err = StaleData(
        data_time=data_time,
        max_age=timedelta(minutes=30),
        age=timedelta(hours=2),
    )
    assert err.data_time == data_time
    assert err.max_age == timedelta(minutes=30)
    assert err.age == timedelta(hours=2)
    assert str(err) == (
        "data from 2026-10-15T12:00:00+00:00 is 2:00:00 old, "
        "more than the allowed 0:30:00"
    )


def test_stale_data_rejects_naive_datetime() -> None:
    naive = datetime(2026, 10, 15, 12, 0)  # noqa: DTZ001
    with pytest.raises(ValueError, match="UTC"):
        StaleData(data_time=naive, max_age=timedelta(0), age=timedelta(1))


def test_stale_data_rejects_non_utc_datetime() -> None:
    cet = datetime(2026, 10, 15, 12, 0, tzinfo=timezone(timedelta(hours=1)))
    with pytest.raises(ValueError, match="UTC"):
        StaleData(data_time=cet, max_age=timedelta(0), age=timedelta(1))


def test_stale_data_accepts_any_zero_offset_tzinfo() -> None:
    zero = datetime(2026, 10, 15, 12, 0, tzinfo=timezone(timedelta(0)))
    err = StaleData(data_time=zero, max_age=timedelta(0), age=timedelta(1))
    assert err.data_time == zero
