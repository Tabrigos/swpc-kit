"""Record SWPC products as test fixtures.

Downloads every product listed in ``tools/fixtures.toml`` into
``tests/fixtures/<product>/<YYYY-MM-DD>.<ext>`` (UTC date of the download),
reduces the large JSON products as configured, and updates the table of
recorded files in ``tests/fixtures/README.md``.

Usage::

    uv run python tools/record_fixtures.py            # every product
    uv run python tools/record_fixtures.py kp-3h dst  # only these

This is the only code in the repository that uses the network. Downloaded
content is data: it is checked and saved, never interpreted.

A reduction keeps the first ``head`` and last ``tail`` groups of consecutive
records sharing the ``group`` key, plus every ``every``-th group in between,
so that records belonging together (several sources or energy bands at the
same time, a whole longitude of a grid) stay together. It re-serialises the
JSON, so it refuses files whose formatting ``json.dumps`` would not reproduce
byte for byte.
"""

import argparse
import json
import re
import sys
import tomllib
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIST = ROOT / "tools" / "fixtures.toml"
DEFAULT_OUT = ROOT / "tests" / "fixtures"
MAX_TOTAL_BYTES = 2 * 1024 * 1024
USER_AGENT = "swpc-kit-fixture-recorder (+https://github.com/Tabrigos/swpc-kit)"
TIMEOUT_SECONDS = 60

BEGIN = "<!-- recorded:begin -->"
END = "<!-- recorded:end -->"
TABLE_HEADER = (
    "| File | Source | Recorded (UTC) | Size (bytes) | Notes |\n|---|---|---|---|---|"
)

_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
_ROW_PATH = re.compile(r"^\| `([^`]+)` \|")
_EXTENSIONS = ("json", "txt")
_PRODUCT_KEYS = {"name", "url", "reduce"}
_REDUCE_KEYS = {"head", "tail", "every", "group", "array"}

Fetch = Callable[[str], tuple[bytes, str]]


class RecordError(Exception):
    """A download cannot be recorded as a fixture."""


@dataclass(frozen=True, slots=True)
class Reduction:
    """How to shrink a large JSON product.

    Attributes:
        head: Number of leading groups to keep.
        tail: Number of trailing groups to keep.
        every: Keep also every ``every``-th group (counting from the first).
        group: Key (for objects) or index (for arrays) shared by consecutive
            records that belong together; ``None`` makes each record a group.
        array: Key of the array to reduce when the document is an object;
            ``None`` when the document itself is the array.
    """

    head: int
    tail: int
    every: int
    group: str | int | None = None
    array: str | None = None

    def describe(self) -> str:
        """Return a one-line description for the fixtures README."""
        if self.group is None:
            unit = "elements"
        elif isinstance(self.group, int):
            unit = f"groups by item {self.group}"
        else:
            unit = f"groups by {self.group}"
        where = f"{self.array}: " if self.array is not None else ""
        return (
            f"{where}first {self.head} and last {self.tail} {unit}, "
            f"plus every {_ordinal(self.every)}"
        )


@dataclass(frozen=True, slots=True)
class Product:
    """A product to record."""

    name: str
    url: str
    reduce: Reduction | None = None

    @property
    def ext(self) -> str:
        """File extension of the product, taken from its URL."""
        return urlsplit(self.url).path.rsplit(".", 1)[-1]


@dataclass(frozen=True, slots=True)
class Row:
    """One line of the table of recorded fixtures."""

    path: str
    url: str
    recorded: datetime
    size: int
    notes: str

    def render(self) -> str:
        """Return the Markdown table line."""
        line = (
            f"| `{self.path}` | {self.url} | {self.recorded:%Y-%m-%d %H:%M} "
            f"| {self.size} |"
        )
        return f"{line} {self.notes} |" if self.notes else f"{line} |"


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _reduction(name: str, raw: object) -> Reduction:
    if not isinstance(raw, dict):
        raise ValueError(f"{name}: reduce must be a table")
    unknown = set(raw) - _REDUCE_KEYS
    if unknown:
        raise ValueError(f"{name}: unknown reduce keys: {', '.join(sorted(unknown))}")
    try:
        head, tail, every = raw["head"], raw["tail"], raw["every"]
    except KeyError as exc:
        raise ValueError(f"{name}: reduce needs {exc.args[0]}") from None
    for key, value, minimum in (("head", head, 0), ("tail", tail, 0)):
        if not isinstance(value, int) or value < minimum:
            raise ValueError(f"{name}: {key} must be an integer >= {minimum}")
    if not isinstance(every, int) or every < 1:
        raise ValueError(f"{name}: every must be an integer >= 1")
    group = raw.get("group")
    if group is not None and not isinstance(group, str | int):
        raise ValueError(f"{name}: group must be a key or an index")
    array = raw.get("array")
    if array is not None and not isinstance(array, str):
        raise ValueError(f"{name}: array must be a key")
    return Reduction(head=head, tail=tail, every=every, group=group, array=array)


