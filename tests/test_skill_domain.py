"""The parts of the bundled skill that are specific to swpc-kit.

``tests/test_skill.py`` is the shared template and checks what every library
skill must do. These tests check what only this library has: the product
table of ``SKILL.md`` against the client, the field tables of
``references/api.md`` against the models, and the examples run against the
recorded fixtures, including the ones fenced ```` ```python nocheck ````
because the shared test has no SWPC to talk to.
"""

import dataclasses
import inspect
import re
import shutil
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

import build_skill
import pytest

import swpc_kit
import swpc_kit.client
import swpc_kit.codes
import swpc_kit.errors
import swpc_kit.export
import swpc_kit.models
import swpc_kit.parse
from swpc_kit.client import PRODUCTS, AsyncClient, Client
from swpc_kit.skill import read_skill

FIXTURES = Path(__file__).parent / "fixtures"
SKILL = read_skill()
BODY = SKILL.split("\n---\n", 1)[1]
FENCE = re.compile(r"^```(\w*)([^\n]*)\n(.*?)^```$", re.MULTILINE | re.DOTALL)
INLINE = re.compile(r"`([^`\n]+)`")
TABLE_ROW = re.compile(r"^\| [^|]+ \| `(\w+)` \| (.+) \|$", re.MULTILINE)


def _public_names() -> set[str]:
    """Every attribute, field, method and module name a reader could use."""
    classes: list[Any] = [Client, AsyncClient]
    for module in (swpc_kit, swpc_kit.models, swpc_kit.errors, swpc_kit.codes):
        classes += [v for v in vars(module).values() if inspect.isclass(v)]
    names = {cls.__name__ for cls in classes}
    names |= {name for cls in classes for name in dir(cls)}
    for cls in classes:
        if dataclasses.is_dataclass(cls):
            names |= {f.name for f in dataclasses.fields(cls)}
        for _, method in inspect.getmembers(cls, inspect.isfunction):
            names |= set(inspect.signature(method).parameters)
    return names


def _models() -> list[type]:
    found = [getattr(swpc_kit.models, n) for n in swpc_kit.models.__all__]
    return [m for m in found if inspect.isclass(m) and dataclasses.is_dataclass(m)]


# --- SKILL.md against the code ------------------------------------------------


def test_product_table_lists_every_client_method() -> None:
    rows = [method for method, _ in TABLE_ROW.findall(BODY)]
    assert sorted(rows) == sorted(p.name for p in PRODUCTS)
    for name in rows:
        assert callable(getattr(Client, name))
        assert inspect.iscoroutinefunction(getattr(AsyncClient, name))


def test_product_table_attributes_exist() -> None:
    known = _public_names()
    checked = 0
    for _, cells in TABLE_ROW.findall(BODY):
        for span in INLINE.findall(cells):
            if "/" in span:
                continue
            for word in re.findall(r"[A-Za-z_]\w*", re.sub(r'"[^"]*"', "", span)):
                assert word in known, (word, cells)
                checked += 1
    assert checked >= len(PRODUCTS), "the 'Look at' column names too few attributes"


def test_parsers_named_exist() -> None:
    names = set(re.findall(r"\bparse_\w+", BODY))
    assert len(names) >= 2, names
    assert names <= set(swpc_kit.parse.__all__), names - set(swpc_kit.parse.__all__)


@pytest.fixture
def workdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, swpc_from_fixtures: None
) -> Path:
    shutil.copy(FIXTURES / "dst" / "2026-10-15.json", tmp_path / "kyoto-dst.json")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_python_examples_run_against_the_fixtures(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The fixtures were recorded on 2026-10-15: run the examples as if then.
    then = datetime(2026, 10, 15, 13, tzinfo=UTC)
    monkeypatch.setattr(swpc_kit.client, "Client", partial(Client, clock=lambda: then))
    blocks = [code for kind, _, code in FENCE.findall(BODY) if kind == "python"]
    assert len(blocks) >= 3
    namespace: dict[str, Any] = {"__name__": "skill"}
    for number, code in enumerate(blocks):
        exec(compile(code, f"SKILL.md python block {number}", "exec"), namespace)
    raw = (FIXTURES / "ovation-aurora" / "2026-10-15.json").read_bytes()
    oval = swpc_kit.parse.parse_ovation_aurora(raw, partial=True)
    assert namespace["aurora_geojson"](oval)["type"] == "FeatureCollection"
    printed = capsys.readouterr().out.splitlines()
    assert printed[0] == "2026-10-15 12:00:00+00:00 2.67", printed
    assert printed[1].startswith("2026-10-15 "), printed


# --- references/api.md against the models ---------------------------------------


def test_api_reference_lists_every_product() -> None:
    """Each product: its client method, and its URL as its parser's default."""
    reference = build_skill.build()
    client = reference.split("### `Client`\n", 1)[1].split("\n### ", 1)[0]
    parsers = reference.split("## `swpc_kit.parse.", 1)[1]
    for product in PRODUCTS:
        assert f"- `.{product.name}(" in client, product.name
        assert f"source_url: str = '{product.url}'" in parsers, product.url


def test_api_reference_explains_every_model_field() -> None:
    reference = build_skill.build()
    models = _models()
    assert len(models) >= 20, len(models)
    for model in models:
        section = reference.split(f"### `{model.__name__}`\n", 1)[1].split("\n#", 1)[0]
        for field in dataclasses.fields(model):
            row = re.search(rf"^\| `{field.name}` \| .+ \| (.*) \|$", section, re.M)
            assert row, f"{model.__name__}.{field.name} has no row"
            assert row[1].strip(), f"{model.__name__}.{field.name} has no meaning"
