"""The README examples run: ``pycon`` blocks as doctests, ``python`` blocks as code.

The ``python`` blocks fetch from SWPC; here the ``swpc_from_fixtures``
fixture (``conftest.py``) makes the client read the recorded fixtures, so
nothing goes to the network.
"""

import doctest
import re
from pathlib import Path
from typing import Any

import pytest

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
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "fixtures").symlink_to(ROOT / "tests" / "fixtures")
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
