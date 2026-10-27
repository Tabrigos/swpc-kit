import asyncio
import dataclasses
import importlib
import json
import logging
import re
import sys
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest

from swpc_kit.client import (
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    AsyncClient,
    AsyncHttpxTransport,
    Client,
    HttpResponse,
    HttpxTransport,
)
from swpc_kit.client._products import PLANETARY_K_INDEX
from swpc_kit.errors import (
    ParseError,
    RateLimited,
    SourceNotReady,
    StaleData,
    SwpcError,
    UnexpectedContent,
)
from swpc_kit.parse import (
    parse_27_day_outlook,
    parse_alerts,
    parse_drap_global_frequencies,
    parse_f107_flux_30_day,
    parse_geomagnetic_forecast,
    parse_goes_integral_protons,
    parse_goes_xrays,
    parse_kyoto_dst,
    parse_noaa_scales,
    parse_planetary_k_index,
    parse_planetary_k_index_1m,
    parse_planetary_k_index_forecast,
    parse_rtsw_mag_1m,
    parse_rtsw_wind_1m,
    parse_three_day_forecast,
)

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://services.swpc.noaa.gov"
KP_URL = f"{BASE}/products/noaa-planetary-k-index.json"
KP_FIXTURE = "kp-3h/2026-10-15.json"
# Last Kp interval in the fixture starts at 2026-10-15 12:00 UTC.
KP_DATA_TIME = datetime(2026, 10, 15, 12, tzinfo=UTC)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def full_ovation() -> bytes:
    coordinates = [[lon, lat, 0] for lon in range(360) for lat in range(-90, 91)]
    return json.dumps(
        {
            "Observation Time": "2026-10-15T17:39:00Z",
            "Forecast Time": "2026-10-15T18:37:00Z",
            "Data Format": "[Longitude, Latitude, Aurora]",
            "coordinates": coordinates,
        }
    ).encode()


def ok(body: bytes, **headers: str) -> HttpResponse:
    return HttpResponse(status=200, headers=headers, content=body)


@dataclass
class Call:
    url: str
    headers: dict[str, str]
    timeout: float


@dataclass
class FakeTransport:
    """Returns queued responses (or raises queued errors) and records calls."""

    responses: list[HttpResponse | Exception] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    closed: bool = False

    def get(
        self, url: str, *, headers: Mapping[str, str], timeout: float
    ) -> HttpResponse:
        self.calls.append(Call(url, dict(headers), timeout))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        self.closed = True


@dataclass
class AsyncFakeTransport:
    sync: FakeTransport = field(default_factory=FakeTransport)

    async def get(
        self, url: str, *, headers: Mapping[str, str], timeout: float
    ) -> HttpResponse:
        return self.sync.get(url, headers=headers, timeout=timeout)

    async def aclose(self) -> None:
        self.sync.closed = True


def at(when: datetime) -> Callable[[], datetime]:
    return lambda: when


# --- one method per product -------------------------------------------------

