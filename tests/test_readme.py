"""The README examples run: ``pycon`` blocks as doctests, ``python`` blocks as code.

The ``python`` blocks fetch from SWPC; here the client's default transport is
replaced by one that serves the recorded fixtures, so nothing goes to the
network.
"""

import doctest
import re
from pathlib import Path
from typing import Any

import httpx2
import pytest

import swpc_kit.client
from swpc_kit.client import PRODUCTS, AsyncHttpxTransport, HttpxTransport

ROOT = Path(__file__).parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
BLOCK = re.compile(r"^```(pycon|python)\n(.*?)^```$", re.MULTILINE | re.DOTALL)

FIXTURE_FOR = {
    "planetary_k_index": "kp-3h/2026-10-15.json",
    "kyoto_dst": "dst/2026-10-15.json",
    "alerts": "alerts/2026-10-15.json",
}
URLS = {p.url: FIXTURE_FOR[p.name] for p in PRODUCTS if p.name in FIXTURE_FOR}


def _blocks(kind: str) -> list[str]:
    return [body for k, body in BLOCK.findall(README) if k == kind]


def _serve(request: httpx2.Request) -> httpx2.Response:
    name = URLS.get(str(request.url))
    if name is None:
        return httpx2.Response(404)
    return httpx2.Response(200, content=(ROOT / "tests/fixtures" / name).read_bytes())


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A scratch directory where the README's relative paths resolve."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "fixtures").symlink_to(ROOT / "tests" / "fixtures")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        swpc_kit.client,
        "HttpxTransport",
        lambda: HttpxTransport(httpx2.Client(transport=httpx2.MockTransport(_serve))),
    )
    monkeypatch.setattr(
        swpc_kit.client,
        "AsyncHttpxTransport",
        lambda: AsyncHttpxTransport(
            httpx2.AsyncClient(transport=httpx2.MockTransport(_serve))
        ),
    )
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
