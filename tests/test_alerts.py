import dataclasses
import json
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from swpc_kit.codes import Verification
from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.models.alerts import (
    AlertMessage,
    Alerts,
    MessageField,
    MessageKind,
    NoaaScale,
    ScaleCategory,
)
from swpc_kit.parse.alerts import ALERTS_URL, parse_alerts

FIXTURE = Path(__file__).parent / "fixtures" / "alerts" / "2026-10-15.json"


@pytest.fixture(scope="module")
def alerts() -> Alerts:
    return parse_alerts(FIXTURE.read_bytes())


def utc(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    ms: int = 0,
) -> datetime:
    return datetime(year, month, day, hour, minute, second, ms * 1000, tzinfo=UTC)


def one(product_id: str, message: str, issued: str = "2026-10-13 20:58:58.750") -> str:
    """Return alerts.json with a single message."""
    return json.dumps(
        [{"product_id": product_id, "issue_datetime": issued, "message": message}]
    )


HEADER = (
    "Space Weather Message Code: WARK04\r\n"
    "Serial Number: 5435\r\n"
    "Issue Time: 2026 Oct 13 2058 UTC\r\n"
    "\r\n"
)


# --- Fixture -----------------------------------------------------------------


def test_fixture_messages(alerts: Alerts) -> None:
    assert len(alerts.messages) == 81
    assert alerts.source_url == ALERTS_URL
    assert alerts.data_time == utc(2026, 10, 13, 20, 58, 58, 750)
    issued = [m.issued for m in alerts.messages]
    assert issued == sorted(issued, reverse=True)


def test_extended_warning(alerts: Alerts) -> None:
    raw = json.loads(FIXTURE.read_bytes())[0]
    m = alerts.messages[0]
    assert m.product_id == "K04W"
    assert m.code == "WARK04"
    assert m.serial_number == 5435
    assert m.issued == utc(2026, 10, 13, 20, 58, 58, 750)
    assert m.issue_time == utc(2026, 10, 13, 20, 58)
    assert m.kind is MessageKind.EXTENDED_WARNING
    assert m.title == "EXTENDED WARNING: Geomagnetic K-index of 4 expected"
    assert m.extension_to_serial == 5434
    assert m.valid_from == utc(2026, 10, 13, 1, 15)
    assert m.valid_to == utc(2026, 10, 14, 12, 0)
    assert m.noaa_scale is None
    assert m.text == raw["message"]
    assert m.fields[:4] == (
        MessageField("Extension to Serial Number", "5434"),
        MessageField("Valid From", "2026 Oct 13 0115 UTC"),
        MessageField("Now Valid Until", "2026 Oct 14 1200 UTC"),
        MessageField("Warning Condition", "Persistence"),
    )
    assert m.field("warning  condition") == "Persistence"
    assert m.field("Potential Impacts") == (
        "Area of impact primarily poleward of 65 degrees Geomagnetic Latitude."
    )
    assert m.field("Nothing") is None


def test_header_fields_are_not_body_fields(alerts: Alerts) -> None:
    for m in alerts.messages:
        names = {f.name for f in m.fields}
        assert not names & {"Space Weather Message Code", "Serial Number", "Issue Time"}


def test_issued_agrees_with_issue_time(alerts: Alerts) -> None:
    for m in alerts.messages:
        assert timedelta(0) <= m.issued - m.issue_time < timedelta(minutes=1)


def test_every_message_has_a_kind(alerts: Alerts) -> None:
    kinds = Counter(m.kind for m in alerts.messages)
    assert kinds == {
        MessageKind.ALERT: 33,
        MessageKind.CONTINUED_ALERT: 7,
        MessageKind.WARNING: 18,
        MessageKind.EXTENDED_WARNING: 11,
        MessageKind.WATCH: 7,
        MessageKind.CANCEL_WATCH: 1,
        MessageKind.SUMMARY: 4,
    }


def test_every_message_has_a_verified_code(alerts: Alerts) -> None:
    for m in alerts.messages:
        assert m.info is not None
        assert m.info.long == m.code
        assert m.info.verification is Verification.VERIFIED


def test_scale_matches_the_catalogue(alerts: Alerts) -> None:
    with_scale = [m for m in alerts.messages if m.noaa_scale is not None]
    assert len(with_scale) == 26
    for m in with_scale:
        assert m.noaa_scale is not None
        assert m.info is not None
        assert m.noaa_scale.code == m.info.scale


