"""HTTP client for SWPC products (``client`` extra).

:class:`Client` and :class:`AsyncClient` have one method per product. Each
downloads the product, recognises the errors of the source, hands the content
to the matching parser and, if asked, checks that the data is recent enough::

    from datetime import timedelta
    from swpc_kit.client import Client

    with Client() as client:
        kp = client.planetary_k_index(max_age=timedelta(hours=6))

Errors (all :class:`~swpc_kit.errors.SwpcError`):

- :class:`~swpc_kit.errors.SourceNotReady`: timeout, network failure,
  ``408``/``425``/``429``/``5xx``, or truncated content; try again later;
- :class:`~swpc_kit.errors.UnexpectedContent`: redirect (never followed),
  other status, HTML, or content no parser knows;
- :class:`~swpc_kit.errors.ParseError`: known format, inconsistent value;
- :class:`~swpc_kit.errors.StaleData`: the content declares a time older
  than ``max_age``.

Requests are conditional: once a URL answered with ``ETag`` or
``Last-Modified``, the next request sends them back, and a ``304 Not
Modified`` reuses the previous model (``max_age`` is still checked).

If SWPC moves a product before a new version of swpc-kit knows the new
address, ``urls`` points the client there::

    Client(urls={"kyoto_dst": "https://services.swpc.noaa.gov/new/dst.json"})

Every error that goes through the client says which product and URL it comes
from (``product`` and ``url`` attributes, and in the message).

The HTTP library (httpx2) is used only by the default transports
(:class:`HttpxTransport`, :class:`AsyncHttpxTransport`) and imported only
when one is needed; any object with the :class:`Transport` or
:class:`AsyncTransport` interface can replace them.
"""

import asyncio
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

from swpc_kit.client import _products as p
from swpc_kit.client._core import (
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    AsyncTransport,
    BaseClient,
    HttpResponse,
    Product,
    Transport,
    _Timed,
    _utc_now,
    check_transport,
)
from swpc_kit.client._products import PRODUCTS
from swpc_kit.errors import SwpcError
from swpc_kit.models.alerts import (
    Alerts,
)
from swpc_kit.models.bulletins import (
    GeomagneticForecast,
    ThreeDayForecast,
    TwentySevenDayOutlook,
)
from swpc_kit.models.goes import (
    GoesIntegralProtons,
    GoesXrays,
)
from swpc_kit.models.grids import (
    DrapFrequencies,
    OvationAurora,
)
from swpc_kit.models.indices import (
    F107Flux,
    KyotoDst,
    NoaaScales,
    PlanetaryKIndex,
    PlanetaryKIndex1m,
    PlanetaryKIndexForecast,
)
from swpc_kit.models.solar_wind import (
    RtswMag1m,
    RtswWind1m,
)

if TYPE_CHECKING:
    from swpc_kit.client._httpx import AsyncHttpxTransport, HttpxTransport

__all__ = [
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
    "PRODUCTS",
    "AsyncClient",
    "AsyncHttpxTransport",
    "AsyncTransport",
    "Client",
    "HttpResponse",
    "HttpxTransport",
    "Product",
    "Transport",
]


