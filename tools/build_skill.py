"""Generate the API reference of the bundled agent skill from the code.

Writes ``src/swpc_kit/skill/swpc-kit/references/api.md``: products, client,
models (fields, properties, methods), errors and exports, all read from the
installed package by introspection. The hand-written ``SKILL.md`` next to it
points here for details.

Usage::

    uv run python tools/build_skill.py           # rewrite the file
    uv run python tools/build_skill.py --check   # exit 1 if it is stale

``tests/test_skill.py`` fails when the committed file differs from what this
script produces, so a change to the public API cannot ship without it.
"""

import argparse
import dataclasses
import enum
import inspect
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import swpc_kit
import swpc_kit.client
import swpc_kit.codes
import swpc_kit.errors
import swpc_kit.export.geojson
import swpc_kit.models
import swpc_kit.parse
from swpc_kit.client import PRODUCTS, Client

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "src" / "swpc_kit" / "skill" / "swpc-kit" / "references" / "api.md"

MODEL_MODULES = ["indices", "solar_wind", "goes", "alerts", "bulletins", "grids"]

_QUALIFIED = re.compile(r"\b(?:[a-z_][\w]*\.)+([A-Za-z_]\w*)")
_ATTRIBUTE = re.compile(r"^    (\w+)(?: \([^)]*\))?: (.*)$")


def _short(text: str) -> str:
    """Drop module prefixes: ``swpc_kit.models.goes.XraySample`` -> ``XraySample``."""
    text = text.replace("<class '", "").replace("'>", "")
    return _QUALIFIED.sub(r"\1", text)


def _type(annotation: Any) -> str:
    if isinstance(annotation, type):
        return annotation.__name__
    return _short(str(annotation))


_ROLE = re.compile(r":(?:class|meth|func|data|mod|attr):`~?(?:[\w.]*\.)?([^`]+)`")


def _md(text: str) -> str:
    """Turn reStructuredText inline markup into Markdown."""
    return _ROLE.sub(r"`\1`", text).replace("``", "`")


def _cell(text: str) -> str:
    """Make text safe inside a Markdown table cell."""
    return text.replace("|", "\\|")


def _first_line(obj: Any) -> str:
    doc = inspect.getdoc(obj) or ""
    return _md(doc.split("\n\n")[0].replace("\n", " ").strip())


def _attributes(cls: type) -> dict[str, str]:
    """Parse the ``Attributes:`` section of a Google-style class docstring."""
    doc = inspect.getdoc(cls) or ""
    found: dict[str, str] = {}
    lines = iter(doc.splitlines())
    for line in lines:
        if line.strip() == "Attributes:":
            break
    current: str | None = None
    for line in lines:
        if line and not line.startswith(" "):
            break
        match = _ATTRIBUTE.match(line)
        if match:
            current = match[1]
            found[current] = _md(match[2].strip())
        elif current is not None and line.strip():
            found[current] += " " + _md(line.strip())
    return found


def _default(value: Any) -> str:
    if isinstance(value, enum.Enum):
        return f"{type(value).__name__}.{value.name}"
    if callable(value):
        return str(getattr(value, "__name__", "..."))
    return repr(value)


def _signature(func: Callable[..., Any], *, drop_self: bool = True) -> str:
    """Render a signature with short type names and stable defaults."""
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    if drop_self and params and params[0].name in ("self", "cls"):
        params = params[1:]
    parts: list[str] = []
    star_done = False
    for p in params:
        if p.kind is p.KEYWORD_ONLY and not star_done:
            parts.append("*")
            star_done = True
        if p.kind is p.VAR_POSITIONAL:
            star_done = True
        text = p.name
        if p.annotation is not p.empty:
            text += f": {_type(p.annotation)}"
        if p.default is not p.empty:
            text += f" = {_default(p.default)}"
        parts.append(text)
    returns = ""
    if sig.return_annotation is not sig.empty:
        returns = f" -> {_type(sig.return_annotation)}"
    return f"({', '.join(parts)}){returns}"


def _members(cls: type) -> Iterator[tuple[str, str]]:
    """Public properties and methods defined in swpc_kit (inherited included)."""
    field_names = (
        {f.name for f in dataclasses.fields(cls)}
        if dataclasses.is_dataclass(cls)
        else set()
    )
    for attr in inspect.classify_class_attrs(cls):
        name = attr.name
        if name.startswith("_") or name in field_names:
            continue
        if not attr.defining_class.__module__.startswith("swpc_kit"):
            continue
        obj: Any = attr.object
        if attr.kind == "property":
            returns = inspect.signature(obj.fget).return_annotation
            yield f"`{name}` → `{_type(returns)}`", _first_line(obj)
        elif attr.kind in ("method", "class method", "static method"):
            func = obj if attr.kind == "method" else obj.__func__
            yield f"`{name}{_signature(func)}`", _first_line(func)


def _class_section(cls: type) -> list[str]:
    out = [f"### `{cls.__name__}`", "", _first_line(cls), ""]
    if issubclass(cls, enum.Enum):
        values = ", ".join(f"`{m.name}` = `{m.value!r}`" for m in cls)
        out += [f"Members: {values}.", ""]
        return out
    if dataclasses.is_dataclass(cls):
        described = _attributes(cls)
        out += ["| Field | Type | Meaning |", "|---|---|---|"]
        for f in dataclasses.fields(cls):
            meaning = _cell(described.get(f.name, ""))
            out.append(f"| `{f.name}` | `{_cell(_type(f.type))}` | {meaning} |")
        out.append("")
    members = list(_members(cls))
    if members:
        out += [f"- {name}: {doc}" if doc else f"- {name}" for name, doc in members]
        out.append("")
    return out


