"""Reader shared by the SWPC text products: header, lines and errors.

A text product starts with a header::

    :Product: 3-Day Forecast
    :Issued: 2026 Oct 15 1230 UTC
    # Prepared by the U.S. Dept. of Commerce, NOAA, ...

:func:`open_text_product` checks the header and returns a
:class:`TextReader` placed after the ``#`` comments. The reader walks the
remaining lines and classifies what goes wrong:

- the content ends before an expected element: :class:`SourceNotReady` (SWPC
  served the file while rewriting it);
- an element is there but not as expected: :class:`ParseError` with its
  1-based line number;
- except when that element is on the last line and the content does not end
  with a line break: the line was probably cut, so :class:`SourceNotReady`.
"""

import re
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from swpc_kit.errors import ParseError, SourceNotReady, SwpcError, UnexpectedContent
from swpc_kit.parse._common import decode

MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ),
        start=1,
    )
}
"""English month abbreviations as SWPC writes them, to month numbers."""

_PRODUCT = re.compile(r":Product:\s*(.*)")
_ISSUED = re.compile(
    r":Issued:\s*(\d{4})\s+([A-Za-z]{3})\s+(\d{1,2})\s+(\d{2})(\d{2})\s+UTC"
)


@dataclass(frozen=True, slots=True)
class Line:
    """One line of a text product.

    Attributes:
        number: 1-based line number.
        text: The line without leading and trailing whitespace.
    """

    number: int
    text: str


@dataclass(frozen=True, slots=True)
class Unwrapped:
    """Free text with its line wrapping undone, mapped back to its lines.

    Attributes:
        text: Wrapped lines joined with a space, paragraphs with a blank line.
        starts: Offset in ``text`` where each source line starts.
        numbers: Line number of each source line, aligned with ``starts``.
    """

    text: str
    starts: tuple[int, ...]
    numbers: tuple[int, ...]

    def line_at(self, offset: int) -> int:
        """Return the line number of the character at ``offset``."""
        index = max(bisect_right(self.starts, offset) - 1, 0)
        return self.numbers[index]


def unwrap(lines: Sequence[Line]) -> Unwrapped:
    """Join wrapped lines into text, keeping blank lines as paragraph breaks."""
    parts: list[str] = []
    starts: list[int] = []
    numbers: list[int] = []
    length = 0
    pending_break = False
    for line in lines:
        if not line.text:
            pending_break = bool(parts)
            continue
        if parts:
            separator = "\n\n" if pending_break else " "
            parts.append(separator)
            length += len(separator)
        pending_break = False
        starts.append(length)
        numbers.append(line.number)
        parts.append(line.text)
        length += len(line.text)
    return Unwrapped("".join(parts), tuple(starts), tuple(numbers))


def nearest_date(month: int, day: int, near: date) -> date:
    """Place a month and day without a year in the year closest to ``near``.

    A forecast issued on 31 December for ``Jan 01`` gets the next year; an
    observation of ``31 Dec`` issued on 1 January gets the previous one.

    Raises:
        ValueError: If no year has that day (such as 31 April).
    """
    candidates = []
    for year in (near.year - 1, near.year, near.year + 1):
        try:
            candidates.append(date(year, month, day))
        except ValueError:
            continue
    if not candidates:
        raise ValueError(f"no such day: month {month}, day {day}")
    return min(candidates, key=lambda d: abs(d - near))