def __getattr__(name: str) -> Any:
    # The httpx2 transports load on first use: a custom transport needs no
    # httpx2, and without the extra the import error says what to install.
    if name in ("HttpxTransport", "AsyncHttpxTransport"):
        from swpc_kit.client import _httpx

        return getattr(_httpx, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class Client(BaseClient):
    """Synchronous client for SWPC products.

    Use it with ``with`` or call :meth:`close`.

    Args:
        transport: How requests are sent; by default an
            :class:`HttpxTransport` (closed with the client).
        user_agent: ``User-Agent`` header sent with every request.
        timeout: Timeout in seconds for each phase of a request: connecting,
            sending, waiting for a free connection, and each wait for the
            next piece of the reply, as httpx2 applies it. It does not
            bound the whole request: a server that keeps sending slowly can
            make one last longer.
        max_age: Default maximum age of the data; ``None`` means no check.
            Each method also takes ``max_age``, which wins over this one.
        conditional: Use ``ETag``/``Last-Modified`` conditional requests.
        clock: Returns the current time as an aware UTC datetime (for
            ``max_age``).
        urls: URLs that replace the canonical ones, by method name, for a
            product that SWPC moved: ``{"kyoto_dst": "https://..."}``.

    Raises:
        TypeError: If an argument has the wrong type, or ``transport`` lacks
            the methods it needs.
        ValueError: If ``timeout`` or ``max_age`` is not positive, the user
            agent is empty or not one line, or ``urls`` names a method that
            does not exist or gives a URL that is not HTTP.
        ImportError: If no ``transport`` is given and httpx2 (the
            ``client`` extra) is not installed.
    """

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        max_age: timedelta | None = None,
        conditional: bool = True,
        clock: Callable[[], datetime] = _utc_now,
        urls: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(
            user_agent=user_agent,
            timeout=timeout,
            max_age=max_age,
            conditional=conditional,
            clock=clock,
            urls=urls,
        )
        if transport is None:
            from swpc_kit.client._httpx import HttpxTransport

            transport = HttpxTransport()
        check_transport("Client", transport, "get", "close")
        self.transport: Transport = transport

    def fetch[M: _Timed](
        self, product: Product[M], *, max_age: timedelta | None = None
    ) -> M:
        """Fetch and parse ``product`` (one of :data:`PRODUCTS`).

        Args:
            product: What to fetch.
            max_age: Maximum age of the data; ``None`` uses the client's.

        Returns:
            The parsed model.
        """
        product = self.resolve(product)
        try:
            response = self.transport.get(
                product.url,
                headers=self.request_headers(product),
                timeout=self.timeout,
            )
            return self.handle(product, response, max_age)
        except SwpcError as error:
            self.locate(error, product)
            raise

    def close(self) -> None:
        """Close the transport."""
        self.transport.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def planetary_k_index(self, *, max_age: timedelta | None = None) -> PlanetaryKIndex:
        """Fetch the 3-hour planetary K index of the last days."""
        return self.fetch(p.PLANETARY_K_INDEX, max_age=max_age)

    def planetary_k_index_forecast(
        self, *, max_age: timedelta | None = None
    ) -> PlanetaryKIndexForecast:
        """Fetch the observed and forecast 3-hour Kp."""
        return self.fetch(p.PLANETARY_K_INDEX_FORECAST, max_age=max_age)

    def planetary_k_index_1m(
        self, *, max_age: timedelta | None = None
    ) -> PlanetaryKIndex1m:
        """Fetch the 1-minute Kp estimates."""
        return self.fetch(p.PLANETARY_K_INDEX_1M, max_age=max_age)

    def kyoto_dst(self, *, max_age: timedelta | None = None) -> KyotoDst:
        """Fetch the hourly Kyoto Dst of the last week."""
        return self.fetch(p.KYOTO_DST, max_age=max_age)

    def f107_flux_30_day(self, *, max_age: timedelta | None = None) -> F107Flux:
        """Fetch the daily F10.7 of the last 30 days."""
        return self.fetch(p.F107_FLUX_30_DAY, max_age=max_age)

    def noaa_scales(self, *, max_age: timedelta | None = None) -> NoaaScales:
        """Fetch the NOAA space weather scales."""
        return self.fetch(p.NOAA_SCALES, max_age=max_age)

    def rtsw_mag_1m(self, *, max_age: timedelta | None = None) -> RtswMag1m:
        """Fetch the real-time solar wind magnetic field."""
        return self.fetch(p.RTSW_MAG_1M, max_age=max_age)

    def rtsw_wind_1m(self, *, max_age: timedelta | None = None) -> RtswWind1m:
        """Fetch the real-time solar wind plasma."""
        return self.fetch(p.RTSW_WIND_1M, max_age=max_age)

    def goes_xrays(self, *, max_age: timedelta | None = None) -> GoesXrays:
        """Fetch the GOES X-ray flux of the last day (primary satellite)."""
        return self.fetch(p.GOES_XRAYS, max_age=max_age)

    def goes_integral_protons(
        self, *, max_age: timedelta | None = None
    ) -> GoesIntegralProtons:
        """Fetch the GOES integral proton flux of the last day (primary satellite)."""
        return self.fetch(p.GOES_INTEGRAL_PROTONS, max_age=max_age)

    def alerts(self, *, max_age: timedelta | None = None) -> Alerts:
        """Fetch the alerts, warnings, watches and summaries."""
        return self.fetch(p.ALERTS, max_age=max_age)

    def three_day_forecast(
        self, *, max_age: timedelta | None = None
    ) -> ThreeDayForecast:
        """Fetch the 3-day forecast."""
        return self.fetch(p.THREE_DAY_FORECAST, max_age=max_age)

    def geomagnetic_forecast(
        self, *, max_age: timedelta | None = None
    ) -> GeomagneticForecast:
        """Fetch the 3-day geomagnetic forecast."""
        return self.fetch(p.GEOMAGNETIC_FORECAST, max_age=max_age)

    def twenty_seven_day_outlook(
        self, *, max_age: timedelta | None = None
    ) -> TwentySevenDayOutlook:
        """Fetch the 27-day outlook."""
        return self.fetch(p.TWENTY_SEVEN_DAY_OUTLOOK, max_age=max_age)

    def ovation_aurora(self, *, max_age: timedelta | None = None) -> OvationAurora:
        """Fetch the OVATION aurora forecast grid."""
        return self.fetch(p.OVATION_AURORA, max_age=max_age)

    def drap_global_frequencies(
        self, *, max_age: timedelta | None = None
    ) -> DrapFrequencies:
        """Fetch the D-RAP global frequency grid."""
        return self.fetch(p.DRAP_GLOBAL_FREQUENCIES, max_age=max_age)


class AsyncClient(BaseClient):
    """Asynchronous client for SWPC products.

    Use it with ``async with`` or call :meth:`aclose`. The content is parsed
    in a thread (:func:`asyncio.to_thread`), so a large file such as the
    OVATION grid does not block the event loop. For a limit on the whole
    call, wrap it in :func:`asyncio.timeout`.

    Args:
        transport: How requests are sent; by default an
            :class:`AsyncHttpxTransport` (closed with the client).
        user_agent: ``User-Agent`` header sent with every request.
        timeout: Timeout in seconds for each phase of a request: connecting,
            sending, waiting for a free connection, and each wait for the
            next piece of the reply, as httpx2 applies it. It does not
            bound the whole request: a server that keeps sending slowly can
            make one last longer.
        max_age: Default maximum age of the data; ``None`` means no check.
            Each method also takes ``max_age``, which wins over this one.
        conditional: Use ``ETag``/``Last-Modified`` conditional requests.
        clock: Returns the current time as an aware UTC datetime (for
            ``max_age``).
        urls: URLs that replace the canonical ones, by method name, for a
            product that SWPC moved: ``{"kyoto_dst": "https://..."}``.

    Raises:
        TypeError: If an argument has the wrong type, or ``transport`` lacks
            the methods it needs.
        ValueError: If ``timeout`` or ``max_age`` is not positive, the user
            agent is empty or not one line, or ``urls`` names a method that
            does not exist or gives a URL that is not HTTP.
        ImportError: If no ``transport`` is given and httpx2 (the
            ``client`` extra) is not installed.
    """

    def __init__(
        self,
        *,
        transport: AsyncTransport | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        max_age: timedelta | None = None,
        conditional: bool = True,
        clock: Callable[[], datetime] = _utc_now,
        urls: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(
            user_agent=user_agent,
            timeout=timeout,
            max_age=max_age,
            conditional=conditional,
            clock=clock,
            urls=urls,
        )
        if transport is None:
            from swpc_kit.client._httpx import AsyncHttpxTransport

            transport = AsyncHttpxTransport()
        check_transport("AsyncClient", transport, "get", "aclose")
        self.transport: AsyncTransport = transport

    async def fetch[M: _Timed](
        self, product: Product[M], *, max_age: timedelta | None = None
    ) -> M:
        """Fetch and parse ``product`` (one of :data:`PRODUCTS`).

        Args:
            product: What to fetch.
            max_age: Maximum age of the data; ``None`` uses the client's.

        Returns:
            The parsed model.
        """
        product = self.resolve(product)
        try:
            response = await self.transport.get(
                product.url,
                headers=self.request_headers(product),
                timeout=self.timeout,
            )
            model = self.reuse(product, response)
            if model is None:
                model = await asyncio.to_thread(
                    product.parse, response.content, product.url
                )
                self.remember(product, response, model)
            self.check_age(model, max_age)
            return model
        except SwpcError as error:
            self.locate(error, product)
            raise

    async def aclose(self) -> None:
        """Close the transport."""
        await self.transport.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def planetary_k_index(
        self, *, max_age: timedelta | None = None
    ) -> PlanetaryKIndex:
        """Fetch the 3-hour planetary K index of the last days."""
        return await self.fetch(p.PLANETARY_K_INDEX, max_age=max_age)

    async def planetary_k_index_forecast(
        self, *, max_age: timedelta | None = None
    ) -> PlanetaryKIndexForecast:
        """Fetch the observed and forecast 3-hour Kp."""
        return await self.fetch(p.PLANETARY_K_INDEX_FORECAST, max_age=max_age)

    async def planetary_k_index_1m(
        self, *, max_age: timedelta | None = None
    ) -> PlanetaryKIndex1m:
        """Fetch the 1-minute Kp estimates."""
        return await self.fetch(p.PLANETARY_K_INDEX_1M, max_age=max_age)

    async def kyoto_dst(self, *, max_age: timedelta | None = None) -> KyotoDst:
        """Fetch the hourly Kyoto Dst of the last week."""
        return await self.fetch(p.KYOTO_DST, max_age=max_age)

    async def f107_flux_30_day(self, *, max_age: timedelta | None = None) -> F107Flux:
        """Fetch the daily F10.7 of the last 30 days."""
        return await self.fetch(p.F107_FLUX_30_DAY, max_age=max_age)

    async def noaa_scales(self, *, max_age: timedelta | None = None) -> NoaaScales:
        """Fetch the NOAA space weather scales."""
        return await self.fetch(p.NOAA_SCALES, max_age=max_age)

    async def rtsw_mag_1m(self, *, max_age: timedelta | None = None) -> RtswMag1m:
        """Fetch the real-time solar wind magnetic field."""
        return await self.fetch(p.RTSW_MAG_1M, max_age=max_age)

    async def rtsw_wind_1m(self, *, max_age: timedelta | None = None) -> RtswWind1m:
        """Fetch the real-time solar wind plasma."""
        return await self.fetch(p.RTSW_WIND_1M, max_age=max_age)

    async def goes_xrays(self, *, max_age: timedelta | None = None) -> GoesXrays:
        """Fetch the GOES X-ray flux of the last day (primary satellite)."""
        return await self.fetch(p.GOES_XRAYS, max_age=max_age)

    async def goes_integral_protons(
        self, *, max_age: timedelta | None = None
    ) -> GoesIntegralProtons:
        """Fetch the GOES integral proton flux of the last day (primary satellite)."""
        return await self.fetch(p.GOES_INTEGRAL_PROTONS, max_age=max_age)

    async def alerts(self, *, max_age: timedelta | None = None) -> Alerts:
        """Fetch the alerts, warnings, watches and summaries."""
        return await self.fetch(p.ALERTS, max_age=max_age)

    async def three_day_forecast(
        self, *, max_age: timedelta | None = None
    ) -> ThreeDayForecast:
        """Fetch the 3-day forecast."""
        return await self.fetch(p.THREE_DAY_FORECAST, max_age=max_age)

    async def geomagnetic_forecast(
        self, *, max_age: timedelta | None = None
    ) -> GeomagneticForecast:
        """Fetch the 3-day geomagnetic forecast."""
        return await self.fetch(p.GEOMAGNETIC_FORECAST, max_age=max_age)

    async def twenty_seven_day_outlook(
        self, *, max_age: timedelta | None = None
    ) -> TwentySevenDayOutlook:
        """Fetch the 27-day outlook."""
        return await self.fetch(p.TWENTY_SEVEN_DAY_OUTLOOK, max_age=max_age)

    async def ovation_aurora(
        self, *, max_age: timedelta | None = None
    ) -> OvationAurora:
        """Fetch the OVATION aurora forecast grid."""
        return await self.fetch(p.OVATION_AURORA, max_age=max_age)

    async def drap_global_frequencies(
        self, *, max_age: timedelta | None = None
    ) -> DrapFrequencies:
        """Fetch the D-RAP global frequency grid."""
        return await self.fetch(p.DRAP_GLOBAL_FREQUENCIES, max_age=max_age)
