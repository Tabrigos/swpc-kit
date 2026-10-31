"""The public API is exported and documented."""

import ast
import importlib
import inspect
from pathlib import Path

import pytest

import swpc_kit

SRC = Path(swpc_kit.__file__).parent
PACKAGES = [
    "swpc_kit",
    "swpc_kit.parse",
    "swpc_kit.models",
    "swpc_kit.export",
    "swpc_kit.client",
    "swpc_kit.skill",
]
PUBLIC_MODULES = [
    "swpc_kit.errors",
    "swpc_kit.http",
    "swpc_kit.codes",
    "swpc_kit.export.geojson",
    "swpc_kit.export.geotiff",
    *(f"swpc_kit.parse.{p.stem}" for p in (SRC / "parse").glob("[!_]*.py")),
    *(f"swpc_kit.models.{p.stem}" for p in (SRC / "models").glob("[!_]*.py")),
]


def _defined_public(module: str) -> set[str]:
    path = SRC.joinpath(*module.split(".")[1:]).with_suffix(".py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    }


@pytest.mark.parametrize("name", PACKAGES)
def test_package_exports_resolve_and_are_documented(name: str) -> None:
    package = importlib.import_module(name)
    assert package.__doc__
    exported = package.__all__
    assert sorted(exported) == sorted(set(exported))
    for attr in exported:
        value = getattr(package, attr)
        if inspect.isclass(value) or inspect.isfunction(value):
            assert inspect.getdoc(value), f"{name}.{attr} has no docstring"


@pytest.mark.parametrize("name", PUBLIC_MODULES)
def test_public_module_is_documented(name: str) -> None:
    module = importlib.import_module(name)
    assert module.__doc__
    for attr in _defined_public(name):
        assert inspect.getdoc(getattr(module, attr)), f"{name}.{attr}"


@pytest.mark.parametrize("group", ["parse", "models"])
def test_every_public_name_is_reexported(group: str) -> None:
    package = importlib.import_module(f"swpc_kit.{group}")
    expected: set[str] = set()
    for path in (SRC / group).glob("[!_]*.py"):
        names = _defined_public(f"swpc_kit.{group}.{path.stem}")
        if group == "parse":
            names = {n for n in names if n.startswith("parse_")}
        expected |= names
    assert set(package.__all__) == expected


def test_top_level_exports_errors_and_version() -> None:
    assert set(swpc_kit.__all__) >= {
        "SwpcError",
        "SourceNotReady",
        "RateLimited",
        "UnexpectedContent",
        "ParseError",
        "StaleData",
        "__version__",
    }
    assert swpc_kit.__version__ == "0.5.0"