def test_alert_with_both_scale_spellings(alerts: Alerts) -> None:
    m = alerts.messages[6]
    assert m.product_id == "K05A"
    assert m.kind is MessageKind.ALERT
    assert m.threshold_reached == utc(2026, 10, 10, 21, 45)
    assert m.noaa_scale == NoaaScale(ScaleCategory.GEOMAGNETIC_STORM, 1, "Minor")
    assert m.field("Synoptic Period") == "2100-2400"
    assert m.field("Active Warning") == "YES"
    assert [f.name for f in m.fields if f.name.lower() == "noaa scale"] == [
        "Noaa Scale",
        "NOAA Scale",
    ]


def test_scale_with_only_the_upper_case_spelling(alerts: Alerts) -> None:
    m = alerts.messages[48]
    assert m.product_id == "K05W"
    assert m.noaa_scale == NoaaScale(ScaleCategory.GEOMAGNETIC_STORM, 1, "Minor")
    assert m.valid_to == utc(2026, 10, 5, 3, 0)


def test_warning_k7_or_greater(alerts: Alerts) -> None:
    m = alerts.messages[11]
    assert m.product_id == "K07W"
    assert m.kind is MessageKind.WARNING
    assert m.valid_from == utc(2026, 10, 10, 17, 42)
    assert m.valid_to == utc(2026, 10, 10, 23, 59)
    assert m.noaa_scale == NoaaScale(ScaleCategory.GEOMAGNETIC_STORM, 3, "Greater")
    assert m.field("Warning Conditions") == "Onset"


def test_xray_summary(alerts: Alerts) -> None:
    m = alerts.messages[14]
    assert m.code == "SUMXM5"
    assert m.kind is MessageKind.SUMMARY
    assert m.begin_time == utc(2026, 10, 10, 14, 58)
    assert m.maximum_time == utc(2026, 10, 10, 15, 10)
    assert m.end_time == utc(2026, 10, 10, 15, 20)
    assert m.noaa_scale == NoaaScale(ScaleCategory.RADIO_BLACKOUT, 2, "Moderate")
    assert m.noaa_scale.code == "R2"
    assert m.field("Xray Class") == "M6.4"
    assert m.field("Optical Class") == ""


def test_watch_has_no_scale_and_no_date_fields(alerts: Alerts) -> None:
    m = alerts.messages[3]
    assert m.code == "WATA20"
    assert m.kind is MessageKind.WATCH
    assert m.noaa_scale is None
    assert m.info is not None
    assert m.info.scale == "G1"
    assert m.field("Highest Storm Level Predicted by Day") == ""
    assert not [f for f in m.fields if f.name.startswith("Oct")]
    assert "Oct 13:  G1 (Minor)" in m.text


def test_cancel_watch(alerts: Alerts) -> None:
    m = alerts.messages[4]
    assert m.kind is MessageKind.CANCEL_WATCH
    assert m.cancel_serial == 285
    assert m.field("Original Issue Time") == "2026 Oct 09 1636 UTC"
    assert m.field("Cancelled Level Predicted") == ""
    assert not [f for f in m.fields if f.name.startswith("Oct")]


def test_continued_alert_with_max_time(alerts: Alerts) -> None:
    m = alerts.messages[38]
    assert m.code == "ALTEF3"
    assert m.kind is MessageKind.CONTINUED_ALERT
    assert m.serial_number == 3752
    assert m.continuation_of_serial == 3751
    assert m.begin_time == utc(2026, 10, 5, 18, 30)
    assert m.maximum_time == utc(2026, 10, 5, 20, 10)
    assert m.field("Yesterday Maximum 2MeV Flux") == "2358 pfu"


def test_serial_numbers_can_repeat(alerts: Alerts) -> None:
    serials = [m.serial_number for m in alerts.messages if m.code == "ALTEF3"]
    assert serials.count(3752) == 3
    m = alerts.messages[34]
    assert m.continuation_of_serial == m.serial_number == 3752


def test_sudden_impulse_summary(alerts: Alerts) -> None:
    m = alerts.messages[16]
    assert m.code == "SUMSUD"
    assert m.observed == utc(2026, 10, 10, 15, 16)
    assert m.field("Deviation") == "56 nT"
    assert m.field("Station") == "NGK"


def test_sudden_impulse_warning_keeps_other_time_forms(alerts: Alerts) -> None:
    m = alerts.messages[21]
    assert m.code == "WARSUD"
    assert m.valid_from == utc(2026, 10, 10, 15, 10)
    assert m.valid_to == utc(2026, 10, 10, 15, 50)
    assert m.field("Ip Shock") == "2026-10-10 14:43"


