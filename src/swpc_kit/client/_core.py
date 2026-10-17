"""Transport-independent core of the clients.

The clients never talk to an HTTP library directly: they hand a URL and
headers to a :class:`Transport` (or :class:`AsyncTransport`) and get back an
:class:`HttpResponse`. Everything else lives here, shared by the sync and the
async client: conditional requests, classification of the source's replies,
parsing, and the ``max_age`` check.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from swpc_kit import __version__
from swpc_kit.errors import SourceNotReady, StaleData, UnexpectedContent

DEFAULT_TIMEOUT = 30.0
"""Default timeout for one request, in seconds."""

DEFAULT_USER_AGENT = f"swpc-kit/{__version__} (+https://github.com/Tabrigos/swpc-kit)"
"""Default ``User-Agent`` header."""

_TRANSIENT_STATUSES = frozenset({408, 425, 429})


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """What a transport returns for one request.

    Attributes:
        status: HTTP status code.
        headers: Response headers; names are matched case-insensitively.
        content: The body, as received (not decoded).
    """

    status: int
    headers: Mapping[str, str]
    content: bytes

    def header(self, name: str) -> str | None:
        """Return the header ``name`` (any case), or ``None``."""
        wanted = name.lower()
        for key, value in self.headers.items():
            if key.lower() == wanted:
                return value
        return None


class Transport(Protocol):
    """Fetches a URL synchronously.

    A transport must not follow redirects, and must raise
    :class:`~swpc_kit.errors.SourceNotReady` when the source cannot be
    reached (timeout, refused connection, connection cut).
    """

    def get(
        self, url: str, *, headers: Mapping[str, str], timeout: float
    ) -> HttpResponse:
        """Send a GET request and return the response, whatever its status."""
        ...

    def close(self) -> None:
        """Release the transport's resources."""
        ...


class AsyncTransport(Protocol):
    """Fetches a URL asynchronously; same contract as :class:`Transport`."""

    async def get(
        self, url: str, *, headers: Mapping[str, str], timeout: float
    ) -> HttpResponse:
        """Send a GET request and return the response, whatever its status."""
        ...

    async def aclose(self) -> None:
        """Release the transport's resources."""
        ...


class _Timed(Protocol):
    @property
    def data_time(self) -> datetime | None: ...


@dataclass(frozen=True, slots=True)
class Product[M: _Timed]:
    """A SWPC product the clients know how to fetch.

    Attributes:
        name: Name of the client method that fetches it.
        url: Canonical URL.
        parse: Parser, called with the body and the URL it came from.
    """

    name: str
    url: str
    parse: Callable[[bytes, str], M]


@dataclass(frozen=True, slots=True)
class _Cached:
    etag: str | None
    last_modified: str | None
    model: Any


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BaseClient:
    """State and logic shared by :class:`Client` and :class:`AsyncClient`.

    Args:
        user_agent: ``User-Agent`` header sent with every request.
        timeout: Timeout for one request, in seconds.
        max_age: Default maximum age of the data (see :meth:`check_age`);
            ``None`` means no check.
        conditional: Send ``If-None-Match`` / ``If-Modified-Since`` when a
            previous reply for the same URL carried ``ETag`` /
            ``Last-Modified``, and reuse that reply's model on ``304``.
        clock: Returns the current time, as an aware UTC datetime.

    Raises:
        ValueError: If ``timeout`` is not positive.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float,
        max_age: timedelta | None,
        conditional: bool,
        clock: Callable[[], datetime],
    ) -> None:
        if timeout <= 0:
            raise ValueError(f"timeout must be positive, got {timeout}")
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_age = max_age
        self.conditional = conditional
        self._clock = clock
        self._cache: dict[str, _Cached] = {}

    def request_headers(self, product: Product[Any]) -> dict[str, str]:
        """Return the headers for a request of ``product``."""
        headers = {"User-Agent": self.user_agent}
        cached = self._cache.get(product.url) if self.conditional else None
        if cached is not None:
            if cached.etag is not None:
                headers["If-None-Match"] = cached.etag
            if cached.last_modified is not None:
                headers["If-Modified-Since"] = cached.last_modified
        return headers

    def handle[M: _Timed](
        self,
        product: Product[M],
        response: HttpResponse,
        max_age: timedelta | None,
    ) -> M:
        """Turn a response into a model, or raise the matching error.

        Args:
            product: The product requested.
            response: What the transport returned.
            max_age: Maximum age for this call; ``None`` uses the client's.

        Returns:
            The parsed model, or the cached one on ``304 Not Modified``.

        Raises:
            SourceNotReady: Temporary failure (``429``, ``5xx``…) or
                truncated content.
            UnexpectedContent: Redirect, other status, HTML instead of data,
                or content no parser knows.
            ParseError: Known format with an inconsistent value.
            StaleData: The data is older than the maximum age.
        """
        url = product.url
        status = response.status
        if status == 304:
            cached = self._cache.get(url)
            if cached is None:
                raise UnexpectedContent(f"304 Not Modified from {url} with no copy")
            model: M = cached.model
        else:
            if status in _TRANSIENT_STATUSES or 500 <= status <= 599:
                raise SourceNotReady(f"HTTP {status} from {url}; try again later")
            if 300 <= status <= 399:
                target = response.header("Location") or "an unknown place"
                raise UnexpectedContent(f"HTTP {status} from {url}: moved to {target}")
            if status != 200:
                raise UnexpectedContent(f"HTTP {status} from {url}")
            content_type = response.header("Content-Type") or ""
            if "html" in content_type.lower():
                raise UnexpectedContent(f"got HTML ({content_type}) from {url}")
            model = product.parse(response.content, url)
            etag = response.header("ETag")
            last_modified = response.header("Last-Modified")
            if etag is not None or last_modified is not None:
                self._cache[url] = _Cached(etag, last_modified, model)
            else:
                self._cache.pop(url, None)
        self.check_age(model, max_age)
        return model

    def check_age(self, model: _Timed, max_age: timedelta | None) -> None:
        """Raise :class:`StaleData` if ``model`` is older than allowed.

        The age is measured on ``model.data_time``, the time the content
        declares, never on HTTP metadata. A model with no ``data_time`` (an
        empty list of alerts) cannot be stale.

        Args:
            model: The model to check.
            max_age: Maximum age; ``None`` uses the client's default.

        Raises:
            StaleData: If the data is too old.
            ValueError: If the clock does not return a UTC datetime.
        """
        limit = max_age if max_age is not None else self.max_age
        if limit is None:
            return
        data_time = model.data_time
        if data_time is None:
            return
        now = self._clock()
        if now.utcoffset() != timedelta(0):
            raise ValueError(f"clock must return an aware datetime in UTC, got {now!r}")
        age = now - data_time
        if age > limit:
            raise StaleData(data_time=data_time, max_age=limit, age=age)