def load_products(text: str) -> list[Product]:
    """Parse and validate the product list.

    Args:
        text: Content of the TOML product list.

    Returns:
        The products, in file order.

    Raises:
        ValueError: If an entry is incomplete or inconsistent.
    """
    products: list[Product] = []
    seen: set[str] = set()
    for entry in tomllib.loads(text).get("product", []):
        name = entry.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise ValueError(f"bad or missing name: {name!r}")
        unknown = set(entry) - _PRODUCT_KEYS
        if unknown:
            raise ValueError(f"{name}: unknown keys: {', '.join(sorted(unknown))}")
        url = entry.get("url")
        if not isinstance(url, str):
            raise ValueError(f"{name}: missing url")
        if urlsplit(url).scheme != "https":
            raise ValueError(f"{name}: url must use https")
        reduce = _reduction(name, entry["reduce"]) if "reduce" in entry else None
        product = Product(name=name, url=url, reduce=reduce)
        if product.ext not in _EXTENSIONS:
            raise ValueError(f"{name}: url extension must be one of {_EXTENSIONS}")
        if reduce is not None and product.ext != "json":
            raise ValueError(f"{name}: only JSON products can be reduced")
        if name in seen:
            raise ValueError(f"{name}: listed twice")
        seen.add(name)
        products.append(product)
    return products


def check_content(raw: bytes, content_type: str, ext: str) -> None:
    """Refuse downloads that are not the expected product.

    Args:
        raw: Downloaded bytes.
        content_type: Value of the ``Content-Type`` response header.
        ext: Expected extension, ``json`` or ``txt``.

    Raises:
        RecordError: If the content is empty, HTML, or invalid JSON.
    """
    text = raw.decode("utf-8-sig", errors="replace")
    if not text.strip():
        raise RecordError("empty response")
    if "html" in content_type.lower() or text.lstrip().startswith("<"):
        raise RecordError("got an HTML page instead of the product")
    if ext == "json":
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise RecordError(f"invalid or truncated JSON: {exc}") from None


def _group_key(item: Any, group: str | int | None, position: int) -> Any:
    if group is None:
        return position
    try:
        return item[group]
    except (KeyError, IndexError, TypeError):
        raise RecordError(f"record {position} has no {group!r}") from None


def reduce_json(raw: bytes, reduction: Reduction) -> bytes:
    """Shrink a JSON product as described by ``reduction``.

    Args:
        raw: The complete JSON document.
        reduction: What to keep.

    Returns:
        The reduced document, serialised like the source.

    Raises:
        RecordError: If the document has no such array, or its formatting
            would change when serialised again.
    """
    text = raw.decode("utf-8")
    document = json.loads(text)
    if json.dumps(document) != text:
        raise RecordError(
            "formatting would change on re-serialisation; "
            "keep the file whole or reduce it by hand"
        )
    if reduction.array is None:
        items = document
    elif isinstance(document, dict) and isinstance(document.get(reduction.array), list):
        items = document[reduction.array]
    else:
        raise RecordError(f"no array {reduction.array!r} in the document")
    if not isinstance(items, list):
        raise RecordError("the document is not an array")

    groups: list[list[Any]] = []
    previous: Any = object()
    for position, item in enumerate(items):
        key = _group_key(item, reduction.group, position)
        if not groups or key != previous:
            groups.append([])
        groups[-1].append(item)
        previous = key

    n = len(groups)
    kept = [
        item
        for i, group in enumerate(groups)
        if i < reduction.head or i >= n - reduction.tail or i % reduction.every == 0
        for item in group
    ]
    if reduction.array is None:
        document = kept
    else:
        document[reduction.array] = kept
    return json.dumps(document).encode("utf-8")


