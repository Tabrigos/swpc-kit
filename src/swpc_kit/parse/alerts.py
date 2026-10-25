r"""Parser for ``alerts.json``, the space weather messages of the last weeks.

The JSON is an array of ``{product_id, issue_datetime, message}`` objects.
Each ``message`` is free text: lines end with ``\r\n`` or ``\n`` (both are
mixed in one message), the first three lines are the header
(``Space Weather Message Code:``, ``Serial Number:``, ``Issue Time:``), then
come a title such as ``ALERT: ...`` and ``Name: value`` lines.

The header is mandatory: if it is missing or broken the parser raises
:class:`~swpc_kit.errors.ParseError`. Everything else is optional: a value
in an unknown form gives ``None`` in the typed attribute and stays as text
in the message fields. The message text is data, never instructions.
"""

import re
from collections.abc import Sequence
from datetime import UTC, datetime

from swpc_kit.errors import UnexpectedContent
from swpc_kit.models.alerts import (
    AlertMessage,
    Alerts,
    MessageField,
    MessageKind,
    NoaaScale,
    ScaleCategory,
    field_key,
)
from swpc_kit.models.records import SkippedRecord
from swpc_kit.parse._common import Record, load_json, read_records

ALERTS_URL = "https://services.swpc.noaa.gov/products/alerts.json"

_CODE_LABEL = "Space Weather Message Code"
_SERIAL_LABEL = "Serial Number"
_ISSUE_LABEL = "Issue Time"

_MONTHS = {
    name: number
    for number, name in enumerate(
        [
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
        ],
        start=1,
    )
}
_TEXT_TIME = re.compile(r"(\d{4}) ([A-Z][a-z]{2}) (\d{1,2}) (\d{2})(\d{2}) UTC")
_NEWLINE = re.compile(r"\r\n|\r|\n")
_CODE = re.compile(r"[A-Za-z0-9]+")
_SERIAL = re.compile(r"\d+")
_TITLE = re.compile(r"([A-Z]+(?: [A-Z]+)*):")
_FIELD = re.compile(r"([A-Za-z][A-Za-z0-9 ()/-]*?)\s*:(.*)")
_DATE_KEY = re.compile(r"[A-Z][a-z]{2} \d{1,2}")
_SCALE = re.compile(r"([GSR])([1-5])(?:\s*-\s*(.*))?")


def _text_time(text: str) -> datetime:
    """Parse a time written like ``2026 Oct 13 2058 UTC``.

    Raises:
        ValueError: If the text is not such a time.
    """
    match = _TEXT_TIME.fullmatch(text)
    if match is None or match.group(2) not in _MONTHS:
        raise ValueError(f"expected a time like '2026 Oct 13 2058 UTC', got {text!r}")
    year, month, day, hour, minute = match.groups()
    try:
        return datetime(
            int(year), _MONTHS[month], int(day), int(hour), int(minute), tzinfo=UTC
        )
    except ValueError as exc:
        raise ValueError(f"not a valid time: {text!r} ({exc})") from None


def _header(record: Record, lines: Sequence[str], label: str) -> tuple[int, str]:
    """Return the position and value of the first line ``label: value``."""
    prefix = label.lower() + ":"
    for number, line in enumerate(lines):
        if line[: len(prefix)].lower() == prefix:
            return number, line[len(prefix) :].strip()
    raise record.error("missing header line", f"message.{label}")


def _fields(lines: Sequence[str]) -> tuple[MessageField, ...]:
    """Return the ``Name: value`` lines.

    Day labels of watches (``Oct 12:  None (Below G1)``) and lines starting
    with a URL are not fields.
    """
    fields = []
    for line in lines:
        match = _FIELD.fullmatch(line.strip())
        if match is None:
            continue
        name, value = match.group(1).strip(), match.group(2).strip()
        if _DATE_KEY.fullmatch(name) or value.startswith("//"):
            continue
        fields.append(MessageField(name, value))
    return tuple(fields)


def _values(fields: Sequence[MessageField], *names: str) -> list[str]:
    keys = {field_key(n) for n in names}
    return [f.value for f in fields if field_key(f.name) in keys]


def _optional_time(fields: Sequence[MessageField], *names: str) -> datetime | None:
    """Return the first field found, by order of ``names``, as a time.

    Returns ``None`` when no such field exists or its value has another form.
    """
    for name in names:
        values = _values(fields, name)
        if values:
            try:
                return _text_time(values[0])
            except ValueError:
                return None
    return None


