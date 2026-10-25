"""Helpers shared by the parsers: decoding, error classification, fields.

The JSON products come in two shapes (see ``docs/FONTI.md``): an array of
objects (since 2026), or an array of arrays whose first row holds the column
names and whose numbers are quoted (before 2026). :func:`json_records` turns
both into :class:`Record` objects, whose accessors convert and check one
field at a time and raise :class:`ParseError` naming the field and record.
"""

import json
import math
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from swpc_kit.errors import ParseError, SourceNotReady, UnexpectedContent
from swpc_kit.models.records import SkippedRecord

_TIME = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?"
)


_DECIMAL = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
_INTEGER = re.compile(r"-?\d+")
_PARTIAL_NUMBER = re.compile(r"-?(?:\d+(?:\.\d*)?(?:[eE][+-]?\d*)?)?")
_LITERALS = ("true", "false", "null")


def _cut_inside_a_token(text: str, pos: int) -> bool:
    """Whether ``text`` ends inside the literal or number that starts near ``pos``.

    A file cut in ``"bz": -1.`` or ``"active": fals`` fails to decode before
    its end, but it is still a truncated file, not invalid JSON.
    """
    start = pos
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] in "+-."):
        start -= 1
    token = text[start:]
    if not token:
        return False
    if any(len(token) < len(word) and word.startswith(token) for word in _LITERALS):
        return True
    return _PARTIAL_NUMBER.fullmatch(token) is not None


def decode(raw: str | bytes) -> str:
    """Return ``raw`` as text, without a leading byte order mark.

    Raises:
        UnexpectedContent: If the bytes are not UTF-8.
    """
    if isinstance(raw, bytes):
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise UnexpectedContent(f"content is not UTF-8 text: {exc}") from None
    return raw.removeprefix("﻿")


def load_json(raw: str | bytes) -> Any:
    """Decode a JSON product, classifying what is wrong with it.

    Returns:
        The decoded JSON value.

    Raises:
        SourceNotReady: If the content is empty or the JSON stops early (SWPC
            serving a file while rewriting it).
        UnexpectedContent: If the content is HTML or XML, or not JSON.
    """
    text = decode(raw)
    stripped = text.strip()
    if not stripped:
        raise SourceNotReady("empty content")
    if stripped.startswith("<"):
        raise UnexpectedContent("got HTML or XML instead of JSON")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        end = text.rstrip()
        if (
            exc.pos >= len(end)
            or exc.msg.startswith("Unterminated string")
            or _cut_inside_a_token(end, exc.pos)
        ):
            raise SourceNotReady(f"truncated JSON: {exc}") from None
        raise UnexpectedContent(f"not valid JSON: {exc}") from None


