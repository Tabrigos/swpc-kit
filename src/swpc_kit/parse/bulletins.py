"""Parsers for the SWPC text bulletins.

The 3-day forecast, the geomagnetic forecast and the 27-day outlook share the
``:Product:`` / ``:Issued:`` header read by :mod:`swpc_kit.parse._text`, and
the first two share the Kp forecast table::

                 Oct 15       Oct 16       Oct 17
    00-03UT       2.00         2.33         1.67
    ...
    21-00UT       2.33         2.67         5.33 (G1)

Errors name the 1-based line. Content that ends before an expected element,
or inside a line, is :class:`~swpc_kit.errors.SourceNotReady`. The last
rationale of the 3-day forecast is free text running to the end of the file,
so a cut inside it cannot be told from a complete file.
"""

import re
from datetime import UTC, date, datetime, time, timedelta
from itertools import pairwise

from swpc_kit.models.bulletins import (
    KP_PERIODS_PER_DAY,
    DailyAp,
    GeomagneticForecast,
    KpPeriod,
    OutlookDay,
    ThreeDayForecast,
    TwentySevenDayOutlook,
)
from swpc_kit.parse._text import (
    MONTHS,
    Line,
    TextReader,
    Unwrapped,
    open_text_product,
    unwrap,
)

THREE_DAY_FORECAST_URL = "https://services.swpc.noaa.gov/text/3-day-forecast.txt"
GEOMAGNETIC_FORECAST_URL = (
    "https://services.swpc.noaa.gov/text/3-day-geomag-forecast.txt"
)
TWENTY_SEVEN_DAY_OUTLOOK_URL = "https://services.swpc.noaa.gov/text/27-day-outlook.txt"

_MONTH = r"[A-Za-z]{3}"
_DAY_COLUMNS = re.compile(rf"{_MONTH}\s+\d{{1,2}}(?:\s+{_MONTH}\s+\d{{1,2}})*")
_DAY_COLUMN = re.compile(rf"({_MONTH})\s+(\d{{1,2}})")
_DAY_RANGE = rf"(\d{{1,2}})\s+({_MONTH})\s*-\s*(\d{{1,2}})\s+({_MONTH})"

_KP_LABELS = tuple(
    f"{3 * i:02d}-{(3 * i + 3) % 24:02d}UT" for i in range(KP_PERIODS_PER_DAY)
)
_KP_ROW = re.compile(r"(\d{2}-\d{2}UT)\s+(.*)")
_KP_CELL = re.compile(r"(\S+?)(?:\s*\(([^()]*)\))?(?=\s|$)")
_KP_TABLE_VALUE = re.compile(r"\d\.\d{2}")
_KP_SCALE = re.compile(r"G[1-5]")
_SPACE = re.compile(r"\s+")
_PERCENT = re.compile(r"(\d{1,3})%")

# 3-day forecast.
_SECTION = re.compile(r"[A-Z]\.\s+\S.*")
_KP_BREAKDOWN = re.compile(r"NOAA Kp index breakdown\b.*")
_S_TITLE = re.compile(r"Solar Radiation Storm Forecast for\b.*")
_R_TITLE = re.compile(r"Radio Blackout Forecast for\b.*")
_RATIONALE = re.compile(r"Rationale:\s*(.*)")
_OBSERVED = re.compile(
    r"The greatest observed 3 hr Kp over the past 24 hours was (\S+) \(([^)]*)\)"
)
_EXPECTED = re.compile(r"The greatest expected 3 hr Kp for .+? is (\S+) \(([^)]*)\)")
_SENTENCE_SCALE = re.compile(r"\b(G[1-5])\b")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")

# Geomagnetic forecast.
_AP_TITLE = re.compile(r"NOAA Ap Index Forecast")
_AP_OBSERVED = re.compile(rf"Observed Ap\s+(\d{{1,2}})\s+({_MONTH})\s+(\d+)")
_AP_ESTIMATED = re.compile(rf"Estimated Ap\s+(\d{{1,2}})\s+({_MONTH})\s+(\d+)")
_AP_PREDICTED = re.compile(rf"Predicted Ap\s+{_DAY_RANGE}\s+(\d+(?:-\d+)*)")
_PROBABILITIES_TITLE = re.compile(
    rf"NOAA Geomagnetic Activity Probabilities\s+{_DAY_RANGE}"
)
_PROBABILITY_ROWS = ("Active", "Minor storm", "Moderate storm", "Strong-Extreme storm")
_KP_FORECAST_TITLE = re.compile(rf"NOAA Kp index forecast\s+{_DAY_RANGE}")

