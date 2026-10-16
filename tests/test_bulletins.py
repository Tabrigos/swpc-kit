import dataclasses
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.models.bulletins import (
    DailyAp,
    GeomagneticForecast,
    KpPeriod,
    OutlookDay,
    ThreeDayForecast,
    TwentySevenDayOutlook,
)
from swpc_kit.parse.bulletins import (
    GEOMAGNETIC_FORECAST_URL,
    THREE_DAY_FORECAST_URL,
    TWENTY_SEVEN_DAY_OUTLOOK_URL,
    parse_27_day_outlook,
    parse_geomagnetic_forecast,
    parse_three_day_forecast,
)

FIXTURES = Path(__file__).parent / "fixtures"

THREE_DAY = "3-day-forecast/2026-10-15.txt"
THREE_DAY_2022 = "3-day-forecast/2022-09-22-sample.txt"
GEOMAG = "geomag-forecast/2026-10-15.txt"
OUTLOOK = "27-day-outlook/2026-10-15.txt"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def text(name: str) -> str:
    return fixture(name).decode()


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def line_at(content: str, index: int) -> int:
    """1-based number of the line holding character ``index``."""
    return content.count("\n", 0, index) + 1


def line_of(content: str, needle: str) -> int:
    """1-based number of the first line containing ``needle``."""
    for number, line in enumerate(content.splitlines(), start=1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not found")


def replace_once(content: str, old: str, new: str) -> str:
    assert content.count(old) == 1, old
    return content.replace(old, new)


# --- 3-day forecast ----------------------------------------------------------


def test_three_day_forecast() -> None:
    f = parse_three_day_forecast(fixture(THREE_DAY))
    assert f.issued == utc(2026, 10, 15, 12, 30)
    assert f.data_time == f.issued
    assert f.source_url == THREE_DAY_FORECAST_URL
    assert f.days == (date(2026, 10, 15), date(2026, 10, 16), date(2026, 10, 17))

    assert f.greatest_observed_kp == 3.0
    assert f.greatest_observed_scale is None
    assert f.greatest_expected_kp == 2.67
    assert f.greatest_expected_scale is None
    assert f.geomagnetic_summary == (
        "The greatest observed 3 hr Kp over the past 24 hours was 3 (below NOAA "
        "Scale levels). The greatest expected 3 hr Kp for Oct 15-Oct 17 2026 is "
        "2.67 (below NOAA Scale levels)."
    )

    assert len(f.kp) == 24
    assert f.kp[0] == KpPeriod(start=utc(2026, 10, 15, 0), kp=2.0, noaa_scale=None)
    assert f.kp[1] == KpPeriod(start=utc(2026, 10, 15, 3), kp=0.67, noaa_scale=None)
    assert f.kp[8] == KpPeriod(start=utc(2026, 10, 16, 0), kp=2.33, noaa_scale=None)
    assert f.kp[-1] == KpPeriod(start=utc(2026, 10, 17, 21), kp=1.67, noaa_scale=None)
    assert f.kp[-1].end == utc(2026, 10, 18, 0)
    assert [p.start for p in f.kp] == [
        utc(2026, 10, 15) + timedelta(hours=3 * i) for i in range(24)
    ]
    assert f.geomagnetic_rationale == (
        "No G1 (Minor) or greater geomagnetic storms are expected. No "
        "significant transient or recurrent solar wind features are forecast."
    )

    assert f.solar_radiation_summary == (
        "Solar radiation, as observed by NOAA GOES-18 over the past 24 hours, "
        "was below S-scale storm level thresholds."
    )
    assert f.s1_or_greater == (5, 1, 1)
    assert f.solar_radiation_rationale == (
        "No S1 (Minor) or greater solar radiation storms are expected. No "
        "significant active region activity favorable for radiation storm "
        "production is forecast."
    )

    assert f.radio_blackout_summary == (
        "No radio blackouts were observed over the past 24 hours."
    )
    assert f.r1_r2 == (20, 20, 20)
    assert f.r3_or_greater == (5, 5, 5)
    assert f.radio_blackout_rationale == (
        "No R1 (Minor) or greater radio blackouts are expected. No significant "
        "active region flare activity is forecast."
    )


def test_three_day_forecast_official_2022_sample_with_scales() -> None:
    f = parse_three_day_forecast(fixture(THREE_DAY_2022))
    assert f.issued == utc(2022, 4, 28, 12, 30)
    assert f.days == (date(2022, 4, 28), date(2022, 4, 29), date(2022, 4, 30))
    assert f.greatest_observed_kp == 5.33
    assert f.greatest_observed_scale == "G1"
    assert f.greatest_expected_kp == 5.33
    assert f.greatest_expected_scale == "G1"
    scaled = [p for p in f.kp if p.noaa_scale is not None]
    assert scaled == [KpPeriod(start=utc(2022, 4, 29, 6), kp=5.33, noaa_scale="G1")]
    assert f.kp[2] == KpPeriod(start=utc(2022, 4, 28, 6), kp=3.67, noaa_scale=None)
    assert f.kp[-1] == KpPeriod(start=utc(2022, 4, 30, 21), kp=2.33, noaa_scale=None)
    assert f.s1_or_greater == (10, 10, 5)
    assert f.r1_r2 == (25, 20, 15)
    assert f.r3_or_greater == (5, 5, 1)
    assert f.geomagnetic_rationale == (
        "G1 (Minor) geomagnetic storms are likely on 29 Apr due to CH HSS effects."
    )


def test_three_day_forecast_accepts_str_crlf_and_bom() -> None:
    expected = parse_three_day_forecast(fixture(THREE_DAY))
    content = text(THREE_DAY)
    assert parse_three_day_forecast(content) == expected
    assert parse_three_day_forecast(content.replace("\n", "\r\n")) == expected
    assert parse_three_day_forecast(b"\xef\xbb\xbf" + fixture(THREE_DAY)) == expected


def test_three_day_forecast_without_final_newline_is_complete() -> None:
    content = text(THREE_DAY)
    expected = parse_three_day_forecast(content)
    assert parse_three_day_forecast(content.rstrip()) == expected


def test_three_day_forecast_source_url_can_be_overridden() -> None:
    f = parse_three_day_forecast(fixture(THREE_DAY), source_url="https://example.org/f")
    assert f.source_url == "https://example.org/f"


THREE_DAY_ROLLOVER = """\
:Product: 3-Day Forecast
:Issued: 2026 Dec 31 1230 UTC
# Prepared by the U.S. Dept. of Commerce, NOAA, Space Weather Prediction Center
#
A. NOAA Geomagnetic Activity Observation and Forecast

The greatest observed 3 hr Kp over the past 24 hours was 2 (below NOAA
Scale levels).
The greatest expected 3 hr Kp for Dec 31-Jan 02 2027 is 5.00 (NOAA Scale
G1).

NOAA Kp index breakdown Dec 31-Jan 02 2027

             Dec 31       Jan 01       Jan 02
00-03UT       2.00         2.33         1.67
03-06UT       0.67         2.67         1.67
06-09UT       1.33         5.00 (G1)    1.33
09-12UT       2.33         1.67         1.33
12-15UT       1.67         1.67         1.33
15-18UT       1.00         2.00         1.33
18-21UT       1.33         2.00         1.33
21-00UT       2.33         2.67         1.67

Rationale: G1 (Minor) storms are likely on 01 Jan.

B. NOAA Solar Radiation Activity Observation and Forecast

Solar radiation was below S-scale storm level thresholds.

Solar Radiation Storm Forecast for Dec 31-Jan 02 2027

              Dec 31  Jan 01  Jan 02
S1 or greater    1%      1%      1%

Rationale: No S1 (Minor) or greater solar radiation storms are expected.

C. NOAA Radio Blackout Activity and Forecast

No radio blackouts were observed over the past 24 hours.

Radio Blackout Forecast for Dec 31-Jan 02 2027

              Dec 31        Jan 01        Jan 02
R1-R2           10%           10%           10%
R3 or greater    1%            1%            1%

Rationale: No R1 (Minor) or greater radio blackouts are expected.

Second paragraph.
"""


def test_three_day_forecast_year_rollover() -> None:
    f = parse_three_day_forecast(THREE_DAY_ROLLOVER)
    assert f.days == (date(2026, 12, 31), date(2027, 1, 1), date(2027, 1, 2))
    assert f.kp[8] == KpPeriod(start=utc(2027, 1, 1, 0), kp=2.33, noaa_scale=None)
    assert f.kp[10] == KpPeriod(start=utc(2027, 1, 1, 6), kp=5.0, noaa_scale="G1")
    assert f.kp[-1].end == utc(2027, 1, 3, 0)
    assert f.greatest_observed_kp == 2.0
    assert f.greatest_expected_scale == "G1"
    assert f.radio_blackout_rationale == (
        "No R1 (Minor) or greater radio blackouts are expected.\n\nSecond paragraph."
    )


def test_three_day_forecast_every_truncation_is_not_ready() -> None:
    content = text(THREE_DAY)
    # The last rationale is free text running to the end: once it has started,
    # a cut cannot be told from a complete file.
    end = content.index("Rationale: No R1") + len("Rationale: ")
    for cut in range(end + 1):
        with pytest.raises(SourceNotReady):
            parse_three_day_forecast(content[:cut])


def test_three_day_forecast_truncation_at_a_line_boundary_is_not_ready() -> None:
    content = text(THREE_DAY)
    cut = content.index("21-00UT")
    with pytest.raises(SourceNotReady):
        parse_three_day_forecast(content[:cut])


@pytest.mark.parametrize(
    "raw",
    [b"", b"   \n\n", "﻿".encode()],
)
def test_empty_is_not_ready(raw: bytes) -> None:
    for parse in (
        parse_three_day_forecast,
        parse_geomagnetic_forecast,
        parse_27_day_outlook,
    ):
        with pytest.raises(SourceNotReady):
            parse(raw)


@pytest.mark.parametrize(
    "raw",
    [
        b"<!DOCTYPE html>\n<html><body>Moved</body></html>\n",
        b'[{"time_tag":"2026-10-08T00:00:00","Kp":1.00}]',
        b"Product: 3-Day Forecast\n:Issued: 2026 Oct 15 1230 UTC\n",
        b"\xff\xfe\x00",
    ],
)
def test_not_a_text_product_is_unexpected(raw: bytes) -> None:
    for parse in (
        parse_three_day_forecast,
        parse_geomagnetic_forecast,
        parse_27_day_outlook,
    ):
        with pytest.raises(UnexpectedContent):
            parse(raw)


def test_a_different_product_is_unexpected() -> None:
    with pytest.raises(UnexpectedContent, match="Geomagnetic Forecast"):
        parse_three_day_forecast(fixture(GEOMAG))
    with pytest.raises(UnexpectedContent):
        parse_geomagnetic_forecast(fixture(THREE_DAY))
    with pytest.raises(UnexpectedContent):
        parse_27_day_outlook(fixture(THREE_DAY))
    with pytest.raises(UnexpectedContent):
        parse_three_day_forecast(fixture(OUTLOOK))


@pytest.mark.parametrize(
    ("old", "new", "field"),
    [
        (":Issued: 2026 Oct 15 1230 UTC", ":Issued: 2026 Okt 15 1230 UTC", "Issued"),
        (":Issued: 2026 Oct 15 1230 UTC", ":Issued: 2026 Oct 32 1230 UTC", "Issued"),
        (":Issued: 2026 Oct 15 1230 UTC", ":Issued: 2026 Oct 15 2460 UTC", "Issued"),
        (":Issued: 2026 Oct 15 1230 UTC", ":Issued: 2026 Oct 15 1230 EST", "Issued"),
        (":Issued: 2026 Oct 15 1230 UTC", ":Issue: 2026 Oct 15 1230 UTC", "Issued"),
    ],
)
def test_bad_issue_time(old: str, new: str, field: str) -> None:
    content = replace_once(text(THREE_DAY), old, new)
    with pytest.raises(ParseError) as info:
        parse_three_day_forecast(content)
    assert info.value.line == 2
    assert info.value.field == field


@pytest.mark.parametrize(
    ("old", "new", "needle", "field"),
    [
        # Kp out of range, or not a whole number of thirds.
        ("09-12UT       2.33", "09-12UT       9.33", "09-12UT", "Kp"),
        ("09-12UT       2.33", "09-12UT       2.50", "09-12UT", "Kp"),
        # Kp written without the two decimals of the tables.
        ("09-12UT       2.33", "09-12UT       2   ", "09-12UT", "Kp"),
        # An unknown annotation.
        (
            "21-00UT       2.33         2.67         1.67",
            "21-00UT       2.33         2.67 (Z9)    1.67",
            "21-00UT",
            "Kp",
        ),
        # Rows out of order.
        ("03-06UT       0.67", "06-09UT       0.67", "06-09UT       0.67", "Kp"),
        # A missing cell in a complete file.
        (
            "12-15UT       1.67         1.67         1.33",
            "12-15UT       1.67         1.67",
            "12-15UT",
            "Kp",
        ),
        # A scale that is not a geomagnetic storm level.
        (
            "12-15UT       1.67         1.67",
            "12-15UT       1.67 (S1)    1.67",
            "12-15UT",
            "Kp",
        ),
        # Days that do not follow each other.
        (
            "             Oct 15       Oct 16       Oct 17",
            "             Oct 15       Oct 17       Oct 18",
            "Oct 15       Oct 17",
            "days",
        ),
        # Tables of a section disagreeing on the days.
        (
            "              Oct 15  Oct 16  Oct 17",
            "              Oct 16  Oct 17  Oct 18",
            "Oct 16  Oct 17  Oct 18",
            "days",
        ),
        # A probability above 100 %.
        ("R1-R2           20%", "R1-R2          120%", "R1-R2", "R1-R2"),
        (
            "S1 or greater    5%",
            "S1 or greater    5 ",
            "S1 or greater",
            "S1 or greater",
        ),
        # The greatest observed Kp, out of range.
        (
            "past 24 hours was 3 (below",
            "past 24 hours was 10 (below",
            "was 10",
            "greatest observed Kp",
        ),
    ],
)
def test_three_day_forecast_inconsistent_values(
    old: str, new: str, needle: str, field: str
) -> None:
    content = replace_once(text(THREE_DAY), old, new)
    with pytest.raises(ParseError) as info:
        parse_three_day_forecast(content)
    assert info.value.line == line_of(content, needle)
    assert info.value.field == field


@pytest.mark.parametrize(
    ("old", "field"),
    [
        ("The greatest observed 3 hr Kp", "greatest observed Kp"),
        ("The greatest expected 3 hr Kp", "greatest expected Kp"),
    ],
)
def test_three_day_forecast_missing_kp_sentence(old: str, field: str) -> None:
    content = replace_once(text(THREE_DAY), old, "The largest seen Kp")
    with pytest.raises(ParseError) as info:
        parse_three_day_forecast(content)
    assert info.value.line == line_of(content, "over the past 24 hours was")
    assert info.value.field == field


def test_three_day_forecast_missing_section_is_a_parse_error() -> None:
    content = text(THREE_DAY)
    start = content.index("B. NOAA Solar")
    end = content.index("C. NOAA Radio")
    content = content[:start] + content[end:]
    with pytest.raises(ParseError) as info:
        parse_three_day_forecast(content)
    assert info.value.line == line_of(content, "C. NOAA Radio")


def test_three_day_forecast_missing_rationale_is_a_parse_error() -> None:
    content = replace_once(
        text(THREE_DAY),
        "Rationale: No S1 (Minor) or greater solar radiation storms are expected.\n"
        "No significant active region activity favorable for radiation storm\n"
        "production is forecast.\n",
        "",
    )
    with pytest.raises(ParseError) as info:
        parse_three_day_forecast(content)
    assert info.value.line == line_of(content, "C. NOAA Radio")


def test_three_day_forecast_empty_rationale_before_a_section() -> None:
    content = replace_once(
        text(THREE_DAY),
        "Rationale: No S1 (Minor) or greater solar radiation storms are expected.\n"
        "No significant active region activity favorable for radiation storm\n"
        "production is forecast.\n",
        "Rationale:\n",
    )
    with pytest.raises(ParseError) as info:
        parse_three_day_forecast(content)
    assert info.value.line == line_at(content, content.index("Rationale:\n"))
    assert info.value.field == "Rationale"


def test_three_day_forecast_empty_last_rationale_is_not_ready() -> None:
    content = text(THREE_DAY)
    content = content[: content.index("Rationale: No R1")] + "Rationale:\n\n"
    with pytest.raises(SourceNotReady):
        parse_three_day_forecast(content)


# --- Geomagnetic forecast ---------------------------------------------------


def test_geomagnetic_forecast() -> None:
    g = parse_geomagnetic_forecast(fixture(GEOMAG))
    assert g.issued == utc(2026, 10, 14, 22, 5)
    assert g.data_time == g.issued
    assert g.source_url == GEOMAGNETIC_FORECAST_URL
    assert g.observed_ap == DailyAp(day=date(2026, 10, 13), ap=13)
    assert g.estimated_ap == DailyAp(day=date(2026, 10, 14), ap=11)
    assert g.days == (date(2026, 10, 15), date(2026, 10, 16), date(2026, 10, 17))
    assert g.predicted_ap == (
        DailyAp(day=date(2026, 10, 15), ap=10),
        DailyAp(day=date(2026, 10, 16), ap=8),
        DailyAp(day=date(2026, 10, 17), ap=5),
    )
    assert g.active == (25, 20, 15)
    assert g.minor_storm == (5, 1, 1)
    assert g.moderate_storm == (1, 1, 1)
    assert g.strong_extreme_storm == (1, 1, 1)
    assert len(g.kp) == 24
    assert g.kp[0] == KpPeriod(start=utc(2026, 10, 15, 0), kp=2.67, noaa_scale=None)
    assert g.kp[1] == KpPeriod(start=utc(2026, 10, 15, 3), kp=3.33, noaa_scale=None)
    assert g.kp[-1] == KpPeriod(start=utc(2026, 10, 17, 21), kp=1.67, noaa_scale=None)


def test_geomagnetic_forecast_accepts_str_and_crlf() -> None:
    expected = parse_geomagnetic_forecast(fixture(GEOMAG))
    content = text(GEOMAG)
    assert parse_geomagnetic_forecast(content) == expected
    assert parse_geomagnetic_forecast(content.replace("\n", "\r\n")) == expected
    assert parse_geomagnetic_forecast(content.rstrip()) == expected


GEOMAG_ROLLOVER = """\
:Product: Geomagnetic Forecast
:Issued: 2026 Dec 31 2205 UTC
# Prepared by the U.S. Dept. of Commerce, NOAA, Space Weather Prediction Center
#
NOAA Ap Index Forecast
Observed Ap 30 Dec 013
Estimated Ap 31 Dec 011
Predicted Ap 01 Jan-03 Jan 010-008-005

NOAA Geomagnetic Activity Probabilities 01 Jan-03 Jan
Active                25/20/15
Minor storm           05/01/01
Moderate storm        01/01/01
Strong-Extreme storm  01/01/01

NOAA Kp index forecast 01 Jan - 03 Jan
             Jan 01    Jan 02    Jan 03
00-03UT        2.67      2.33      1.67
03-06UT        3.33      2.67      1.67
06-09UT        3.00      2.00      1.33
09-12UT        2.33      1.67      1.33
12-15UT        1.67      1.67      1.33
15-18UT        1.00      2.00      1.33
18-21UT        1.33      2.00      1.33
21-00UT        2.33      2.67      1.67
"""


def test_geomagnetic_forecast_year_rollover() -> None:
    g = parse_geomagnetic_forecast(GEOMAG_ROLLOVER)
    assert g.observed_ap.day == date(2026, 12, 30)
    assert g.estimated_ap.day == date(2026, 12, 31)
    assert g.days == (date(2027, 1, 1), date(2027, 1, 2), date(2027, 1, 3))
    assert g.kp[0].start == utc(2027, 1, 1)


def test_geomagnetic_forecast_issued_in_january_looks_back_to_december() -> None:
    content = (
        GEOMAG_ROLLOVER.replace("2026 Dec 31 2205", "2027 Jan 01 2205")
        .replace("Observed Ap 30 Dec", "Observed Ap 31 Dec")
        .replace("Estimated Ap 31 Dec", "Estimated Ap 01 Jan")
        .replace("01 Jan-03 Jan", "02 Jan-04 Jan")
        .replace("01 Jan - 03 Jan", "02 Jan - 04 Jan")
        .replace("Jan 01    Jan 02    Jan 03", "Jan 02    Jan 03    Jan 04")
    )
    g = parse_geomagnetic_forecast(content)
    assert g.observed_ap.day == date(2026, 12, 31)
    assert g.estimated_ap.day == date(2027, 1, 1)
    assert g.days == (date(2027, 1, 2), date(2027, 1, 3), date(2027, 1, 4))


def test_geomagnetic_forecast_every_truncation_is_not_ready() -> None:
    content = text(GEOMAG)
    for cut in range(len(content.rstrip())):
        with pytest.raises(SourceNotReady):
            parse_geomagnetic_forecast(content[:cut])


@pytest.mark.parametrize(
    ("old", "new", "needle", "field"),
    [
        ("010-008-005", "010-008", "Predicted Ap", "Ap"),
        ("Observed Ap 13 Oct 013", "Observed Ap 13 Okt 013", "Observed Ap", "Ap"),
        ("Observed Ap 13 Oct 013", "Observed Ap 13 Oct", "Observed Ap", "Ap"),
        (
            "Active                25/20/15",
            "Active                25/20",
            "Active",
            "Active",
        ),
        (
            "Minor storm           05/01/01",
            "Minor storm           05/01/101",
            "Minor",
            "Minor storm",
        ),
        (
            "Moderate storm        01/01/01",
            "Severe storm          01/01/01",
            "Severe",
            "Moderate storm",
        ),
        (
            "Probabilities 15 Oct-17 Oct",
            "Probabilities 16 Oct-18 Oct",
            "Probabilities",
            "days",
        ),
        (
            "Oct 15    Oct 16    Oct 17",
            "Oct 16    Oct 17    Oct 18",
            "Oct 16    Oct 17",
            "days",
        ),
        ("03-06UT        3.33", "03-06UT        3.30", "03-06UT", "Kp"),
    ],
)
def test_geomagnetic_forecast_inconsistent_values(
    old: str, new: str, needle: str, field: str
) -> None:
    content = replace_once(text(GEOMAG), old, new)
    with pytest.raises(ParseError) as info:
        parse_geomagnetic_forecast(content)
    assert info.value.line == line_of(content, needle)
    assert info.value.field == field


def test_geomagnetic_forecast_rejects_trailing_content() -> None:
    content = text(GEOMAG) + "\nSomething new\n"
    with pytest.raises(ParseError) as info:
        parse_geomagnetic_forecast(content)
    assert info.value.line == line_of(content, "Something new")


# --- 27-day outlook ----------------------------------------------------------


def test_27_day_outlook() -> None:
    o = parse_27_day_outlook(fixture(OUTLOOK))
    assert o.issued == utc(2026, 10, 12, 3, 45)
    assert o.data_time == o.issued
    assert o.source_url == TWENTY_SEVEN_DAY_OUTLOOK_URL
    assert len(o.days) == 27
    assert o.days[0] == OutlookDay(
        day=date(2026, 10, 12), radio_flux=120.0, ap=16, largest_kp=4
    )
    assert o.days[1] == OutlookDay(
        day=date(2026, 10, 13), radio_flux=115.0, ap=28, largest_kp=5
    )
    assert o.days[-1] == OutlookDay(
        day=date(2026, 11, 7), radio_flux=110.0, ap=10, largest_kp=3
    )
    assert [d.day for d in o.days] == [
        date(2026, 10, 12) + timedelta(days=i) for i in range(27)
    ]


def test_27_day_outlook_accepts_str_and_crlf() -> None:
    expected = parse_27_day_outlook(fixture(OUTLOOK))
    content = text(OUTLOOK)
    assert parse_27_day_outlook(content) == expected
    assert parse_27_day_outlook(content.replace("\n", "\r\n")) == expected
    assert parse_27_day_outlook(content.rstrip()) == expected


def test_27_day_outlook_across_the_new_year() -> None:
    rows = "".join(
        f"{d:%Y %b %d}     100          10          3\n"
        for d in (date(2026, 12, 20) + timedelta(days=i) for i in range(27))
    )
    content = (
        ":Product: 27-day Space Weather Outlook Table 27DO.txt\n"
        ":Issued: 2026 Dec 20 0345 UTC\n"
        "#   UTC      Radio Flux   Planetary   Largest\n" + rows
    )
    o = parse_27_day_outlook(content)
    assert o.days[11].day == date(2026, 12, 31)
    assert o.days[12].day == date(2027, 1, 1)


def test_27_day_outlook_every_truncation_is_not_ready() -> None:
    content = text(OUTLOOK)
    for cut in range(len(content.rstrip())):
        with pytest.raises(SourceNotReady):
            parse_27_day_outlook(content[:cut])


@pytest.mark.parametrize(
    ("old", "new", "needle", "field"),
    [
        ("2026 Oct 20     100", "2026 Oct 21     100", "2026 Oct 21     100", "date"),
        ("2026 Oct 20     100", "2026 Okt 20     100", "Okt", "date"),
        (
            "2026 Oct 31     105          30          5",
            "2026 Oct 31     105          30         10",
            "Oct 31",
            "largest Kp",
        ),
        (
            "2026 Oct 31     105          30",
            "2026 Oct 31     105         -30",
            "Oct 31",
            "Ap",
        ),
        (
            "2026 Oct 31     105          30",
            "2026 Oct 31     1x5          30",
            "Oct 31",
            "radio flux",
        ),
        ("2026 Oct 31     105          30", "2026 Oct 31     105", "Oct 31", None),
    ],
)
def test_27_day_outlook_inconsistent_values(
    old: str, new: str, needle: str, field: str | None
) -> None:
    content = replace_once(text(OUTLOOK), old, new)
    with pytest.raises(ParseError) as info:
        parse_27_day_outlook(content)
    assert info.value.line == line_of(content, needle)
    assert info.value.field == field


def test_27_day_outlook_rejects_a_28th_row() -> None:
    content = text(OUTLOOK) + "2026 Nov 08     110          10          3\n"
    with pytest.raises(ParseError) as info:
        parse_27_day_outlook(content)
    assert info.value.line == line_of(content, "2026 Nov 08")


# --- Models -----------------------------------------------------------------


def test_models_are_frozen() -> None:
    f = parse_three_day_forecast(fixture(THREE_DAY))
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.issued = utc(2020, 1, 1)  # type: ignore[misc]


def test_naive_times_cannot_be_built() -> None:
    with pytest.raises(ValueError, match="UTC"):
        KpPeriod(start=datetime(2026, 10, 15), kp=1.0, noaa_scale=None)  # noqa: DTZ001
    o = parse_27_day_outlook(fixture(OUTLOOK))
    with pytest.raises(ValueError, match="UTC"):
        TwentySevenDayOutlook(
            issued=datetime(2026, 10, 12),  # noqa: DTZ001
            days=o.days,
            source_url="x",
        )


def test_misaligned_values_cannot_be_built() -> None:
    f = parse_three_day_forecast(fixture(THREE_DAY))
    with pytest.raises(ValueError, match="s1_or_greater"):
        dataclasses.replace(f, s1_or_greater=(1, 2))
    with pytest.raises(ValueError, match="kp"):
        dataclasses.replace(f, kp=f.kp[:-1])
    g = parse_geomagnetic_forecast(fixture(GEOMAG))
    with pytest.raises(ValueError, match="predicted_ap"):
        dataclasses.replace(g, predicted_ap=g.predicted_ap[:2])
    assert isinstance(g, GeomagneticForecast)
    assert isinstance(f, ThreeDayForecast)