def _optional_serial(fields: Sequence[MessageField], name: str) -> int | None:
    """Return the named field as a serial number, or ``None``."""
    values = _values(fields, name)
    if not values or not _SERIAL.fullmatch(values[0]):
        return None
    return int(values[0])


def _scale(fields: Sequence[MessageField]) -> NoaaScale | None:
    for value in _values(fields, "NOAA Scale"):
        match = _SCALE.fullmatch(value)
        if match is not None:
            label = (match.group(3) or "").strip() or None
            return NoaaScale(ScaleCategory(match.group(1)), int(match.group(2)), label)
    return None


def _kind(title: str) -> MessageKind | None:
    match = _TITLE.match(title)
    if match is None:
        return None
    try:
        return MessageKind(match.group(1))
    except ValueError:
        return None


def _message(record: Record) -> AlertMessage:
    product_id = record.get_str("product_id").strip()
    if not product_id:
        raise record.error("empty product_id", "product_id")
    issued = record.get_time("issue_datetime")
    text = record.get_str("message")
    lines = _NEWLINE.split(text)

    end, code = _header(record, lines, _CODE_LABEL)
    if not _CODE.fullmatch(code):
        raise record.error(f"expected a code, got {code!r}", f"message.{_CODE_LABEL}")
    position, serial = _header(record, lines, _SERIAL_LABEL)
    end = max(end, position)
    if not _SERIAL.fullmatch(serial):
        raise record.error(
            f"expected a serial number, got {serial!r}", f"message.{_SERIAL_LABEL}"
        )
    position, issue = _header(record, lines, _ISSUE_LABEL)
    end = max(end, position)
    try:
        issue_time = _text_time(issue)
    except ValueError as exc:
        raise record.error(str(exc), f"message.{_ISSUE_LABEL}") from None

    body = lines[end + 1 :]
    start = next((n for n, line in enumerate(body) if line.strip()), len(body))
    title = body[start].strip() if start < len(body) else ""
    fields = _fields(body[start + 1 :])

    return AlertMessage(
        product_id=product_id,
        code=code,
        serial_number=int(serial),
        issued=issued,
        issue_time=issue_time,
        kind=_kind(title),
        title=title,
        valid_from=_optional_time(fields, "Valid From"),
        valid_to=_optional_time(fields, "Now Valid Until", "Valid To"),
        threshold_reached=_optional_time(fields, "Threshold Reached"),
        begin_time=_optional_time(fields, "Begin Time"),
        maximum_time=_optional_time(fields, "Maximum Time", "Max time"),
        end_time=_optional_time(fields, "End Time"),
        observed=_optional_time(fields, "Observed"),
        extension_to_serial=_optional_serial(fields, "Extension to Serial Number"),
        continuation_of_serial=_optional_serial(
            fields, "Continuation of Serial Number"
        ),
        cancel_serial=_optional_serial(fields, "Cancel Serial Number"),
        noaa_scale=_scale(fields),
        fields=fields,
        text=text,
    )


def parse_alerts(raw: str | bytes, *, source_url: str = ALERTS_URL) -> Alerts:
    """Parse ``alerts.json`` (space weather messages of the last weeks).

    Args:
        raw: The content. An empty array gives a model without messages.
        source_url: Where the content came from.

    Raises:
        SourceNotReady: If the content is empty or truncated.
        UnexpectedContent: If the content is not an array of objects.
        ParseError: If a record or the header of a message is missing or
            inconsistent; the error names the field and the record.
    """
    document = load_json(raw)
    if not isinstance(document, list):
        raise UnexpectedContent(
            f"expected a JSON array of messages, got {type(document).__name__}"
        )
    if document and not isinstance(document[0], dict):
        raise UnexpectedContent(
            f"expected objects in the JSON array, got {type(document[0]).__name__}"
        )
    not_objects = [
        SkippedRecord(index=index, field=None, reason="expected an object")
        for index, item in enumerate(document)
        if not isinstance(item, dict)
    ]
    records = [
        Record(index, item)
        for index, item in enumerate(document)
        if isinstance(item, dict)
    ]
    read, skipped = read_records(records, _message)
    return Alerts(
        messages=tuple(message for _, message in read),
        source_url=source_url,
        skipped=tuple(sorted([*skipped, *not_objects], key=lambda s: s.index)),
    )
