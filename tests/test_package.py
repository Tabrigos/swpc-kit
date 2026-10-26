import importlib
import re
import socket
from importlib import resources

import pytest

import swpc_kit

MODULES = [
    "swpc_kit",
    "swpc_kit.errors",
    "swpc_kit.parse",
    "swpc_kit.models",
    "swpc_kit.export",
    "swpc_kit.client",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports_and_has_docstring(name: str) -> None:
    module = importlib.import_module(name)
    assert module.__doc__
    assert module.__doc__.strip()


def test_version_is_a_pep440_string() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(\.dev\d+)?", swpc_kit.__version__)


def test_package_is_marked_as_typed() -> None:
    assert resources.files("swpc_kit").joinpath("py.typed").is_file()


def test_network_is_blocked_in_tests() -> None:
    with pytest.raises(RuntimeError, match="network"):
        socket.create_connection(("services.swpc.noaa.gov", 443), timeout=1)


def test_only_the_loopback_interface_is_open() -> None:
    with socket.socket() as sock:
        sock.settimeout(0.5)  # should the barrier fail, do not hang
        with pytest.raises(RuntimeError, match="network"):
            sock.connect(("192.0.2.1", 443))  # TEST-NET-1, never routed
    with socket.socket() as sock, pytest.raises(RuntimeError, match="network"):
        sock.connect_ex(("127.0.0.1", 9))
    # asyncio's event loop wakes itself up through a socket pair, which on
    # Windows connects to 127.0.0.1.
    left, right = socket.socketpair()
    with left, right:
        left.sendall(b"x")
        assert right.recv(1) == b"x"