def _parsers_by_url() -> dict[str, Callable[..., Any]]:
    found = {}
    for name in swpc_kit.parse.__all__:
        func = getattr(swpc_kit.parse, name)
        found[inspect.signature(func).parameters["source_url"].default] = func
    return found


def build() -> str:
    """Return the content of ``references/api.md``."""
    version = swpc_kit.__version__
    out = [
        f"# swpc-kit {version}: API reference",
        "",
        "<!-- Generated by tools/build_skill.py from the code. Do not edit by hand:",
        "     run `uv run python tools/build_skill.py` after changing the API. -->",
        "",
        "Read only the section you need. Times are aware UTC `datetime` objects",
        "everywhere; every top-level model has `data_time` and `source_url`.",
        "",
        "Contents: [Products](#products) · [Client](#client) ·",
        " · ".join(f"[{m}](#models-{m.replace('_', '-')})" for m in MODEL_MODULES)
        + " · [Errors](#errors) · [Exports](#exports)"
        + " · [Message codes](#message-codes)",
        "",
        "## Products",
        "",
        "| Client method | Parser | Returns | URL |",
        "|---|---|---|---|",
    ]
    parsers = _parsers_by_url()
    for product in PRODUCTS:
        parser = parsers[product.url]
        returns = _type(inspect.signature(parser).return_annotation)
        out.append(
            f"| `{product.name}` | `{parser.__name__}` | `{returns}` | {product.url} |"
        )
    out += [
        "",
        "Every parser is `parse_x(raw: str | bytes, *, source_url=<URL>) -> Model`.",
        "`parse_ovation_aurora` also takes `partial=False`; `True` accepts a grid",
        "with whole longitudes missing.",
        "",
        "## Client",
        "",
        "`from swpc_kit.client import Client, AsyncClient` (`client` extra).",
        "",
        f"`Client{_signature(Client.__init__)}`",
        "",
        "`AsyncClient` takes the same arguments, its methods are coroutines, and it",
        "closes with `aclose()` / `async with`.",
        "",
    ]
    for name in ("fetch", "close"):
        method = getattr(Client, name)
        out.append(f"- `{name}{_signature(method)}`: {_first_line(method)}")
    out += [
        "- one method per product, `client.<method>(*, max_age=None) -> Model`"
        " (see [Products](#products)).",
        "",
    ]
    for module_name in MODEL_MODULES:
        module = sys.modules[f"swpc_kit.models.{module_name}"]
        out += [
            f"## Models: {module_name}",
            "",
            f"`swpc_kit.models.{module_name}` (all re-exported by `swpc_kit.models`).",
            "",
        ]
        for name in swpc_kit.models.__all__:
            obj = getattr(swpc_kit.models, name)
            if getattr(obj, "__module__", "") != module.__name__:
                continue
            if inspect.isclass(obj):
                out += _class_section(obj)
            else:
                out += [f"### `{name}{_signature(obj, drop_self=False)}`", ""]
                out += [_first_line(obj), ""]
    geojson = swpc_kit.export.geojson.to_geojson
    out += [
        "## Errors",
        "",
        "`from swpc_kit import SwpcError, SourceNotReady, UnexpectedContent, "
        "ParseError, StaleData`",
        "",
    ]
    for name in (
        "SwpcError",
        "SourceNotReady",
        "UnexpectedContent",
        "ParseError",
        "StaleData",
    ):
        cls = getattr(swpc_kit.errors, name)
        base = cls.__bases__[0].__name__
        out.append(f"- `{name}` ({base}): {_first_line(cls)}")
    out += [
        "",
        "`ParseError` has `field`, `line` (1-based, text products) and `index`",
        "(0-based record in a JSON array). `StaleData` has `data_time`, `max_age`,"
        " `age`.",
        "",
        "## Exports",
        "",
        f"- `swpc_kit.export.to_geojson{_signature(geojson, drop_self=False)}`:"
        f" {_first_line(geojson)}",
        "- `swpc_kit.export.geotiff.write_geotiff(product, path, *, nodata=nan)`"
        " (`geo` extra): write a single-band float32 GeoTIFF in EPSG:4326 with the"
        " times in its tags.",
        "",
        "## Message codes",
        "",
        "`swpc_kit.codes`: catalogue of the alert codes.",
        "",
    ]
    for name in ("by_short", "by_long", "lookup"):
        func = getattr(swpc_kit.codes, name)
        out.append(
            f"- `{name}{_signature(func, drop_self=False)}`: {_first_line(func)}"
        )
    out.append("")
    out += _class_section(swpc_kit.codes.MessageCode)
    out += _class_section(swpc_kit.codes.Verification)
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write the reference, or check that it is up to date."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if stale")
    args = parser.parse_args(argv)
    content = build()
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != content:
            print(f"{TARGET} is stale: run tools/build_skill.py", file=sys.stderr)
            return 1
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
