"""The README examples run: ``pycon`` blocks as doctests, ``python`` blocks as code.

The ``python`` blocks fetch from SWPC; here the ``swpc_from_fixtures``
fixture (``conftest.py``) makes the client read the recorded fixtures, so
nothing goes to the network.
"""

import doctest
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from swpc_kit.errors import RateLimited, SourceNotReady, UnexpectedContent
from swpc_kit.parse import parse_planetary_k_index

ROOT = Path(__file__).parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
BLOCK = re.compile(r"^```(pycon|python)\n(.*?)^```$", re.MULTILINE | re.DOTALL)


def _blocks(kind: str) -> list[str]:
    return [body for k, body in BLOCK.findall(README) if k == kind]


@pytest.fixture
def workdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, swpc_from_fixtures: None
) -> Path:
    """A scratch directory where the README's relative paths resolve."""
    # A copy, not a symlink: on Windows a symlink needs a privilege that a
    # normal user does not have. The fixtures stay under 2 MiB.
    shutil.copytree(ROOT / "tests" / "fixtures", tmp_path / "tests" / "fixtures")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_readme_has_examples() -> None:
    assert len(_blocks("pycon")) >= 5
    assert len(_blocks("python")) >= 3


def test_pycon_examples(workdir: Path) -> None:
    parser = doctest.DocTestParser()
    runner = doctest.DocTestRunner(
        optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
    )
    globs: dict[str, Any] = {}
    for number, body in enumerate(_blocks("pycon")):
        test = parser.get_doctest(body, globs, f"README block {number}", "README.md", 0)
        runner.run(test, clear_globs=False)
        globs.update(test.globs)  # DocTest works on a copy
    results = runner.summarize(verbose=False)
    assert results.failed == 0
    assert results.attempted > 0


@pytest.mark.parametrize("number", range(len(_blocks("python"))))
def test_python_examples(workdir: Path, number: int) -> None:
    code = _blocks("python")[number]
    exec(compile(code, f"README python block {number}", "exec"), {"__name__": "readme"})


def test_geotiff_example_writes_a_file(workdir: Path) -> None:
    for code in _blocks("python"):
        if "write_geotiff" in code:
            exec(compile(code, "README geotiff block", "exec"), {"__name__": "readme"})
    assert (workdir / "drap.tif").stat().st_size > 0


# --- the recipe with a politefetch gate -------------------------------------

KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
KP_BODY = (ROOT / "tests" / "fixtures" / "kp-3h" / "2026-10-15.json").read_bytes()


@dataclass
class FakeAttempt:
    """Records what the recipe tells the gate, with politefetch's method names."""

    conditional_headers: dict[str, str]
    calls: list[tuple[str, object]] = field(default_factory=list)

    def __enter__(self) -> "FakeAttempt":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def response(self, status: int, *, headers: object) -> None:
        self.calls.append(("response", status))

    def failure(self, shape: str, *, status: int, headers: object) -> None:
        self.calls.append(("failure", shape))


@dataclass
class FakeGate:
    attempt_made: FakeAttempt = field(
        default_factory=lambda: FakeAttempt({"If-None-Match": '"old"'})
    )

    def attempt(self, url: str) -> FakeAttempt:
        return self.attempt_made


@dataclass
class FakeResponse:
    status_code: int
    content: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class FakeHttp:
    response: FakeResponse
    sent: list[dict[str, str]] = field(default_factory=list)

    def get(self, url: str, *, headers: dict[str, str]) -> FakeResponse:
        self.sent.append(headers)
        return self.response


def _fetch_politely() -> Callable[..., Any]:
    (code,) = [c for c in _blocks("python") if "def fetch_politely" in c]
    names: dict[str, Any] = {"__name__": "readme"}
    exec(compile(code, "README politefetch block", "exec"), names)
    fetch: Callable[..., Any] = names["fetch_politely"]
    return fetch


def test_politely_a_good_body_is_a_good_answer() -> None:
    gate, http = FakeGate(), FakeHttp(FakeResponse(200, KP_BODY))
    kp = _fetch_politely()(gate, http, KP_URL, parse_planetary_k_index)
    assert kp.values
    assert gate.attempt_made.calls == [("response", 200)]
    # Without a copy, no conditional headers: a 304 would be of no use.
    assert http.sent == [{}]


def test_politely_a_truncated_body_is_a_failure_not_an_answer() -> None:
    gate, http = FakeGate(), FakeHttp(FakeResponse(200, KP_BODY[:-40]))
    with pytest.raises(SourceNotReady):
        _fetch_politely()(gate, http, KP_URL, parse_planetary_k_index)
    assert gate.attempt_made.calls == [("failure", "not_ready")]


def test_politely_an_html_page_is_a_failure() -> None:
    page = FakeResponse(200, b"<html></html>", {"Content-Type": "text/html"})
    gate = FakeGate()
    with pytest.raises(UnexpectedContent):
        _fetch_politely()(gate, FakeHttp(page), KP_URL, parse_planetary_k_index)
    assert gate.attempt_made.calls == [("failure", "unexpected_content")]


@pytest.mark.parametrize("status", [203, 204, 206])
def test_politely_a_refused_2xx_is_a_failure(status: int) -> None:
    # politefetch takes any 2xx as a good answer: the recipe must not tell it.
    gate, http = FakeGate(), FakeHttp(FakeResponse(status, KP_BODY))
    with pytest.raises(UnexpectedContent):
        _fetch_politely()(gate, http, KP_URL, parse_planetary_k_index)
    assert gate.attempt_made.calls == [("failure", "unexpected_content")]


def test_politely_a_429_reaches_the_gate_and_raises_rate_limited() -> None:
    gate = FakeGate()
    refused = FakeHttp(FakeResponse(429, headers={"Retry-After": "600"}))
    with pytest.raises(RateLimited):
        _fetch_politely()(gate, refused, KP_URL, parse_planetary_k_index)
    assert gate.attempt_made.calls == [("response", 429)]


def test_politely_a_304_returns_the_copy() -> None:
    gate, http = FakeGate(), FakeHttp(FakeResponse(304))
    copy = object()
    assert _fetch_politely()(gate, http, KP_URL, parse_planetary_k_index, copy) is copy
    assert gate.attempt_made.calls == [("response", 304)]
    assert http.sent == [{"If-None-Match": '"old"'}]