# 27-day outlook.
_OUTLOOK_PRODUCT = "27-day Space Weather Outlook Table 27DO.txt"
_OUTLOOK_DAYS = 27
_FLUX = re.compile(r"\d+(?:\.\d+)?")
_INTEGER = re.compile(r"\d+")


# --- Shared pieces -----------------------------------------------------------


# A storm scale needs Kp 5- (4.67) at least: G1 is Kp 5. Which third starts
# each level above G1 is not checked (docs/FONTI.md, "Plausibility limits").
_G1_KP = 4.67


def _check_kp(reader: TextReader, kp: float, line: int, field: str) -> None:
    if not 0 <= kp <= 9:
        raise reader.error(f"Kp {kp} out of range [0, 9]", line, field)
    if abs(kp * 3 - round(kp * 3)) > 0.02:
        raise reader.error(f"Kp {kp} is not a whole number of thirds", line, field)


def _check_consecutive(
    reader: TextReader, days: list[date], line: int, field: str
) -> None:
    for before, after in pairwise(days):
        if after - before != timedelta(days=1):
            raise reader.error(
                f"days do not follow each other: {before} then {after}", line, field
            )


def _day_columns(
    reader: TextReader, near: date, what: str
) -> tuple[Line, tuple[date, ...]]:
    """Read a line of day columns such as ``Oct 15   Oct 16   Oct 17``."""
    line, _ = reader.expect(_DAY_COLUMNS, f"the day columns of {what}", "days")
    days = [
        reader.date(m[1], m[2], near, line.number, "days")
        for m in _DAY_COLUMN.finditer(line.text)
    ]
    _check_consecutive(reader, days, line.number, "days")
    return line, tuple(days)


def _day_range(
    reader: TextReader, match: re.Match[str], start: int, near: date, line: int
) -> list[date]:
    """Expand ``15 Oct-17 Oct`` from groups ``start`` to ``start + 3``."""
    first = reader.date(match[start + 1], match[start], near, line, "days")
    last = reader.date(match[start + 3], match[start + 2], near, line, "days")
    if not timedelta(0) <= last - first <= timedelta(days=31):
        raise reader.error(f"not a range of days: {first} to {last}", line, "days")
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _check_same_days(
    reader: TextReader, days: tuple[date, ...], expected: tuple[date, ...], line: int
) -> None:
    if days != expected:
        raise reader.error(
            f"days {[str(d) for d in days]} differ from the forecast days "
            f"{[str(d) for d in expected]}",
            line,
            "days",
        )


def _kp_cells(text: str) -> list[tuple[str, str | None]] | None:
    """Split the cells of a Kp row: a value, maybe followed by ``(G1)``."""
    cells: list[tuple[str, str | None]] = []
    pos = 0
    while pos < len(text):
        if cells:
            space = _SPACE.match(text, pos)
            if space is None:
                return None
            pos = space.end()
        cell = _KP_CELL.match(text, pos)
        if cell is None:
            return None
        cells.append((cell[1], cell[2]))
        pos = cell.end()
    return cells


def _kp_table(
    reader: TextReader,
    issued: datetime,
    what: str,
    expected: tuple[date, ...] | None = None,
) -> tuple[tuple[date, ...], tuple[KpPeriod, ...]]:
    """Read a Kp table: the day columns, then the eight 3-hour rows.

    When ``expected`` is given, the day columns must be those days.
    """
    header, days = _day_columns(reader, issued.date(), what)
    if expected is not None:
        _check_same_days(reader, days, expected, header.number)
    columns: list[list[KpPeriod]] = [[] for _ in days]
    for row, label in enumerate(_KP_LABELS):
        line, match = reader.expect(_KP_ROW, f"the {label} row of {what}", "Kp")
        if match[1] != label:
            raise reader.error(
                f"expected the {label} row, got {match[1]!r}", line.number, "Kp"
            )
        cells = _kp_cells(match[2])
        if cells is None:
            raise reader.error(
                f"expected Kp values, got {match[2]!r}", line.number, "Kp"
            )
        if len(cells) != len(days):
            raise reader.error(
                f"{len(cells)} values for {len(days)} days", line.number, "Kp"
            )
        for column, (value, scale) in enumerate(cells):
            if not _KP_TABLE_VALUE.fullmatch(value):
                raise reader.error(
                    f"expected a Kp like '2.33', got {value!r}", line.number, "Kp"
                )
            kp = float(value)
            _check_kp(reader, kp, line.number, "Kp")
            if scale is not None and not _KP_SCALE.fullmatch(scale.strip()):
                raise reader.error(
                    f"expected a scale like '(G1)', got {scale!r}", line.number, "Kp"
                )
            if scale is not None and kp < _G1_KP:
                raise reader.error(
                    f"Kp {value} is below storm level, yet marked {scale.strip()}",
                    line.number,
                    "Kp",
                )
            start = datetime.combine(days[column], time(3 * row), tzinfo=UTC)
            columns[column].append(
                KpPeriod(
                    start=start,
                    kp=kp,
                    noaa_scale=scale.strip() if scale is not None else None,
                )
            )
    return days, tuple(period for column in columns for period in column)


