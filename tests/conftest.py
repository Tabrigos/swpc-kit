"""Shared test setup.

Tests never use the network: they read the fixtures in ``tests/fixtures/``.
Any attempt to open a socket fails loudly instead of reaching SWPC.
"""

import socket
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
