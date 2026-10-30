"""Guards on tests/fixtures: size cap, naming, and the README inventory."""

import json
import re
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
README = FIXTURES / "README.md"
MAX_TOTAL_BYTES = 2 * 1024 * 1024
NAME = re.compile(r"\d{4}-\d{2}-\d{2}(-sample|-built|-shared|-live)?\.(json|txt)")

FILES = sorted(
    p.relative_to(FIXTURES).as_posix()
    for p in FIXTURES.rglob("*")
    if p.is_file() and p.parent != FIXTURES
)


def _listed() -> list[str]:
    return re.findall(r"^\| `([^`]+)` \|", README.read_text("utf-8"), re.MULTILINE)


def test_fixtures_stay_under_the_size_cap() -> None:
    total = sum((FIXTURES / f).stat().st_size for f in FILES)
    assert total <= MAX_TOTAL_BYTES


def test_every_fixture_is_listed_once_in_readme() -> None:
    listed = _listed()
    assert sorted(listed) == FILES
    assert len(set(listed)) == len(listed)


@pytest.mark.parametrize("name", FILES)
def test_fixture_name_follows_convention(name: str) -> None:
    product, file = name.split("/")
    assert re.fullmatch(r"[a-z0-9][a-z0-9-]*", product)
    assert NAME.fullmatch(file)


@pytest.mark.parametrize("name", [f for f in FILES if f.endswith(".json")])
def test_json_fixtures_are_valid(name: str) -> None:
    json.loads((FIXTURES / name).read_bytes().decode("utf-8-sig"))
