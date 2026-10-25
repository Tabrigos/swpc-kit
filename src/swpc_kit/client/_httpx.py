"""Transports built on httpx2, the only module that knows the HTTP library.

httpx2 is the maintained continuation of httpx (see ``docs/FONTI.md``,
section "HTTP client"). Switching library means rewriting this module only:
the clients depend on the :class:`~swpc_kit.client.Transport` protocol.
"""

from collections.abc import Mapping

try:
    import httpx2
except ImportError as exc:
    raise ImportError(
        "the default transports of swpc_kit.client need httpx2:"
        " pip install 'swpc-kit[client]'"
    ) from exc

from swpc_kit.client._core import HttpResponse
from swpc_kit.errors import SourceNotReady


def _response(response: httpx2.Response) -> HttpResponse:
    return HttpResponse(
        status=response.status_code,
        headers=dict(response.headers),
        content=response.content,
    )


def _not_ready(url: str, exc: httpx2.HTTPError) -> SourceNotReady:
    return SourceNotReady(f"cannot fetch {url}: {type(exc).__name__}: {exc}")


class HttpxTransport:
    """Synchronous transport on an ``httpx2.Client``.

    Redirects are never followed. Timeouts, network failures and any other
    httpx2 error (a body that does not decode, for one) become
    :class:`~swpc_kit.errors.SourceNotReady`.

    Args:
        client: The ``httpx2.Client`` to use; by default a new one, closed by
            :meth:`close`.
    """

    def __init__(self, client: httpx2.Client | None = None) -> None:
        self.client = client if client is not None else httpx2.Client()

    def get(
        self, url: str, *, headers: Mapping[str, str], timeout: float
    ) -> HttpResponse:
        """Send a GET request and return the response, whatever its status."""
        try:
            response = self.client.get(
                url, headers=dict(headers), timeout=timeout, follow_redirects=False
            )
        except httpx2.HTTPError as exc:
            raise _not_ready(url, exc) from exc
        return _response(response)

    def close(self) -> None:
        """Close the underlying ``httpx2.Client``."""
        self.client.close()


class AsyncHttpxTransport:
    """Asynchronous transport on an ``httpx2.AsyncClient``.

    Same behaviour as :class:`HttpxTransport`.

    Args:
        client: The ``httpx2.AsyncClient`` to use; by default a new one,
            closed by :meth:`aclose`.
    """

    def __init__(self, client: httpx2.AsyncClient | None = None) -> None:
        self.client = client if client is not None else httpx2.AsyncClient()

    async def get(
        self, url: str, *, headers: Mapping[str, str], timeout: float
    ) -> HttpResponse:
        """Send a GET request and return the response, whatever its status."""
        try:
            response = await self.client.get(
                url, headers=dict(headers), timeout=timeout, follow_redirects=False
            )
        except httpx2.HTTPError as exc:
            raise _not_ready(url, exc) from exc
        return _response(response)

    async def aclose(self) -> None:
        """Close the underlying ``httpx2.AsyncClient``."""
        await self.client.aclose()