def _percent_row(
    reader: TextReader, label: str, days: tuple[date, ...], what: str
) -> tuple[int, ...]:
    """Read a row like ``S1 or greater    5%      1%      1%``."""
    pattern = re.compile(r"\s+".join(map(re.escape, label.split())) + r"\s+(.*)")
    line, match = reader.expect(pattern, f"the {label!r} row of {what}", label)
    values = []
    for token in match[1].split():
        percent = _PERCENT.fullmatch(token)
        if percent is None:
            raise reader.error(
                f"expected a percentage, got {token!r}", line.number, label
            )
        values.append(_percent(reader, percent[1], line.number, label))
    if len(values) != len(days):
        raise reader.error(
            f"{len(values)} values for {len(days)} days", line.number, label
        )
    return tuple(values)


def _percent(reader: TextReader, text: str, line: int, field: str) -> int:
    value = int(text)
    if value > 100:
        raise reader.error(f"probability {value} above 100", line, field)
    return value


# --- 3-day forecast ----------------------------------------------------------


def _section(reader: TextReader, letter: str) -> int:
    """Read the title of a section; return its line number."""
    line, match = reader.expect(_SECTION, f"section {letter}")
    if not match[0].startswith(f"{letter}."):
        raise reader.error(f"expected section {letter}, got {line.text!r}", line.number)
    return line.number


def _summary(reader: TextReader, stop: re.Pattern[str], what: str) -> Unwrapped:
    return unwrap(reader.take_until(stop, what, guard=_SECTION))


def _rationale(reader: TextReader, what: str, *, last: bool) -> str:
    """Read ``Rationale:`` and its text, up to the next section or the end."""
    line, match = reader.expect(_RATIONALE, f"the rationale of {what}", "Rationale")
    first = Line(line.number, match[1].strip())
    if last:
        rest = reader.take_rest()
    else:
        rest = reader.take_until(_SECTION, f"the section after {what}")
    text = unwrap([first, *rest]).text
    if not text:
        if last:
            raise reader.ended(f"the text of the rationale of {what}")
        raise reader.error("empty rationale", line.number, "Rationale")
    return text


def _greatest_kp(
    reader: TextReader,
    summary: Unwrapped,
    pattern: re.Pattern[str],
    fallback_line: int,
    field: str,
) -> tuple[float, str | None]:
    """Find a sentence on the greatest Kp: the value and its NOAA scale."""
    match = pattern.search(summary.text)
    if match is None:
        line = summary.numbers[0] if summary.numbers else fallback_line
        raise reader.error(f"no sentence on the {field}", line, field)
    line = summary.line_at(match.start(1))
    if not _NUMBER.fullmatch(match[1]):
        raise reader.error(f"expected a Kp value, got {match[1]!r}", line, field)
    kp = float(match[1])
    _check_kp(reader, kp, line, field)
    scale = _SENTENCE_SCALE.search(match[2])
    return kp, scale[1] if scale is not None else None