PRODUCTS: list[tuple[str, str, Callable[[], bytes], Callable[..., Any] | None]] = [
    ("planetary_k_index", KP_URL, lambda: fixture(KP_FIXTURE), parse_planetary_k_index),
    (
        "planetary_k_index_forecast",
        f"{BASE}/products/noaa-planetary-k-index-forecast.json",
        lambda: fixture("kp-forecast/2026-10-15.json"),
        parse_planetary_k_index_forecast,
    ),
    (
        "planetary_k_index_1m",
        f"{BASE}/json/planetary_k_index_1m.json",
        lambda: fixture("kp-1m/2026-10-15.json"),
        parse_planetary_k_index_1m,
    ),
    (
        "kyoto_dst",
        f"{BASE}/products/kyoto-dst.json",
        lambda: fixture("dst/2026-10-15.json"),
        parse_kyoto_dst,
    ),
    (
        "f107_flux_30_day",
        f"{BASE}/products/10cm-flux-30-day.json",
        lambda: fixture("f107-30-day/2026-10-15.json"),
        parse_f107_flux_30_day,
    ),
    (
        "noaa_scales",
        f"{BASE}/products/noaa-scales.json",
        lambda: fixture("noaa-scales/2026-10-15.json"),
        parse_noaa_scales,
    ),
    (
        "rtsw_mag_1m",
        f"{BASE}/json/rtsw/rtsw_mag_1m.json",
        lambda: fixture("rtsw-mag-1m/2026-10-15.json"),
        parse_rtsw_mag_1m,
    ),
    (
        "rtsw_wind_1m",
        f"{BASE}/json/rtsw/rtsw_wind_1m.json",
        lambda: fixture("rtsw-wind-1m/2026-10-15.json"),
        parse_rtsw_wind_1m,
    ),
    (
        "goes_xrays",
        f"{BASE}/json/goes/primary/xrays-1-day.json",
        lambda: fixture("goes-xrays-1-day/2026-10-15.json"),
        parse_goes_xrays,
    ),
    (
        "goes_integral_protons",
        f"{BASE}/json/goes/primary/integral-protons-1-day.json",
        lambda: fixture("goes-protons-1-day/2026-10-15.json"),
        parse_goes_integral_protons,
    ),
    (
        "alerts",
        f"{BASE}/products/alerts.json",
        lambda: fixture("alerts/2026-10-15.json"),
        parse_alerts,
    ),
    (
        "three_day_forecast",
        f"{BASE}/text/3-day-forecast.txt",
        lambda: fixture("3-day-forecast/2026-10-15.txt"),
        parse_three_day_forecast,
    ),
    (
        "geomagnetic_forecast",
        f"{BASE}/text/3-day-geomag-forecast.txt",
        lambda: fixture("geomag-forecast/2026-10-15.txt"),
        parse_geomagnetic_forecast,
    ),
    (
        "twenty_seven_day_outlook",
        f"{BASE}/text/27-day-outlook.txt",
        lambda: fixture("27-day-outlook/2026-10-15.txt"),
        parse_27_day_outlook,
    ),
    (
        "ovation_aurora",
        f"{BASE}/json/ovation_aurora_latest.json",
        full_ovation,
        None,  # checked separately: the recorded fixture is a reduced grid
    ),
    (
        "drap_global_frequencies",
        f"{BASE}/text/drap_global_frequencies.txt",
        lambda: fixture("drap/2026-10-15.txt"),
        parse_drap_global_frequencies,
    ),
]


@pytest.mark.parametrize(
    ("method", "url", "body", "parser"), PRODUCTS, ids=[p[0] for p in PRODUCTS]
)
def test_each_product_method_fetches_its_url_and_parses(
    method: str, url: str, body: Callable[[], bytes], parser: Callable[..., Any] | None
) -> None:
    raw = body()
    transport = FakeTransport([ok(raw)])
    client = Client(transport=transport)
    model = getattr(client, method)()
    assert [c.url for c in transport.calls] == [url]
    assert model.source_url == url
    if parser is not None:
        assert model == parser(raw, source_url=url)


def test_ovation_through_the_client_is_a_full_grid() -> None:
    client = Client(transport=FakeTransport([ok(full_ovation())]))
    oval = client.ovation_aurora()
    assert oval.grid.shape == (181, 360)


def test_every_parser_has_a_client_method() -> None:
    import swpc_kit.parse as parse

    methods = {p[0] for p in PRODUCTS}
    assert len(methods) == len(parse.__all__)
    for name in methods:
        assert callable(getattr(Client, name))
        assert callable(getattr(AsyncClient, name))


# --- request headers, timeout, user agent -----------------------------------


def test_default_user_agent_and_timeout() -> None:
    transport = FakeTransport([ok(fixture(KP_FIXTURE))])
    Client(transport=transport).planetary_k_index()
    (call,) = transport.calls
    assert call.headers["User-Agent"] == DEFAULT_USER_AGENT
    assert DEFAULT_USER_AGENT.startswith("swpc-kit/")
    assert call.timeout == DEFAULT_TIMEOUT
    assert "If-None-Match" not in call.headers


def test_user_agent_and_timeout_are_configurable() -> None:
    transport = FakeTransport([ok(fixture(KP_FIXTURE))])
    client = Client(transport=transport, user_agent="my-app/1.0", timeout=3.5)
    client.planetary_k_index()
    (call,) = transport.calls
    assert call.headers["User-Agent"] == "my-app/1.0"
    assert call.timeout == 3.5