def fixture_path(out: Path, product: Product, when: datetime) -> Path:
    """Return where the fixture of ``product`` recorded at ``when`` goes."""
    return out / product.name / f"{when:%Y-%m-%d}.{product.ext}"


def update_readme(text: str, rows: Sequence[Row]) -> str:
    """Insert or replace ``rows`` in the table of recorded fixtures.

    Args:
        text: Current README content, with the begin and end markers.
        rows: Rows to insert or replace, matched by file path.

    Returns:
        The new README content, with the table sorted by path.

    Raises:
        RecordError: If the markers are missing.
    """
    try:
        before, rest = text.split(BEGIN, 1)
        table, after = rest.split(END, 1)
    except ValueError:
        raise RecordError(f"README needs the {BEGIN} and {END} markers") from None
    lines: dict[str, str] = {}
    for line in table.splitlines():
        match = _ROW_PATH.match(line)
        if match:
            lines[match.group(1)] = line
    for row in rows:
        lines[row.path] = row.render()
    body = "\n".join(lines[path] for path in sorted(lines))
    return f"{before}{BEGIN}\n{TABLE_HEADER}\n{body}\n{END}{after}"


def fetch(url: str) -> tuple[bytes, str]:
    """Download ``url`` and return its body and content type."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        body: bytes = response.read()
        content_type: str = response.headers.get("Content-Type", "")
    return body, content_type


def record(
    products: Sequence[Product], out: Path, fetch: Fetch, now: datetime
) -> list[Row]:
    """Download, check and reduce every product, then write the fixtures.

    Nothing is written unless every product downloads and checks cleanly.

    Args:
        products: What to record.
        out: The fixtures directory, which holds ``README.md``.
        fetch: Function that downloads a URL.
        now: Time of the recording, in UTC; its date names the files.

    Returns:
        The rows added to the README.

    Raises:
        RecordError: If a download is not the expected product.
        ValueError: If ``now`` is not in UTC.
    """
    if now.utcoffset() != timedelta(0):
        raise ValueError("now must be an aware datetime in UTC")
    pending: list[tuple[Path, bytes, Row]] = []
    for product in products:
        try:
            raw, content_type = fetch(product.url)
            check_content(raw, content_type, product.ext)
            data, notes = raw, ""
            if product.reduce is not None:
                data = reduce_json(raw, product.reduce)
                notes = f"reduced from {len(raw)} bytes: {product.reduce.describe()}"
        except RecordError as exc:
            raise RecordError(f"{product.name} ({product.url}): {exc}") from exc
        path = fixture_path(out, product, now)
        row = Row(path.relative_to(out).as_posix(), product.url, now, len(data), notes)
        pending.append((path, data, row))

    readme = out / "README.md"
    new_readme = update_readme(
        readme.read_text(encoding="utf-8"), [row for *_, row in pending]
    )
    for path, data, _ in pending:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    readme.write_text(new_readme, encoding="utf-8")
    return [row for *_, row in pending]


def _total_size(out: Path) -> int:
    return sum(
        p.stat().st_size for p in out.rglob("*") if p.is_file() and p.parent != out
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the recorder from the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("names", nargs="*", help="products to record (default: all)")
    parser.add_argument("--list", type=Path, default=DEFAULT_LIST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    products = load_products(args.list.read_text(encoding="utf-8"))
    if args.names:
        unknown = set(args.names) - {p.name for p in products}
        if unknown:
            parser.error(f"unknown products: {', '.join(sorted(unknown))}")
        products = [p for p in products if p.name in args.names]

    try:
        rows = record(products, args.out, fetch, datetime.now(UTC))
    except RecordError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for row in rows:
        print(f"{row.size:>9}  {row.path}")
    total = _total_size(args.out)
    print(f"{total:>9}  total in {args.out}")
    if total > MAX_TOTAL_BYTES:
        print(f"error: fixtures exceed {MAX_TOTAL_BYTES} bytes", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