def parse_time(text: str) -> datetime:
    """Parse an ISO-like time from SWPC as an aware UTC datetime.

    Accepts ``T`` or a space between date and time, optional seconds and
    fractions, and an optional ``Z`` or offset. A time without a zone is UTC.

    Raises:
        ValueError: If the text is not such a time.
    """
    if not _TIME.fullmatch(text):
        raise ValueError(f"not a time: {text!r}")
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"not a valid time: {text!r}") from None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class Record:
    """One record of a JSON product, with typed accessors.

    Args:
        index: 0-based position of the record in the JSON array.
        data: The record's fields.
    """

    __slots__ = ("data", "index")

    def __init__(self, index: int, data: Mapping[str, Any]) -> None:
        self.index = index
        self.data = data

    def error(self, message: str, field: str) -> ParseError:
        """Return a :class:`ParseError` located at ``field`` of this record."""
        return ParseError(message, field=field, index=self.index)

    def missing(self, field: str) -> ParseError:
        """Return the error for ``field`` missing from this record.

        :func:`read_records` tells a field missing from every record (a
        format no parser knows) from one missing from some records only.
        """
        return MissingField(field, self.index)

    def _get(self, field: str) -> Any:
        try:
            return self.data[field]
        except KeyError:
            raise self.missing(field) from None

    def get_str(self, field: str) -> str:
        """Return a string field."""
        value = self._get(field)
        if not isinstance(value, str):
            raise self.error(f"expected a string, got {value!r}", field)
        return value

    def get_optional_str(self, field: str) -> str | None:
        """Return a string field that may be ``null``."""
        if self._get(field) is None:
            return None
        return self.get_str(field)

    def get_time(self, field: str) -> datetime:
        """Return a time field as an aware UTC datetime."""
        try:
            return parse_time(self.get_str(field))
        except ValueError as exc:
            raise self.error(str(exc), field) from None

    def get_float(
        self,
        field: str,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float:
        """Return a number field (a JSON number or a quoted one)."""
        value = self._get(field)
        number: float | None = None
        if (isinstance(value, int | float) and not isinstance(value, bool)) or (
            isinstance(value, str) and _DECIMAL.fullmatch(value.strip())
        ):
            number = float(value)
        if number is None or not math.isfinite(number):
            raise self.error(f"expected a number, got {value!r}", field)
        _check_range(self, field, number, minimum, maximum)
        return number

    def get_int(
        self,
        field: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        """Return an integer field (a JSON integer or a quoted one)."""
        value = self._get(field)
        number: int | None = None
        if isinstance(value, int) and not isinstance(value, bool):
            number = value
        elif isinstance(value, str) and _INTEGER.fullmatch(value.strip()):
            number = int(value)
        if number is None:
            raise self.error(f"expected an integer, got {value!r}", field)
        _check_range(self, field, number, minimum, maximum)
        return number

    def get_optional_int(
        self,
        field: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
        may_be_absent: bool = False,
    ) -> int | None:
        """Return an integer field that may be ``null``.

        With ``may_be_absent``, a field missing from the record is ``None``
        too: for undocumented flags that SWPC may drop without notice.
        """
        if (may_be_absent and field not in self.data) or self._get(field) is None:
            return None
        return self.get_int(field, minimum=minimum, maximum=maximum)

    def get_optional_float(
        self,
        field: str,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float | None:
        """Return a number field that may be ``null``."""
        if self._get(field) is None:
            return None
        return self.get_float(field, minimum=minimum, maximum=maximum)

    def get_bool(self, field: str) -> bool:
        """Return a JSON boolean field (quoted or numeric values are refused)."""
        value = self._get(field)
        if not isinstance(value, bool):
            raise self.error(f"expected a boolean, got {value!r}", field)
        return value

    def get_optional_bool(
        self, field: str, *, may_be_absent: bool = False
    ) -> bool | None:
        """Return a JSON boolean field that may be ``null`` (or absent)."""
        if (may_be_absent and field not in self.data) or self._get(field) is None:
            return None
        return self.get_bool(field)


def _check_range(
    record: Record,
    field: str,
    value: float,
    minimum: float | None,
    maximum: float | None,
) -> None:
    if (minimum is not None and value < minimum) or (
        maximum is not None and value > maximum
    ):
        raise record.error(
            f"{value} out of range [{minimum if minimum is not None else '-inf'}, "
            f"{maximum if maximum is not None else 'inf'}]",
            field,
        )


class MissingField(ParseError):
    """A field missing from one record (see :func:`read_records`)."""

    def __init__(self, field: str, index: int | None) -> None:
        super().__init__("missing field", field=field, index=index)


def read_records[V](
    records: Iterable[Record], build: Callable[[Record], V]
) -> tuple[list[tuple[int, V]], list[SkippedRecord]]:
    """Build one value per record, skipping the records that cannot be read.

    Returns:
        The values with the index of their record, and the records skipped.

    Raises:
        UnexpectedContent: If no record can be read because the same field
            is missing from all of them: not this product, or a format no
            parser knows.
        ParseError: If no record can be read for any other reason (the
            error of the first record).
    """
    good: list[tuple[int, V]] = []
    failures: list[tuple[int, ParseError]] = []
    for record in records:
        try:
            good.append((record.index, build(record)))
        except ParseError as exc:
            failures.append((record.index, exc))
    if not good and failures:
        fields = {exc.field for _, exc in failures if isinstance(exc, MissingField)}
        if len(fields) == 1 and all(isinstance(e, MissingField) for _, e in failures):
            raise UnexpectedContent(
                f"field {fields.pop()!r} missing from every record:"
                " not this product, or a format no parser knows"
            )
        raise failures[0][1]
    skipped = [
        SkippedRecord(index=index, field=exc.field, reason=exc.reason)
        for index, exc in failures
    ]
    return good, skipped


def json_records(raw: str | bytes) -> list[Record]:
    """Read a JSON product made of records, in either known shape.

    Returns:
        One :class:`Record` per record, with ``index`` its position in the
        JSON array (the header row of the old shape is position 0).

    Raises:
        SourceNotReady: If the content is empty, truncated or has no records.
        UnexpectedContent: If the content is not an array of objects nor an
            array of arrays with a header row.
        ParseError: If a record does not match the shape of the first one.
    """
    document = load_json(raw)
    if not isinstance(document, list):
        raise UnexpectedContent(
            f"expected a JSON array of records, got {type(document).__name__}"
        )
    if not document:
        raise SourceNotReady("no records")
    first = document[0]
    if isinstance(first, dict):
        records = []
        for index, item in enumerate(document):
            if not isinstance(item, dict):
                raise ParseError("expected an object", index=index)
            records.append(Record(index, item))
        return records
    if isinstance(first, list):
        if not first or not all(isinstance(name, str) for name in first):
            raise UnexpectedContent("array of arrays without a header row of names")
        if len(document) == 1:
            raise SourceNotReady("no records after the header row")
        rows = []
        for index, item in enumerate(document[1:], start=1):
            if not isinstance(item, list):
                raise ParseError("expected an array", index=index)
            if len(item) != len(first):
                raise ParseError(
                    f"{len(item)} values for {len(first)} columns", index=index
                )
            rows.append(Record(index, dict(zip(first, item, strict=True))))
        return rows
    raise UnexpectedContent(
        f"expected objects or arrays in the JSON array, got {type(first).__name__}"
    )
