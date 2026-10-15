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