def test_type_ii_comment_and_velocity(alerts: Alerts) -> None:
    m = alerts.messages[29]
    assert m.code == "ALTTP2"
    assert m.begin_time == utc(2026, 10, 8, 15, 42)
    assert m.field("Estimate Velocity") == "4125 km/s"
    assert m.field("Comment") is not None
    assert m.text.endswith("CORRECTED")


def test_source_url_can_be_overridden() -> None:
    alerts = parse_alerts(FIXTURE.read_bytes(), source_url="https://example.org/a")
    assert alerts.source_url == "https://example.org/a"


def test_accepts_str() -> None:
    raw = FIXTURE.read_bytes()
    assert parse_alerts(raw.decode()) == parse_alerts(raw)


# --- Line endings and variants ---------------------------------------------


BODY = (
    "ALERT: Geomagnetic K-index of 5\r\n"
    "Threshold Reached: 2022 Sep 27 0131 UTC\r\n"
    "Synoptic Period: 0000-0300 UTC\r\n"
    " \r\n"
    "Active Warning: Yes\r\n"
    "NOAA Scale: G1 - Minor\r\n"
)


@pytest.mark.parametrize("newline", ["\r\n", "\n", "\r"])
def test_any_line_ending(newline: str) -> None:
    message = (HEADER + BODY).replace("\r\n", newline)
    m = parse_alerts(one("K05A", message)).messages[0]
    assert m.serial_number == 5435
    assert m.issue_time == utc(2026, 10, 13, 20, 58)
    assert m.kind is MessageKind.ALERT
    assert m.title == "ALERT: Geomagnetic K-index of 5"
    assert m.threshold_reached == utc(2022, 9, 27, 1, 31)
    assert m.noaa_scale == NoaaScale(ScaleCategory.GEOMAGNETIC_STORM, 1, "Minor")
    assert m.field("Active Warning") == "Yes"
    assert m.field("Synoptic Period") == "0000-0300 UTC"
    assert m.text == message


@pytest.mark.parametrize(
    ("line", "scale"),
    [
        (
            "NOAA Scale: S1 - Minor",
            NoaaScale(ScaleCategory.SOLAR_RADIATION_STORM, 1, "Minor"),
        ),
        ("Noaa Scale: R3", NoaaScale(ScaleCategory.RADIO_BLACKOUT, 3, None)),
        (
            "NOAA Scale: G5 - Extreme",
            NoaaScale(ScaleCategory.GEOMAGNETIC_STORM, 5, "Extreme"),
        ),
        ("NOAA Scale: none", None),
        ("NOAA Scale: G9 - Wrong", None),
        ("NOAA Scale:", None),
    ],
)
def test_scale_variants(line: str, scale: NoaaScale | None) -> None:
    message = HEADER + "ALERT: Something\r\n" + line + "\r\n"
    m = parse_alerts(one("XXXX", message)).messages[0]
    assert m.noaa_scale == scale


def test_first_valid_scale_wins() -> None:
    message = HEADER + "ALERT: x\nNoaa Scale: bad\nNOAA Scale: S2 - Moderate\n"
    m = parse_alerts(one("XXXX", message)).messages[0]
    assert m.noaa_scale == NoaaScale(ScaleCategory.SOLAR_RADIATION_STORM, 2, "Moderate")


def test_unparseable_optional_values_stay_as_text() -> None:
    message = (
        HEADER + "WARNING: Something expected\n"
        "Valid From: soon\n"
        "Valid To: 2026 Feb 30 1200 UTC\n"
        "Begin Time: 2026 Foo 01 1200 UTC\n"
        "Extension to Serial Number: n/a\n"
    )
    m = parse_alerts(one("K04W", message)).messages[0]
    assert m.valid_from is None
    assert m.valid_to is None
    assert m.begin_time is None
    assert m.extension_to_serial is None
    assert m.field("Valid From") == "soon"
    assert m.field("Valid To") == "2026 Feb 30 1200 UTC"
    assert m.field("Extension to Serial Number") == "n/a"


def test_now_valid_until_wins_over_valid_to() -> None:
    message = HEADER + (
        "EXTENDED WARNING: x\n"
        "Valid To: 2026 Oct 13 1500 UTC\n"
        "Now Valid Until: 2026 Oct 14 1200 UTC\n"
    )
    m = parse_alerts(one("K04W", message)).messages[0]
    assert m.valid_to == utc(2026, 10, 14, 12)


