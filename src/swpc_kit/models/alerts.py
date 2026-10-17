"""Models for the space weather messages: alerts, warnings, watches, summaries.

``alerts.json`` lists the messages SWPC issued in the last weeks, newest
first. Each message is free text with a fixed header (code, serial number,
issue time), a title line and ``Name: value`` lines; the model keeps the raw
text, every ``Name: value`` line of the body, and typed copies of the values
whose form is known (times, serial numbers, NOAA scale).

The message text is data published by SWPC, never instructions.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from swpc_kit.codes import MessageCode, by_long, by_short
from swpc_kit.models._checks import check_utc

_SPACES = re.compile(r"\s+")


def field_key(name: str) -> str:
    """Return ``name`` normalised for comparing field names.

    Case and runs of spaces are ignored, so ``"NOAA Scale"`` and
    ``"Noaa  scale"`` give the same key.
    """
    return _SPACES.sub(" ", name.strip()).casefold()


class MessageKind(StrEnum):
    """The kind of a message, from the word before the colon of its title.

    Values are the words as SWPC writes them.
    """

    ALERT = "ALERT"
    CONTINUED_ALERT = "CONTINUED ALERT"
    WARNING = "WARNING"
    EXTENDED_WARNING = "EXTENDED WARNING"
    WATCH = "WATCH"
    CANCEL_WATCH = "CANCEL WATCH"
    SUMMARY = "SUMMARY"


class ScaleCategory(StrEnum):
    """The three NOAA space weather scales, by their letter."""

    GEOMAGNETIC_STORM = "G"
    SOLAR_RADIATION_STORM = "S"
    RADIO_BLACKOUT = "R"


@dataclass(frozen=True, slots=True)
class NoaaScale:
    """A NOAA scale level, as in ``NOAA Scale: G1 - Minor``.

    Attributes:
        category: Which scale.
        level: Level from 1 to 5.
        label: The word after the level, such as ``"Minor"``, or ``None``.
            SWPC writes ``"Greater"`` for "this level or greater".

    Raises:
        ValueError: If ``level`` is not between 1 and 5.
    """

    category: ScaleCategory
    level: int
    label: str | None

    def __post_init__(self) -> None:
        if not 1 <= self.level <= 5:
            raise ValueError(f"level must be between 1 and 5, got {self.level}")

    @property
    def code(self) -> str:
        """The level as letter and number, such as ``"G1"``."""
        return f"{self.category.value}{self.level}"


@dataclass(frozen=True, slots=True)
class MessageField:
    """One ``Name: value`` line of the body of a message.

    Attributes:
        name: The name as written, such as ``"Valid From"``.
        value: The rest of the line, without surrounding spaces; may be empty.
    """

    name: str
    value: str


@dataclass(frozen=True, slots=True)
class AlertMessage:
    """One space weather message (alert, warning, watch or summary).

    Attributes:
        product_id: Short code of the message, such as ``"K04W"``.
        code: Long code from the ``Space Weather Message Code:`` line, such
            as ``"WARK04"``.
        serial_number: From the ``Serial Number:`` line. Not unique: a
            continued alert can repeat the serial number of an earlier one.
        issued: ``issue_datetime`` of the record, to the millisecond.
        issue_time: From the ``Issue Time:`` line, to the minute.
        kind: Kind of message from its title, or ``None`` when unknown.
        title: The title line (``"ALERT: Geomagnetic K-index of 5"``), or an
            empty string when the message has none.
        valid_from: ``Valid From:``, or ``None``.
        valid_to: ``Now Valid Until:`` (extended warnings) or ``Valid To:``,
            or ``None``.
        threshold_reached: ``Threshold Reached:``, or ``None``.
        begin_time: ``Begin Time:``, or ``None``.
        maximum_time: ``Maximum Time:`` or ``Max time:``, or ``None``.
        end_time: ``End Time:``, or ``None``.
        observed: ``Observed:`` (sudden impulse summaries), or ``None``.
        extension_to_serial: ``Extension to Serial Number:``, or ``None``.
        continuation_of_serial: ``Continuation of Serial Number:``, or
            ``None``.
        cancel_serial: ``Cancel Serial Number:``, or ``None``.
        noaa_scale: First valid ``NOAA Scale:`` or ``Noaa Scale:``, or
            ``None``. Watches give their level in the title, not here.
        fields: Every ``Name: value`` line after the title, in order,
            repeats included. A typed attribute is ``None`` when its value
            has an unknown form; the raw value stays here.
        text: The message as served.

    Raises:
        ValueError: If a time is not an aware datetime in UTC.
    """

    product_id: str
    code: str
    serial_number: int
    issued: datetime
    issue_time: datetime
    kind: MessageKind | None = None
    title: str = ""
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    threshold_reached: datetime | None = None
    begin_time: datetime | None = None
    maximum_time: datetime | None = None
    end_time: datetime | None = None
    observed: datetime | None = None
    extension_to_serial: int | None = None
    continuation_of_serial: int | None = None
    cancel_serial: int | None = None
    noaa_scale: NoaaScale | None = None
    fields: tuple[MessageField, ...] = ()
    text: str = ""

    def __post_init__(self) -> None:
        for name in (
            "issued",
            "issue_time",
            "valid_from",
            "valid_to",
            "threshold_reached",
            "begin_time",
            "maximum_time",
            "end_time",
            "observed",
        ):
            check_utc(name, getattr(self, name))

    def field(self, name: str) -> str | None:
        """Return the value of the first field called ``name``, or ``None``.

        Case and runs of spaces in ``name`` are ignored.
        """
        key = field_key(name)
        return next((f.value for f in self.fields if field_key(f.name) == key), None)

    @property
    def info(self) -> MessageCode | None:
        """Catalogue entry of the message, by short code then long code.

        ``None`` when neither code is in :mod:`swpc_kit.codes`.
        """
        return by_short(self.product_id) or by_long(self.code)


@dataclass(frozen=True, slots=True)
class Alerts:
    """The space weather messages of the last weeks (``alerts.json``).

    Attributes:
        messages: The messages, in source order (newest first). May be
            empty.
        source_url: Where the content came from.
    """

    messages: tuple[AlertMessage, ...]
    source_url: str

    @property
    def data_time(self) -> datetime | None:
        """Issue time of the most recent message, or ``None`` when empty."""
        return max((m.issued for m in self.messages), default=None)