@pytest.mark.parametrize("timeout", [0, -1])
def test_timeout_must_be_positive(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        Client(transport=FakeTransport(), timeout=timeout)


@pytest.mark.parametrize(
    ("arguments", "error", "message"),
    [
        ({"timeout": "30"}, TypeError, "timeout must be a number of seconds, got '30'"),
        ({"timeout": True}, TypeError, "timeout must be a number of seconds"),
        ({"timeout": None}, TypeError, "timeout must be a number of seconds"),
        ({"timeout": float("nan")}, ValueError, "timeout must be positive"),
        ({"timeout": float("inf")}, ValueError, "timeout must be finite"),
        ({"max_age": 3600}, TypeError, "max_age must be a timedelta or None"),
        ({"max_age": timedelta(0)}, ValueError, "max_age must be positive"),
        ({"max_age": timedelta(hours=-1)}, ValueError, "max_age must be positive"),
        ({"user_agent": None}, TypeError, "user_agent must be a string"),
        ({"user_agent": ""}, ValueError, "user_agent must not be empty"),
        ({"user_agent": "app\r\nX-Evil: 1"}, ValueError, "user_agent must be one line"),
        ({"conditional": "no"}, TypeError, "conditional must be True or False"),
        ({"clock": "now"}, TypeError, "clock must be callable"),
        ({"urls": ["kyoto_dst"]}, TypeError, "urls must be a mapping"),
        ({"urls": {"kyoto_dst": 3}}, TypeError, "URL of kyoto_dst must be a string"),
        (
            {"urls": {"kyoto_dst": "services.swpc.noaa.gov/products/kyoto-dst.json"}},
            ValueError,
            "URL of kyoto_dst must start with https:// or http://",
        ),
    ],
)
@pytest.mark.parametrize("kind", ["sync", "async"])
def test_wrong_arguments_say_what_is_wrong(
    arguments: dict[str, Any], error: type[Exception], message: str, kind: str
) -> None:
    def build() -> object:
        if kind == "sync":
            return Client(transport=FakeTransport(), **arguments)
        return AsyncClient(transport=AsyncFakeTransport(), **arguments)

    with pytest.raises(error, match=re.escape(message)):
        build()


def test_a_transport_of_the_wrong_kind_is_named() -> None:
    with pytest.raises(TypeError, match="AsyncClient needs an AsyncTransport"):
        AsyncClient(transport=FakeTransport())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Client needs a Transport"):
        Client(transport=AsyncFakeTransport())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="got str"):
        Client(transport="https://services.swpc.noaa.gov")  # type: ignore[arg-type]


def test_timeout_is_documented_per_phase() -> None:
    for documented in (Client, AsyncClient):
        assert "each phase" in " ".join((documented.__doc__ or "").split())


# --- conditional requests ---------------------------------------------------


def test_etag_is_sent_back_and_304_reuses_the_model() -> None:
    raw = fixture(KP_FIXTURE)
    transport = FakeTransport(
        [
            ok(raw, ETag='"abc"', **{"Last-Modified": "Thu, 15 Oct 2026 17:51:18 GMT"}),
            HttpResponse(status=304, headers={}, content=b""),
        ]
    )
    client = Client(transport=transport)
    first = client.planetary_k_index()
    second = client.planetary_k_index()
    assert second is first
    headers = transport.calls[1].headers
    assert headers["If-None-Match"] == '"abc"'
    assert headers["If-Modified-Since"] == "Thu, 15 Oct 2026 17:51:18 GMT"


def test_conditional_requests_can_be_turned_off() -> None:
    raw = fixture(KP_FIXTURE)
    transport = FakeTransport([ok(raw, ETag='"abc"'), ok(raw, ETag='"abc"')])
    client = Client(transport=transport, conditional=False)
    client.planetary_k_index()
    client.planetary_k_index()
    assert "If-None-Match" not in transport.calls[1].headers


def test_new_content_replaces_the_cached_one() -> None:
    old = fixture("kp-3h/2026-10-15-built.json")
    new = fixture(KP_FIXTURE)
    transport = FakeTransport([ok(old, ETag='"1"'), ok(new, ETag='"2"')])
    client = Client(transport=transport)
    client.planetary_k_index()
    second = client.planetary_k_index()
    assert second == parse_planetary_k_index(new, source_url=KP_URL)
    assert transport.calls[1].headers["If-None-Match"] == '"1"'


def test_304_without_a_cached_copy_is_unexpected() -> None:
    transport = FakeTransport([HttpResponse(status=304, headers={}, content=b"")])
    with pytest.raises(UnexpectedContent, match="304"):
        Client(transport=transport).planetary_k_index()