def parse_three_day_forecast(
    raw: str | bytes, *, source_url: str = THREE_DAY_FORECAST_URL
) -> ThreeDayForecast:
    """Parse ``3-day-forecast.txt``.

    Section A gives the greatest observed and expected Kp and the Kp table,
    section B the probability of an S1 or greater radiation storm, section C
    the probabilities of R1-R2 and R3 or greater radio blackouts. Each
    section ends with a free-text rationale.

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or stops early.
        UnexpectedContent: If the content is HTML or another product.
        ParseError: If a value is inconsistent; the error gives the line.
    """
    reader, issued = open_text_product(raw, ("3-Day Forecast",))

    section_a = _section(reader, "A")
    geomagnetic = _summary(reader, _KP_BREAKDOWN, "the Kp breakdown")
    observed_kp, observed_scale = _greatest_kp(
        reader, geomagnetic, _OBSERVED, section_a, "greatest observed Kp"
    )
    expected_kp, expected_scale = _greatest_kp(
        reader, geomagnetic, _EXPECTED, section_a, "greatest expected Kp"
    )
    reader.expect(_KP_BREAKDOWN, "the Kp breakdown")
    days, kp = _kp_table(reader, issued, "the Kp breakdown")
    geomagnetic_rationale = _rationale(reader, "section A", last=False)

    _section(reader, "B")
    radiation = _summary(reader, _S_TITLE, "the solar radiation storm forecast")
    reader.expect(_S_TITLE, "the solar radiation storm forecast")
    line, s_days = _day_columns(reader, issued.date(), "the S forecast")
    _check_same_days(reader, s_days, days, line.number)
    s1 = _percent_row(reader, "S1 or greater", days, "the S forecast")
    radiation_rationale = _rationale(reader, "section B", last=False)

    _section(reader, "C")
    blackout = _summary(reader, _R_TITLE, "the radio blackout forecast")
    reader.expect(_R_TITLE, "the radio blackout forecast")
    line, r_days = _day_columns(reader, issued.date(), "the R forecast")
    _check_same_days(reader, r_days, days, line.number)
    r1_r2 = _percent_row(reader, "R1-R2", days, "the R forecast")
    r3 = _percent_row(reader, "R3 or greater", days, "the R forecast")
    blackout_rationale = _rationale(reader, "section C", last=True)

    return ThreeDayForecast(
        issued=issued,
        days=days,
        greatest_observed_kp=observed_kp,
        greatest_observed_scale=observed_scale,
        greatest_expected_kp=expected_kp,
        greatest_expected_scale=expected_scale,
        geomagnetic_summary=geomagnetic.text,
        kp=kp,
        geomagnetic_rationale=geomagnetic_rationale,
        solar_radiation_summary=radiation.text,
        s1_or_greater=s1,
        solar_radiation_rationale=radiation_rationale,
        radio_blackout_summary=blackout.text,
        r1_r2=r1_r2,
        r3_or_greater=r3,
        radio_blackout_rationale=blackout_rationale,
        source_url=source_url,
    )


# --- Geomagnetic forecast ----------------------------------------------------


def _daily_ap(
    reader: TextReader, pattern: re.Pattern[str], near: date, what: str
) -> DailyAp:
    line, match = reader.expect(pattern, what, "Ap")
    day = reader.date(match[2], match[1], near, line.number, "Ap")
    return DailyAp(day=day, ap=int(match[3]))


def _probability_row(
    reader: TextReader, label: str, days: tuple[date, ...]
) -> tuple[int, ...]:
    """Read a row like ``Active                25/20/15``."""
    pattern = re.compile(
        r"\s+".join(map(re.escape, label.split())) + r"\s+(\d+(?:/\d+)*)"
    )
    line, match = reader.expect(pattern, f"the {label!r} probabilities", label)
    values = tuple(_percent(reader, v, line.number, label) for v in match[1].split("/"))
    if len(values) != len(days):
        raise reader.error(
            f"{len(values)} values for {len(days)} days", line.number, label
        )
    return values


