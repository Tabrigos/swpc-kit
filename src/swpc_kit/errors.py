"""Typed errors raised by swpc-kit.

Every error derives from :class:`SwpcError`, so a caller can catch them all
at once, or tell apart a transient state (:class:`SourceNotReady`) from a
source that answered with something else (:class:`UnexpectedContent`) and
from a known format with an inconsistent value (:class:`ParseError`).
"""

from datetime import datetime, timedelta


class SwpcError(Exception):
    """Base class for every error raised by swpc-kit.

    Attributes:
        product: Name of the product being fetched, such as
            ``"planetary_k_index"``, when the error went through the client;
            ``None`` from a parser called directly.
        url: The URL being fetched, under the same condition.
    """

    product: str | None = None
    url: str | None = None

    def __str__(self) -> str:
        text = super().__str__()
        if self.product is None or self.url is None:
            return text
        if self.url in text:
            return f"{text} [{self.product}]"
        return f"{text} [{self.product} at {self.url}]"


class SourceNotReady(SwpcError):
    """The data is truncated or empty.

    SWPC sometimes serves a file while rewriting it, so a JSON array may not
    be closed or a text product may stop halfway. This is a transient state,
    not a bug: the caller should try again later.
    """


class UnexpectedContent(SwpcError):
    """The source answered with something other than the expected product.

    For example an HTML page, a redirect to an announcement page, or a format
    that no parser knows.

    Args:
        message: What came instead of the product.
        status: The HTTP status, when the client got one other than ``200``.
        location: The ``Location`` header of a redirect: where the product
            may have moved.
    """

    def __init__(
        self, message: str, *, status: int | None = None, location: str | None = None
    ) -> None:
        self.status = status
        self.location = location
        super().__init__(message)


class ParseError(SwpcError):
    """The format is the expected one, but a value is inconsistent.

    The message names the offending field and where it is, when known.

    Args:
        message: What is wrong with the value.
        field: Name of the offending field or column.
        line: 1-based line number in a text product.
        index: 0-based position of the offending record in a JSON array.

    Raises:
        ValueError: If ``line`` is not positive or ``index`` is negative.
    """

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        line: int | None = None,
        index: int | None = None,
    ) -> None:
        if line is not None and line < 1:
            raise ValueError(f"line is 1-based, got {line}")
        if index is not None and index < 0:
            raise ValueError(f"index must not be negative, got {index}")
        self.field = field
        self.line = line
        self.index = index
        where = []
        if field is not None:
            where.append(f"field {field!r}")
        if line is not None:
            where.append(f"line {line}")
        if index is not None:
            where.append(f"record {index}")
        super().__init__(f"{message} ({', '.join(where)})" if where else message)


class StaleData(SwpcError):
    """The data is older than the maximum age the caller accepts.

    Raised only by the client, and only when the caller passes ``max_age``.
    The age is measured on the time the content declares, never on HTTP
    metadata.

    Args:
        data_time: Most recent time declared by the content, in UTC.
        max_age: Maximum age the caller accepts.
        age: Age of the data when it was checked.

    Raises:
        ValueError: If ``data_time`` is not an aware datetime in UTC.
    """

    def __init__(
        self, *, data_time: datetime, max_age: timedelta, age: timedelta
    ) -> None:
        if data_time.utcoffset() != timedelta(0):
            raise ValueError(f"data_time must be in UTC, got {data_time!r}")
        self.data_time = data_time
        self.max_age = max_age
        self.age = age
        super().__init__(
            f"data from {data_time.isoformat()} is {age} old, "
            f"more than the allowed {max_age}"
        )