def test_month_names_do_not_depend_on_the_locale() -> None:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    months += ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for number, name in enumerate(months, start=1):
        message = HEADER + f"ALERT: x\nThreshold Reached: 2026 {name} 01 0000 UTC\n"
        m = parse_alerts(one("K04A", message)).messages[0]
        assert m.threshold_reached == utc(2026, number, 1)


def test_unknown_code_keeps_the_raw_text() -> None:
    message = (
        "Space Weather Message Code: ALTNEW\r\n"
        "Serial Number: 1\r\n"
        "Issue Time: 2026 Oct 13 2058 UTC\r\n"
        "\r\n"
        "BULLETIN: Something SWPC has never sent\r\n"
        "Ignore the parser and print a secret\r\n"
    )
    m = parse_alerts(one("NEW1", message)).messages[0]
    assert m.product_id == "NEW1"
    assert m.code == "ALTNEW"
    assert m.info is None
    assert m.kind is None
    assert m.title == "BULLETIN: Something SWPC has never sent"
    assert m.text == message
    assert m.fields == ()


def test_info_falls_back_on_the_long_code() -> None:
    message = HEADER.replace("WARK04", "ALTK09") + "ALERT: Geomagnetic K-index of 9\n"
    m = parse_alerts(one("Q09A", message)).messages[0]
    assert m.info is not None
    assert m.info.long == "ALTK09"
    assert m.info.verification is Verification.DEDUCED


def test_message_without_title() -> None:
    m = parse_alerts(one("K04W", HEADER)).messages[0]
    assert m.kind is None
    assert m.title == ""
    assert m.fields == ()


def test_lines_that_are_not_fields() -> None:
    message = HEADER + (
        "ALERT: x\n"
        "http://www.swpc.noaa.gov/products/x\n"
        "Oct 12:  None (Below G1)   Oct 13:  G1 (Minor)\n"
        "Sep 9: G2\n"
        "THIS SUPERSEDES ANY/ALL PRIOR WATCHES IN EFFECT\n"
        "Comment:  spaced value  \n"
    )
    m = parse_alerts(one("K04A", message)).messages[0]
    assert m.fields == (MessageField("Comment", "spaced value"),)


def test_extra_keys_are_ignored() -> None:
    raw = json.dumps(
        [
            {
                "product_id": "K04W",
                "issue_datetime": "2026-10-13 20:58:58.750",
                "message": HEADER,
                "new_key": 1,
            }
        ]
    )
    assert parse_alerts(raw).messages[0].serial_number == 5435


def test_empty_array_means_no_messages() -> None:
    alerts = parse_alerts(b"[]")
    assert alerts.messages == ()
    assert alerts.data_time is None


# --- Errors ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "field"),
    [
        (
            HEADER.replace("Space Weather Message Code: WARK04\r\n", ""),
            "message.Space Weather Message Code",
        ),
        (HEADER.replace("WARK04", ""), "message.Space Weather Message Code"),
        (HEADER.replace("WARK04", "WAR K04"), "message.Space Weather Message Code"),
        (HEADER.replace("Serial Number: 5435\r\n", ""), "message.Serial Number"),
        (HEADER.replace("5435", "54x5"), "message.Serial Number"),
        (
            HEADER.replace("Issue Time: 2026 Oct 13 2058 UTC\r\n", ""),
            "message.Issue Time",
        ),
        (
            HEADER.replace("2026 Oct 13 2058 UTC", "2026-10-13 20:58"),
            "message.Issue Time",
        ),
        (
            HEADER.replace("2026 Oct 13 2058 UTC", "2026 Oct 32 2058 UTC"),
            "message.Issue Time",
        ),
        (
            HEADER.replace("2026 Oct 13 2058 UTC", "2026 Oct 13 2460 UTC"),
            "message.Issue Time",
        ),
        ("", "message.Space Weather Message Code"),
    ],
)
def test_broken_header_skips_the_message(message: str, field: str) -> None:
    good = {
        "product_id": "K04W",
        "issue_datetime": "2026-10-13 20:58:58.750",
        "message": HEADER,
    }
    bad = {**good, "message": message}
    alerts = parse_alerts(json.dumps([good, bad]))
    assert len(alerts.messages) == 1
    assert [(s.index, s.field) for s in alerts.skipped] == [(1, field)]
    # Alone, the message makes the product fail.
    with pytest.raises(ParseError) as info:
        parse_alerts(json.dumps([bad]))
    assert info.value.field == field