def test_a_failed_parse_does_not_replace_the_cached_copy() -> None:
    raw = fixture(KP_FIXTURE)
    transport = FakeTransport(
        [
            ok(raw, ETag='"good"'),
            ok(raw[: len(raw) // 2], ETag='"cut"'),
            HttpResponse(status=304, headers={}, content=b""),
        ]
    )
    client = Client(transport=transport)
    first = client.planetary_k_index()
    with pytest.raises(SourceNotReady):
        client.planetary_k_index()
    assert transport.calls[1].headers["If-None-Match"] == '"good"'
    assert client.planetary_k_index() is first
    assert transport.calls[2].headers["If-None-Match"] == '"good"'


# --- source errors ----------------------------------------------------------


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_statuses_are_not_ready(status: int) -> None:
    transport = FakeTransport([HttpResponse(status=status, headers={}, content=b"")])
    with pytest.raises(SourceNotReady, match=str(status)):
        Client(transport=transport).planetary_k_index()


def test_a_429_is_rate_limited_and_says_where() -> None:
    refused = HttpResponse(status=429, headers={"Retry-After": "600"}, content=b"")
    with pytest.raises(RateLimited) as info:
        Client(transport=FakeTransport([refused])).planetary_k_index()
    assert info.value.retry_after == "600"
    assert info.value.product == "planetary_k_index"


@pytest.mark.parametrize("status", [400, 403, 404, 410])
def test_client_errors_are_unexpected(status: int) -> None:
    transport = FakeTransport([HttpResponse(status=status, headers={}, content=b"")])
    with pytest.raises(UnexpectedContent, match=str(status)) as info:
        Client(transport=transport).planetary_k_index()
    assert info.value.status == status
    assert info.value.location is None


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirects_are_not_followed(status: int) -> None:
    response = HttpResponse(
        status=status,
        headers={"Location": "https://www.weather.gov/notification/"},
        content=b"",
    )
    with pytest.raises(UnexpectedContent, match=r"weather\.gov/notification") as info:
        Client(transport=FakeTransport([response])).planetary_k_index()
    assert info.value.status == status
    assert info.value.location == "https://www.weather.gov/notification/"


def test_html_page_is_unexpected() -> None:
    page = ok(b"<html><body>Moved</body></html>", **{"Content-Type": "text/html"})
    with pytest.raises(UnexpectedContent):
        Client(transport=FakeTransport([page])).planetary_k_index()


def test_html_content_type_is_unexpected_even_with_json_body() -> None:
    page = ok(fixture(KP_FIXTURE), **{"Content-Type": "text/html; charset=utf-8"})
    with pytest.raises(UnexpectedContent, match="HTML"):
        Client(transport=FakeTransport([page])).planetary_k_index()


def test_parse_errors_pass_through() -> None:
    bad = (
        b'[{"time_tag":"2026-10-08T00:00:00","Kp":12,"a_running":4,"station_count":8}]'
    )
    with pytest.raises(ParseError):
        Client(transport=FakeTransport([ok(bad)])).planetary_k_index()


def test_transport_errors_pass_through() -> None:
    transport = FakeTransport([SourceNotReady("timed out")])
    with pytest.raises(SourceNotReady, match="timed out"):
        Client(transport=transport).planetary_k_index()


def _error_through_the_client(response: HttpResponse | Exception) -> SwpcError:
    with pytest.raises(SwpcError) as info:
        Client(transport=FakeTransport([response])).planetary_k_index()
    return info.value


@pytest.mark.parametrize(
    "response",
    [
        ok(
            b'[{"time_tag":"2026-10-08T00:00:00","Kp":12,"a_running":4,'
            b'"station_count":8}]'
        ),
        ok(b"<html>"),
        ok(b'[{"time_tag":"2026-10-08T00:00:00","Kp":'),
        HttpResponse(status=404, headers={}, content=b""),
        SourceNotReady("timed out"),
    ],
)
def test_errors_through_the_client_name_product_and_url(
    response: HttpResponse | Exception,
) -> None:
    error = _error_through_the_client(response)
    assert error.product == "planetary_k_index"
    assert error.url == KP_URL
    assert "planetary_k_index" in str(error)
    assert KP_URL in str(error)


def test_errors_raised_by_a_parser_name_neither_product_nor_url() -> None:
    with pytest.raises(SwpcError) as info:
        parse_planetary_k_index(b"<html>")
    assert info.value.product is None
    assert info.value.url is None
    assert str(info.value) == "got HTML or XML instead of JSON"


# --- logging --------------------------------------------------------------------


def test_skipped_records_are_logged_as_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    records = json.loads(fixture(KP_FIXTURE))
    records[5]["Kp"] = 12
    transport = FakeTransport([ok(json.dumps(records).encode())])
    with caplog.at_level(logging.DEBUG, logger="swpc_kit"):
        kp = Client(transport=transport).planetary_k_index()
    assert len(kp.skipped) == 1
    [record] = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert record.name == "swpc_kit.client"
    message = record.getMessage()
    assert "planetary_k_index" in message
    assert "1 record" in message
    assert "record 5" in message


def test_a_304_is_logged_at_debug_level(caplog: pytest.LogCaptureFixture) -> None:
    transport = FakeTransport(
        [
            ok(fixture(KP_FIXTURE), ETag='"a"'),
            HttpResponse(status=304, headers={}, content=b""),
        ]
    )
    client = Client(transport=transport)
    client.planetary_k_index()
    with caplog.at_level(logging.DEBUG, logger="swpc_kit"):
        client.planetary_k_index()
    [record] = caplog.records
    assert record.levelno == logging.DEBUG
    assert "304" in record.getMessage()
    assert KP_URL in record.getMessage()


def test_a_clean_fetch_logs_no_warning(caplog: pytest.LogCaptureFixture) -> None:
    transport = FakeTransport([ok(fixture(KP_FIXTURE))])
    with caplog.at_level(logging.DEBUG, logger="swpc_kit"):
        Client(transport=transport).planetary_k_index()
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_the_library_adds_no_log_handler() -> None:
    assert logging.getLogger("swpc_kit").handlers == []


# --- a product that moved -----------------------------------------------------


def test_urls_replace_the_url_of_a_product() -> None:
    moved = "https://services.swpc.noaa.gov/products/new/kp.json"
    transport = FakeTransport([ok(fixture(KP_FIXTURE))])
    client = Client(transport=transport, urls={"planetary_k_index": moved})
    kp = client.planetary_k_index()
    assert [call.url for call in transport.calls] == [moved]
    assert kp.source_url == moved
    assert kp == parse_planetary_k_index(fixture(KP_FIXTURE), source_url=moved)


def test_urls_leave_the_other_products_alone() -> None:
    transport = FakeTransport([ok(fixture("dst/2026-10-15.json"))])
    client = Client(transport=transport, urls={"planetary_k_index": "https://x/kp"})
    client.kyoto_dst()
    assert transport.calls[0].url == f"{BASE}/products/kyoto-dst.json"


def test_urls_must_name_known_products() -> None:
    with pytest.raises(ValueError, match="kp_index"):
        Client(transport=FakeTransport(), urls={"kp_index": "https://x/kp"})


def test_async_client_takes_urls_too() -> None:
    moved = "https://services.swpc.noaa.gov/products/new/kp.json"
    transport = AsyncFakeTransport(FakeTransport([ok(fixture(KP_FIXTURE))]))
    client = AsyncClient(transport=transport, urls={"planetary_k_index": moved})
    kp = asyncio.run(client.planetary_k_index())
    assert transport.sync.calls[0].url == moved
    assert kp.source_url == moved


# --- without the client extra -------------------------------------------------


def test_custom_transport_works_without_httpx2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import swpc_kit

    # The import below also rebinds swpc_kit.client: restore it afterwards.
    monkeypatch.setattr(swpc_kit, "client", sys.modules["swpc_kit.client"])
    monkeypatch.setitem(sys.modules, "httpx2", None)
    monkeypatch.delitem(sys.modules, "swpc_kit.client._httpx")
    monkeypatch.delitem(sys.modules, "swpc_kit.client")
    client_module = importlib.import_module("swpc_kit.client")
    transport = FakeTransport([ok(fixture(KP_FIXTURE))])
    kp = client_module.Client(transport=transport).planetary_k_index()
    assert kp.data_time == KP_DATA_TIME
    with pytest.raises(ImportError, match=r"pip install 'swpc-kit\[client\]'"):
        client_module.Client()


# --- max_age ----------------------------------------------------------------


def test_fresh_data_passes_max_age() -> None:
    client = Client(
        transport=FakeTransport([ok(fixture(KP_FIXTURE))]),
        clock=at(KP_DATA_TIME + timedelta(hours=5)),
    )
    client.planetary_k_index(max_age=timedelta(hours=6))


def test_stale_data_raises_with_details() -> None:
    client = Client(
        transport=FakeTransport([ok(fixture(KP_FIXTURE))]),
        clock=at(KP_DATA_TIME + timedelta(hours=7)),
    )
    with pytest.raises(StaleData) as info:
        client.planetary_k_index(max_age=timedelta(hours=6))
    assert info.value.data_time == KP_DATA_TIME
    assert info.value.age == timedelta(hours=7)
    assert info.value.max_age == timedelta(hours=6)


def test_client_default_max_age_and_per_call_override() -> None:
    raw = fixture(KP_FIXTURE)
    client = Client(
        transport=FakeTransport([ok(raw), ok(raw)]),
        clock=at(KP_DATA_TIME + timedelta(hours=7)),
        max_age=timedelta(hours=6),
    )
    with pytest.raises(StaleData):
        client.planetary_k_index()
    client.planetary_k_index(max_age=timedelta(days=1))


def test_max_age_applies_to_a_304_reply() -> None:
    raw = fixture(KP_FIXTURE)
    now = [KP_DATA_TIME + timedelta(hours=1)]
    transport = FakeTransport(
        [ok(raw, ETag='"x"'), HttpResponse(status=304, headers={}, content=b"")]
    )
    client = Client(transport=transport, clock=lambda: now[0])
    client.planetary_k_index(max_age=timedelta(hours=6))
    now[0] = KP_DATA_TIME + timedelta(hours=9)
    with pytest.raises(StaleData):
        client.planetary_k_index(max_age=timedelta(hours=6))


def test_stale_data_is_still_cached() -> None:
    raw = fixture(KP_FIXTURE)
    transport = FakeTransport(
        [ok(raw, ETag='"x"'), HttpResponse(status=304, headers={}, content=b"")]
    )
    client = Client(transport=transport, clock=at(KP_DATA_TIME + timedelta(days=2)))
    with pytest.raises(StaleData):
        client.planetary_k_index(max_age=timedelta(hours=1))
    assert client.planetary_k_index().source_url == KP_URL


def test_empty_alerts_cannot_be_stale() -> None:
    client = Client(
        transport=FakeTransport([ok(b"[]")]),
        clock=at(datetime(2030, 1, 1, tzinfo=UTC)),
    )
    alerts = client.alerts(max_age=timedelta(minutes=1))
    assert alerts.data_time is None


def test_naive_clock_is_rejected() -> None:
    client = Client(
        transport=FakeTransport([ok(fixture(KP_FIXTURE))]),
        clock=lambda: datetime(2026, 10, 15),  # noqa: DTZ001
    )
    with pytest.raises(ValueError, match="UTC"):
        client.planetary_k_index(max_age=timedelta(hours=1))


# --- lifecycle --------------------------------------------------------------


def test_context_manager_closes_the_transport() -> None:
    transport = FakeTransport([ok(fixture(KP_FIXTURE))])
    with Client(transport=transport) as client:
        client.planetary_k_index()
    assert transport.closed


# --- async client -----------------------------------------------------------


def test_async_client_fetches_and_reuses_on_304() -> None:
    raw = fixture(KP_FIXTURE)
    transport = AsyncFakeTransport(
        FakeTransport(
            [ok(raw, ETag='"a"'), HttpResponse(status=304, headers={}, content=b"")]
        )
    )

    async def run() -> None:
        async with AsyncClient(transport=transport) as client:
            first = await client.planetary_k_index()
            second = await client.planetary_k_index()
            assert second is first
            assert first == parse_planetary_k_index(raw, source_url=KP_URL)

    asyncio.run(run())
    assert transport.sync.calls[1].headers["If-None-Match"] == '"a"'
    assert transport.sync.closed


def test_async_client_raises_the_same_errors() -> None:
    transport = AsyncFakeTransport(
        FakeTransport([HttpResponse(status=503, headers={}, content=b"")])
    )

    async def run() -> None:
        await AsyncClient(transport=transport).alerts()

    with pytest.raises(SourceNotReady):
        asyncio.run(run())


def test_async_client_parses_off_the_event_loop() -> None:
    threads: list[threading.Thread] = []

    def parse(content: bytes, url: str) -> Any:
        threads.append(threading.current_thread())
        return parse_planetary_k_index(content, source_url=url)

    product = dataclasses.replace(PLANETARY_K_INDEX, parse=parse)
    transport = AsyncFakeTransport(FakeTransport([ok(fixture(KP_FIXTURE))]))

    async def run() -> threading.Thread:
        kp = await AsyncClient(transport=transport).fetch(product)
        assert kp.data_time == KP_DATA_TIME
        return threading.current_thread()

    loop_thread = asyncio.run(run())
    assert len(threads) == 1
    assert threads[0] is not loop_thread


def test_async_client_errors_from_the_parse_name_the_product() -> None:
    transport = AsyncFakeTransport(FakeTransport([ok(b'[{"time_tag": "2026-')]))
    with pytest.raises(SourceNotReady) as info:
        asyncio.run(AsyncClient(transport=transport).planetary_k_index())
    assert info.value.product == "planetary_k_index"
    assert info.value.url == KP_URL


def test_async_client_skipped_records_are_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    records = json.loads(fixture(KP_FIXTURE))
    records[2]["Kp"] = 12
    transport = AsyncFakeTransport(FakeTransport([ok(json.dumps(records).encode())]))
    with caplog.at_level(logging.WARNING, logger="swpc_kit.client"):
        kp = asyncio.run(AsyncClient(transport=transport).planetary_k_index())
    assert [s.index for s in kp.skipped] == [2]
    assert "1 record skipped" in caplog.text


def test_async_stale_data() -> None:
    transport = AsyncFakeTransport(FakeTransport([ok(fixture(KP_FIXTURE))]))
    client = AsyncClient(
        transport=transport, clock=at(KP_DATA_TIME + timedelta(days=1))
    )
    with pytest.raises(StaleData):
        asyncio.run(client.planetary_k_index(max_age=timedelta(hours=1)))


# --- httpx2 transport (with httpx2's mock transport: no network) -----------


def _mock(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_httpx_transport_maps_the_response() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(
            200, headers={"ETag": '"z"'}, content=fixture(KP_FIXTURE)
        )

    transport = HttpxTransport(client=_mock(handler))
    response = transport.get(KP_URL, headers={"User-Agent": "t/1"}, timeout=2.0)
    assert response.status == 200
    assert response.headers["etag"] == '"z"'
    assert response.content == fixture(KP_FIXTURE)
    assert seen[0].headers["User-Agent"] == "t/1"
    assert str(seen[0].url) == KP_URL


def test_httpx_transport_does_not_follow_redirects() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(302, headers={"Location": "https://example.org/x"})

    response = HttpxTransport(client=_mock(handler)).get(
        KP_URL, headers={}, timeout=2.0
    )
    assert response.status == 302
    assert response.headers["location"] == "https://example.org/x"


@pytest.mark.parametrize(
    "error",
    [
        httpx2.ConnectTimeout("slow"),
        httpx2.ReadTimeout("slow"),
        httpx2.ConnectError("refused"),
        httpx2.RemoteProtocolError("cut"),
        httpx2.DecodingError("corrupt gzip"),
    ],
)
def test_httpx_transport_errors_are_not_ready(error: Exception) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise error

    with pytest.raises(SourceNotReady, match=re.escape(KP_URL)) as info:
        HttpxTransport(client=_mock(handler)).get(KP_URL, headers={}, timeout=2.0)
    assert isinstance(info.value, SwpcError)
    assert info.value.__cause__ is error


def test_client_end_to_end_over_httpx_mock() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=fixture(KP_FIXTURE))

    with Client(transport=HttpxTransport(client=_mock(handler))) as client:
        assert client.planetary_k_index() == parse_planetary_k_index(
            fixture(KP_FIXTURE), source_url=KP_URL
        )


def test_async_httpx_transport() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if "kyoto" in str(request.url):
            raise httpx2.ReadTimeout("slow")
        return httpx2.Response(200, content=fixture(KP_FIXTURE))

    async def run() -> None:
        inner = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        async with AsyncClient(transport=AsyncHttpxTransport(client=inner)) as c:
            kp = await c.planetary_k_index()
            assert kp.data_time == KP_DATA_TIME
            with pytest.raises(SourceNotReady):
                await c.kyoto_dst()

    asyncio.run(run())


def test_default_transport_is_httpx() -> None:
    client = Client()
    try:
        assert isinstance(client.transport, HttpxTransport)
    finally:
        client.close()