def parse_geomagnetic_forecast(
    raw: str | bytes, *, source_url: str = GEOMAGNETIC_FORECAST_URL
) -> GeomagneticForecast:
    """Parse ``3-day-geomag-forecast.txt``.

    The product gives the observed, estimated and predicted Ap, the
    probabilities of active to extreme geomagnetic conditions, and the Kp
    table of the next three days.

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or stops early.
        UnexpectedContent: If the content is HTML or another product.
        ParseError: If a value is inconsistent; the error gives the line.
    """
    reader, issued = open_text_product(raw, ("Geomagnetic Forecast",))
    near = issued.date()

    reader.expect(_AP_TITLE, "'NOAA Ap Index Forecast'")
    observed = _daily_ap(reader, _AP_OBSERVED, near, "'Observed Ap DD Mon NNN'")
    estimated = _daily_ap(reader, _AP_ESTIMATED, near, "'Estimated Ap DD Mon NNN'")
    line, match = reader.expect(
        _AP_PREDICTED, "'Predicted Ap DD Mon-DD Mon NNN-NNN-NNN'", "Ap"
    )
    days = tuple(_day_range(reader, match, 1, near, line.number))
    values = match[5].split("-")
    if len(values) != len(days):
        raise reader.error(
            f"{len(values)} Ap values for {len(days)} days", line.number, "Ap"
        )
    predicted = tuple(
        DailyAp(day=d, ap=int(v)) for d, v in zip(days, values, strict=True)
    )

    line, match = reader.expect(
        _PROBABILITIES_TITLE, "the geomagnetic activity probabilities", "days"
    )
    title_days = tuple(_day_range(reader, match, 1, near, line.number))
    _check_same_days(reader, title_days, days, line.number)
    active, minor, moderate, extreme = (
        _probability_row(reader, label, days) for label in _PROBABILITY_ROWS
    )

    line, match = reader.expect(_KP_FORECAST_TITLE, "the Kp index forecast", "days")
    title_days = tuple(_day_range(reader, match, 1, near, line.number))
    _check_same_days(reader, title_days, days, line.number)
    _, kp = _kp_table(reader, issued, "the Kp index forecast", days)
    reader.finish("the Kp index forecast")

    return GeomagneticForecast(
        issued=issued,
        observed_ap=observed,
        estimated_ap=estimated,
        days=days,
        predicted_ap=predicted,
        active=active,
        minor_storm=minor,
        moderate_storm=moderate,
        strong_extreme_storm=extreme,
        kp=kp,
        source_url=source_url,
    )


# --- 27-day outlook ----------------------------------------------------------


def _outlook_day(reader: TextReader, line: Line, previous: date | None) -> OutlookDay:
    tokens = line.text.split()
    if len(tokens) != 6:
        raise reader.error(
            f"expected date, radio flux, Ap and largest Kp, got {line.text!r}",
            line.number,
        )
    year, month, day, flux, ap, kp = tokens
    when: date | None = None
    if _INTEGER.fullmatch(year) and _INTEGER.fullmatch(day) and month in MONTHS:
        try:
            when = date(int(year), MONTHS[month], int(day))
        except ValueError:
            when = None
    if when is None:
        raise reader.error(f"not a date: {' '.join(tokens[:3])!r}", line.number, "date")
    if previous is not None and when - previous != timedelta(days=1):
        raise reader.error(f"{when} does not follow {previous}", line.number, "date")
    if not _FLUX.fullmatch(flux):
        raise reader.error(
            f"expected a radio flux, got {flux!r}", line.number, "radio flux"
        )
    if not _INTEGER.fullmatch(ap):
        raise reader.error(f"expected an Ap index, got {ap!r}", line.number, "Ap")
    if not (_INTEGER.fullmatch(kp) and int(kp) <= 9):
        raise reader.error(
            f"expected a Kp from 0 to 9, got {kp!r}", line.number, "largest Kp"
        )
    return OutlookDay(day=when, radio_flux=float(flux), ap=int(ap), largest_kp=int(kp))


def parse_27_day_outlook(
    raw: str | bytes, *, source_url: str = TWENTY_SEVEN_DAY_OUTLOOK_URL
) -> TwentySevenDayOutlook:
    """Parse ``27-day-outlook.txt``.

    The product holds 27 rows, one per day: date, predicted 10.7 cm radio
    flux, planetary A index and largest Kp. Fewer rows mean the file stops
    early.

    Args:
        raw: The content.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or stops early.
        UnexpectedContent: If the content is HTML or another product.
        ParseError: If a value is inconsistent; the error gives the line.
    """
    reader, issued = open_text_product(raw, (_OUTLOOK_PRODUCT,))
    days: list[OutlookDay] = []
    for row in range(1, _OUTLOOK_DAYS + 1):
        line = reader.next(f"row {row} of {_OUTLOOK_DAYS}")
        previous = days[-1].day if days else None
        days.append(_outlook_day(reader, line, previous))
    reader.finish(f"the {_OUTLOOK_DAYS} rows")
    return TwentySevenDayOutlook(issued=issued, days=tuple(days), source_url=source_url)