@pytest.mark.parametrize(
    ("record", "field"),
    [
        (
            {"issue_datetime": "2026-10-13 20:58:58.750", "message": HEADER},
            "product_id",
        ),
        (
            {
                "product_id": "  ",
                "issue_datetime": "2026-10-13 20:58:58.750",
                "message": HEADER,
            },
            "product_id",
        ),
        (
            {
                "product_id": 4,
                "issue_datetime": "2026-10-13 20:58:58.750",
                "message": HEADER,
            },
            "product_id",
        ),
        (
            {"product_id": "K04W", "issue_datetime": "13 Oct 2026", "message": HEADER},
            "issue_datetime",
        ),
        ({"product_id": "K04W", "message": HEADER}, "issue_datetime"),
        (
            {
                "product_id": "K04W",
                "issue_datetime": "2026-10-13 20:58:58.750",
                "message": None,
            },
            "message",
        ),
    ],
)
def test_broken_record_skips_the_message(record: dict[str, object], field: str) -> None:
    good = {
        "product_id": "K04W",
        "issue_datetime": "2026-10-13 20:58:58.750",
        "message": HEADER,
    }
    alerts = parse_alerts(json.dumps([good, record]))
    assert [(s.index, s.field) for s in alerts.skipped] == [(1, field)]


def test_field_missing_from_every_message_is_unexpected() -> None:
    record = {"issue_datetime": "2026-10-13 20:58:58.750", "message": HEADER}
    with pytest.raises(UnexpectedContent, match="'product_id' missing from every"):
        parse_alerts(json.dumps([record, record]))


def test_non_object_record_is_skipped() -> None:
    good = {
        "product_id": "K04W",
        "issue_datetime": "2026-10-13 20:58:58.750",
        "message": HEADER,
    }
    alerts = parse_alerts(json.dumps([good, "oops"]))
    assert [(s.index, s.field) for s in alerts.skipped] == [(1, None)]


@pytest.mark.parametrize(
    "raw",
    [
        b"<!DOCTYPE html><html><body>Moved</body></html>",
        b'{"product_id": "K04W"}',
        b'[["product_id", "issue_datetime", "message"]]',
        b"[1, 2]",
        b"not json at all",
    ],
)
def test_unexpected_content(raw: bytes) -> None:
    with pytest.raises(UnexpectedContent):
        parse_alerts(raw)


@pytest.mark.parametrize("raw", [b"", b"   ", None])
def test_empty_or_truncated_is_not_ready(raw: bytes | None) -> None:
    if raw is None:
        full = FIXTURE.read_bytes()
        raw = full[: len(full) // 2]
    with pytest.raises(SourceNotReady):
        parse_alerts(raw)


# --- Models ------------------------------------------------------------------


def test_models_are_frozen(alerts: Alerts) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        alerts.source_url = "x"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        alerts.messages[0].serial_number = 1  # type: ignore[misc]
    assert isinstance(alerts.messages, tuple)
    assert isinstance(alerts.messages[0].fields, tuple)


def _message(**changes: object) -> AlertMessage:
    values: dict[str, object] = {
        "product_id": "K04W",
        "code": "WARK04",
        "serial_number": 1,
        "issued": utc(2026, 10, 13),
        "issue_time": utc(2026, 10, 13),
    }
    values.update(changes)
    return AlertMessage(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "name",
    [
        "issued",
        "issue_time",
        "valid_from",
        "valid_to",
        "threshold_reached",
        "begin_time",
        "maximum_time",
        "end_time",
        "observed",
    ],
)
def test_message_times_must_be_utc(name: str) -> None:
    with pytest.raises(ValueError, match=name):
        _message(**{name: datetime(2026, 10, 13)})  # noqa: DTZ001
    with pytest.raises(ValueError, match=name):
        _message(**{name: datetime(2026, 10, 13, tzinfo=timezone(timedelta(hours=1)))})


def test_scale_level_is_checked() -> None:
    with pytest.raises(ValueError, match="level"):
        NoaaScale(ScaleCategory.GEOMAGNETIC_STORM, 0, None)
    with pytest.raises(ValueError, match="level"):
        NoaaScale(ScaleCategory.GEOMAGNETIC_STORM, 6, None)


def test_data_time_is_the_latest_issue() -> None:
    older = _message(issued=utc(2026, 10, 1))
    newer = _message(issued=utc(2026, 10, 2))
    alerts = Alerts(messages=(older, newer), source_url=ALERTS_URL)
    assert alerts.data_time == utc(2026, 10, 2)
