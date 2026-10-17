"""Shared test setup.

Tests never use the network: they read the fixtures in ``tests/fixtures/``.
Any attempt to open a socket fails loudly instead of reaching SWPC.
"""

import json
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import pytest


def _no_network(*args: Any, **kwargs: Any) -> NoReturn:
    raise RuntimeError("tests must not use the network; read a fixture instead")


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket.socket, "connect", _no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", _no_network)
    monkeypatch.setattr(socket, "create_connection", _no_network)
    monkeypatch.setattr(socket, "getaddrinfo", _no_network)


# --- SWPC served from the fixtures, for examples that use the client --------

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_FOR = {
    "planetary_k_index": "kp-3h/2026-10-15.json",
    "planetary_k_index_forecast": "kp-forecast/2026-10-15.json",
    "planetary_k_index_1m": "kp-1m/2026-10-15.json",
    "kyoto_dst": "dst/2026-10-15.json",
    "f107_flux_30_day": "f107-30-day/2026-10-15.json",
    "noaa_scales": "noaa-scales/2026-10-15.json",
    "rtsw_mag_1m": "rtsw-mag-1m/2026-10-15.json",
    "rtsw_wind_1m": "rtsw-wind-1m/2026-10-15.json",
    "goes_xrays": "goes-xrays-1-day/2026-10-15.json",
    "goes_integral_protons": "goes-protons-1-day/2026-10-15.json",
    "alerts": "alerts/2026-10-15.json",
    "three_day_forecast": "3-day-forecast/2026-10-15.txt",
    "geomagnetic_forecast": "geomag-forecast/2026-10-15.txt",
    "twenty_seven_day_outlook": "27-day-outlook/2026-10-15.txt",
    "drap_global_frequencies": "drap/2026-10-15.txt",
}


def full_ovation() -> bytes:
    """A complete OVATION grid (the recorded fixture is reduced)."""
    coordinates = [[lon, lat, 0] for lon in range(360) for lat in range(-90, 91)]
    return json.dumps(
        {
            "Observation Time": "2026-10-15T17:39:00Z",
            "Forecast Time": "2026-10-15T18:37:00Z",
            "Data Format": "[Longitude, Latitude, Aurora]",
            "coordinates": coordinates,
        }
    ).encode()


@pytest.fixture
def swpc_from_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``Client()`` and ``AsyncClient()`` read the fixtures, not SWPC."""
    import httpx2

    import swpc_kit.client
    from swpc_kit.client import PRODUCTS, AsyncHttpxTransport, HttpxTransport

    bodies: dict[str, Callable[[], bytes]] = {
        p.url: (FIXTURES / FIXTURE_FOR[p.name]).read_bytes
        for p in PRODUCTS
        if p.name in FIXTURE_FOR
    }
    bodies[next(p.url for p in PRODUCTS if p.name == "ovation_aurora")] = full_ovation

    def serve(request: httpx2.Request) -> httpx2.Response:
        body = bodies.get(str(request.url))
        if body is None:
            return httpx2.Response(404)
        return httpx2.Response(200, content=body())

    monkeypatch.setattr(
        swpc_kit.client,
        "HttpxTransport",
        lambda: HttpxTransport(httpx2.Client(transport=httpx2.MockTransport(serve))),
    )
    monkeypatch.setattr(
        swpc_kit.client,
        "AsyncHttpxTransport",
        lambda: AsyncHttpxTransport(
            httpx2.AsyncClient(transport=httpx2.MockTransport(serve))
        ),
    )