class TextReader:
    """Walks the lines of a text product, raising the right error.

    Args:
        text: The decoded content.
    """

    __slots__ = ("_complete", "_lines", "_pos")

    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()
        self._complete = text.endswith(("\n", "\r"))
        self._pos = 0

    def is_cut(self, line: int) -> bool:
        """Whether ``line`` is the last line and has no line break after it."""
        return line >= len(self._lines) and not self._complete

    def error(self, message: str, line: int, field: str | None = None) -> SwpcError:
        """Return the error for an unexpected ``line``.

        Returns:
            :class:`SourceNotReady` if the line looks cut (see :meth:`is_cut`),
            otherwise :class:`ParseError` naming ``field`` and ``line``.
        """
        if self.is_cut(line):
            return SourceNotReady(f"content ends inside line {line}: {message}")
        return ParseError(message, field=field, line=line)

    @staticmethod
    def ended(what: str) -> SourceNotReady:
        """Return the error for content that ends before ``what``."""
        return SourceNotReady(f"content ends before {what}")

    def _line(self) -> Line:
        return Line(self._pos + 1, self._lines[self._pos].strip())

    def peek(self) -> Line | None:
        """Return the next non-blank line without consuming it, or ``None``."""
        while self._pos < len(self._lines) and not self._lines[self._pos].strip():
            self._pos += 1
        if self._pos >= len(self._lines):
            return None
        return self._line()

    def next(self, what: str) -> Line:
        """Consume and return the next non-blank line.

        Raises:
            SourceNotReady: If the content ends first.
        """
        line = self.peek()
        if line is None:
            raise self.ended(what)
        self._pos += 1
        return line

    def expect(
        self, pattern: re.Pattern[str], what: str, field: str | None = None
    ) -> tuple[Line, re.Match[str]]:
        """Consume the next non-blank line, which must match ``pattern`` fully.

        Raises:
            SourceNotReady: If the content ends first, or the line looks cut.
            ParseError: If the line does not match.
        """
        line = self.next(what)
        match = pattern.fullmatch(line.text)
        if match is None:
            raise self.error(f"expected {what}, got {line.text!r}", line.number, field)
        return line, match

    def skip_comments(self) -> None:
        """Skip blank lines and ``#`` comment lines."""
        while self._pos < len(self._lines):
            text = self._lines[self._pos].strip()
            if text and not text.startswith("#"):
                return
            self._pos += 1

    def take_until(
        self,
        stop: re.Pattern[str],
        what: str,
        *,
        guard: re.Pattern[str] | None = None,
        field: str | None = None,
    ) -> list[Line]:
        """Consume lines, blank ones included, up to a line matching ``stop``.

        The ``stop`` line is left for the next call.

        Raises:
            SourceNotReady: If the content ends first.
            ParseError: If a line matching ``guard`` comes first.
        """
        lines: list[Line] = []
        while self._pos < len(self._lines):
            line = self._line()
            if stop.fullmatch(line.text):
                return lines
            if guard is not None and guard.fullmatch(line.text):
                raise self.error(
                    f"expected {what} before {line.text!r}", line.number, field
                )
            lines.append(line)
            self._pos += 1
        raise self.ended(what)

    def take_rest(self) -> list[Line]:
        """Consume and return every remaining line, blank ones included."""
        rest = [
            Line(n + 1, self._lines[n].strip())
            for n in range(self._pos, len(self._lines))
        ]
        self._pos = len(self._lines)
        return rest

    def finish(self, after: str) -> None:
        """Check that only blank lines remain.

        Raises:
            ParseError: If there is more content after ``after``.
        """
        line = self.peek()
        if line is not None:
            raise self.error(
                f"unexpected content after {after}: {line.text!r}", line.number
            )

    def date(
        self, month: str, day: str, near: date, line: int, field: str | None
    ) -> date:
        """Return the date of a month abbreviation and day, near ``near``.

        Raises:
            ParseError: If the month or day is not valid.
        """
        number = MONTHS.get(month.title())
        if number is None:
            raise self.error(f"unknown month {month!r}", line, field)
        try:
            return nearest_date(number, int(day), near)
        except ValueError as exc:
            raise self.error(str(exc), line, field) from None


def open_text_product(
    raw: str | bytes, products: Sequence[str]
) -> tuple[TextReader, datetime]:
    """Check the header of a text product and return a reader after it.

    Args:
        raw: The content.
        products: Accepted values of ``:Product:``, compared ignoring case and
            repeated spaces.

    Returns:
        A reader placed after the header and its ``#`` comments, and the
        ``:Issued:`` time.

    Raises:
        SourceNotReady: If the content is empty or ends inside the header.
        UnexpectedContent: If the content is HTML, not a text product, or a
            different product.
        ParseError: If the ``:Issued:`` line is not valid.
    """
    text = decode(raw)
    if not text.strip():
        raise SourceNotReady("empty content")
    if text.lstrip().startswith("<"):
        raise UnexpectedContent("got HTML or XML instead of a text product")
    reader = TextReader(text)
    first = reader.next("the ':Product:' line")
    match = _PRODUCT.fullmatch(first.text)
    if match is None:
        if reader.is_cut(first.number) and ":Product:".startswith(first.text):
            raise reader.ended("the end of the ':Product:' line")
        raise UnexpectedContent(f"expected a ':Product:' line, got {first.text[:80]!r}")
    name = " ".join(match[1].split())
    accepted = [" ".join(p.split()) for p in products]
    if name.casefold() not in (p.casefold() for p in accepted):
        if reader.is_cut(first.number) and any(
            p.casefold().startswith(name.casefold()) for p in accepted
        ):
            raise reader.ended("the end of the ':Product:' line")
        raise UnexpectedContent(f"expected product {accepted[0]!r}, got {name!r}")

    line, match = reader.expect(_ISSUED, "':Issued: YYYY Mon DD HHMM UTC'", "Issued")
    year, month, day, hour, minute = match.groups()
    number = MONTHS.get(month.title())
    if number is None:
        raise reader.error(f"unknown month {month!r}", line.number, "Issued")
    try:
        issued = datetime(
            int(year), number, int(day), int(hour), int(minute), tzinfo=UTC
        )
    except ValueError as exc:
        raise reader.error(f"not a valid time: {exc}", line.number, "Issued") from None
    reader.skip_comments()
    return reader, issued
