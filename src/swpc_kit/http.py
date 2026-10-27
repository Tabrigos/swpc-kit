"""The rules for reading SWPC's HTTP answers, with no network (D-006, D-024).

The client applies them to every response. A program that downloads with its
own code (any HTTP library, a scheduler, a rate limiter) applies them before
handing the body to a parser::

    check_response(status, headers, url=url)
    kp = parse_planetary_k_index(body)

This module knows nothing of HTTP libraries, of caches or of retries: it
reads a status and the headers, and says whose fault a bad answer is.
Standard library only.
"""

from collections.abc import Mapping

from swpc_kit.errors import RateLimited, SourceNotReady, UnexpectedContent

__all__ = ["check_response"]

_TRANSIENT_STATUSES = frozenset({408, 425})


def _header(headers: Mapping[str, str], name: str) -> str | None:
    """Return the header ``name`` (any case), or ``None``."""
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return None


def check_response(status: int, headers: Mapping[str, str], *, url: str) -> None:
    """Check that an answer from SWPC holds a product, before parsing it.

    Returns only for a ``200`` that is not an HTML page: the body can go to
    the parser, which still raises :class:`SourceNotReady` for a file caught
    while SWPC rewrites it.

    Args:
        status: The HTTP status.
        headers: The response headers, matched in any case.
        url: The URL requested, for the error messages.

    Raises:
        RateLimited: ``429``: a refusal; slow down, do not retry in this run.
        SourceNotReady: ``408``, ``425`` or ``5xx``: try again later.
        UnexpectedContent: A redirect (``status`` and ``location`` say
            where), any other status, or an HTML page: the product moved or
            changed, or the URL is wrong.
        ValueError: ``304``: only the caller holds the copy it refers to.
    """
    if status == 304:
        raise ValueError(f"304 Not Modified from {url}: reuse the copy you hold")
    if status == 429:
        raise RateLimited(
            f"HTTP 429 from {url}: SWPC asks to slow down",
            retry_after=_header(headers, "Retry-After"),
        )
    if status in _TRANSIENT_STATUSES or 500 <= status <= 599:
        raise SourceNotReady(f"HTTP {status} from {url}; try again later")
    if 300 <= status <= 399:
        location = _header(headers, "Location")
        target = location or "an unknown place"
        raise UnexpectedContent(
            f"HTTP {status} from {url}: moved to {target}",
            status=status,
            location=location,
        )
    if status != 200:
        raise UnexpectedContent(f"HTTP {status} from {url}", status=status)
    content_type = _header(headers, "Content-Type") or ""
    if "html" in content_type.lower():
        raise UnexpectedContent(f"got HTML ({content_type}) from {url}")
