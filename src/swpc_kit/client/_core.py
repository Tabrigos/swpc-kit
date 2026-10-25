"""Transport-independent core of the clients.

The clients never talk to an HTTP library directly: they hand a URL and
headers to a :class:`Transport` (or :class:`AsyncTransport`) and get back an
:class:`HttpResponse`. Everything else lives here, shared by the sync and the
async client: conditional requests, classification of the source's replies,
parsing, and the ``max_age`` check.
"""

import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from swpc_kit import __version__
from swpc_kit.errors import SourceNotReady, StaleData, SwpcError, UnexpectedContent

DEFAULT_TIMEOUT = 30.0
"""Default timeout, in seconds, for each phase of a request (see ``timeout``)."""

DEFAULT_USER_AGENT = f"swpc-kit/{__version__} (+https://github.com/Tabrigos/swpc-kit)"
"""Default ``User-Agent`` header."""

_TRANSIENT_STATUSES = frozenset({408, 425, 429})

_log = logging.getLogger("swpc_kit.client")


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


def _log_skipped(name: str, url: str, model: object) -> None:
    """Warn about the records a parser skipped (see ``SkippedRecord``)."""
    skipped = getattr(model, "skipped", ())
    if not skipped:
        return
    first = skipped[0]
    where = f"{first.field}: " if first.field else ""
    count = f"{len(skipped)} record{'s' if len(skipped) > 1 else ''} skipped"
    _log.warning(
        "%s from %s: %s; %srecord %d: %s%s",
        name,
        url,
        count,
        "first, " if len(skipped) > 1 else "",
        first.index,
        where,
        first.reason,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _check_arguments(
    *,
    user_agent: object,
    timeout: object,
    max_age: object,
    conditional: object,
    clock: object,
    urls: object,
) -> None:
    """Raise a clear error for an argument of the wrong type or value."""
    if isinstance(timeout, bool) or not isinstance(timeout, int | float):
        raise TypeError(f"timeout must be a number of seconds, got {timeout!r}")
    if not timeout > 0:
        raise ValueError(f"timeout must be positive, got {timeout}")
    if not math.isfinite(timeout):
        raise ValueError(f"timeout must be finite, got {timeout}")
    if max_age is not None:
        if not isinstance(max_age, timedelta):
            raise TypeError(f"max_age must be a timedelta or None, got {max_age!r}")
        if max_age <= timedelta(0):
            raise ValueError(f"max_age must be positive, got {max_age}")
    if not isinstance(user_agent, str):
        raise TypeError(f"user_agent must be a string, got {user_agent!r}")
    if not user_agent.strip():
        raise ValueError("user_agent must not be empty")
    if "\r" in user_agent or "\n" in user_agent:
        raise ValueError(f"user_agent must be one line, got {user_agent!r}")
    if not isinstance(conditional, bool):
        raise TypeError(f"conditional must be True or False, got {conditional!r}")
    if not callable(clock):
        raise TypeError(f"clock must be callable, got {clock!r}")
    if urls is None:
        return
    if not isinstance(urls, Mapping):
        raise TypeError(f"urls must be a mapping of product to URL, got {urls!r}")
    for name, url in urls.items():
        if not isinstance(url, str):
            raise TypeError(f"URL of {name} must be a string, got {url!r}")
        if not url.startswith(("https://", "http://")):
            raise ValueError(
                f"URL of {name} must start with https:// or http://, got {url!r}"
            )


def check_transport(client: str, transport: object, *methods: str) -> None:
    """Raise :class:`TypeError` if ``transport`` lacks one of ``methods``.

    Args:
        client: Name of the client class, for the message.
        transport: The transport given to the client.
        methods: The methods the client needs: ``get`` and ``close`` or
            ``aclose``.
    """
    if all(callable(getattr(transport, method, None)) for method in methods):
        return
    wanted = "a Transport" if client == "Client" else "an AsyncTransport"
    raise TypeError(
        f"{client} needs {wanted} (with {' and '.join(methods)}),"
        f" got {type(transport).__name__}"
    )


class BaseClient:
    """State and logic shared by :class:`Client` and :class:`AsyncClient`.

    Args:
        user_agent: ``User-Agent`` header sent with every request.
        timeout: Timeout in seconds for each phase of a request, handed to
            the transport (see :class:`~swpc_kit.client.Client`).
        max_age: Default maximum age of the data (see :meth:`check_age`);
            ``None`` means no check.
        conditional: Send ``If-None-Match`` / ``If-Modified-Since`` when a
            previous reply for the same URL carried ``ETag`` /
            ``Last-Modified``, and reuse that reply's model on ``304``.
        clock: Returns the current time, as an aware UTC datetime.
        urls: URLs that replace the canonical ones, by product name, for a
            product that SWPC moved before a new version of swpc-kit knows.

    Raises:
        TypeError: If an argument has the wrong type.
        ValueError: If ``timeout`` or ``max_age`` is not positive, the user
            agent is empty or not one line, or ``urls`` names a product that
            does not exist or gives a URL that is not HTTP.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float,
        max_age: timedelta | None,
        conditional: bool,
        clock: Callable[[], datetime],
        urls: Mapping[str, str] | None = None,
    ) -> None:
        from swpc_kit.client._products import PRODUCTS

        _check_arguments(
            user_agent=user_agent,
            timeout=timeout,
            max_age=max_age,
            conditional=conditional,
            clock=clock,
            urls=urls,
        )
        self.urls: dict[str, str] = dict(urls or {})
        unknown = sorted(set(self.urls) - {product.name for product in PRODUCTS})
        if unknown:
            raise ValueError(f"no such product in urls: {', '.join(unknown)}")
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_age = max_age
        self.conditional = conditional
        self._clock = clock
        self._cache: dict[str, _Cached] = {}

    def resolve[M: _Timed](self, product: Product[M]) -> Product[M]:
        """Return ``product`` with the URL that ``urls`` gives it, if any."""
        url = self.urls.get(product.name)
        return product if url is None else replace(product, url=url)

    @staticmethod
    def locate(error: SwpcError, product: Product[Any]) -> None:
        """Record in ``error`` which product and URL it comes from."""
        if error.product is None:
            error.product = product.name
            error.url = product.url

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
        model = self.reuse(product, response)
        if model is None:
            model = product.parse(response.content, product.url)
            self.remember(product, response, model)
        self.check_age(model, max_age)
        return model

    def reuse[M: _Timed](self, product: Product[M], response: HttpResponse) -> M | None:
        """Return the cached model on ``304``, or ``None`` if the body is new.

        The first half of :meth:`handle`: the async client runs it on the
        event loop, then parses the body in a thread.

        Raises:
            SourceNotReady: Temporary failure (``429``, ``5xx``…).
            UnexpectedContent: Redirect, other status, HTML instead of data,
                or ``304`` with no copy.
        """
        url = product.url
        status = response.status
        if status == 304:
            cached = self._cache.get(url)
            if cached is None:
                raise UnexpectedContent(f"304 Not Modified from {url} with no copy")
            model: M = cached.model
            _log.debug("304 Not Modified from %s: reusing %s", url, product.name)
            return model
        if status in _TRANSIENT_STATUSES or 500 <= status <= 599:
            raise SourceNotReady(f"HTTP {status} from {url}; try again later")
        if 300 <= status <= 399:
            location = response.header("Location")
            target = location or "an unknown place"
            raise UnexpectedContent(
                f"HTTP {status} from {url}: moved to {target}",
                status=status,
                location=location,
            )
        if status != 200:
            raise UnexpectedContent(f"HTTP {status} from {url}", status=status)
        content_type = response.header("Content-Type") or ""
        if "html" in content_type.lower():
            raise UnexpectedContent(f"got HTML ({content_type}) from {url}")
        return None

    def remember(
        self, product: Product[Any], response: HttpResponse, model: object
    ) -> None:
        """Log the skipped records of a new model and keep it for ``304``."""
        url = product.url
        _log_skipped(product.name, url, model)
        etag = response.header("ETag")
        last_modified = response.header("Last-Modified")
        if etag is not None or last_modified is not None:
            self._cache[url] = _Cached(etag, last_modified, model)
        else:
            self._cache.pop(url, None)

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
