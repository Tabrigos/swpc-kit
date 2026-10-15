import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import record_fixtures as rf

URL = "https://services.swpc.noaa.gov/json/example.json"
WHEN = datetime(2026, 10, 15, 17, 52, tzinfo=UTC)


# --- product list -----------------------------------------------------------


def test_load_products_reads_names_urls_and_reductions() -> None:
    products = rf.load_products(
        """
[[product]]
name = "kp-3h"
url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"

[[product]]
name = "ovation-aurora"
url = "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json"
reduce = { array = "coordinates", group = 0, head = 2, tail = 2, every = 30 }
"""
    )
    assert [p.name for p in products] == ["kp-3h", "ovation-aurora"]
    assert products[0].reduce is None
    assert products[0].ext == "json"
    assert products[1].reduce == rf.Reduction(
        head=2, tail=2, every=30, group=0, array="coordinates"
    )


def test_text_product_extension() -> None:
    (product,) = rf.load_products(
        '[[product]]\nname = "drap"\n'
        'url = "https://services.swpc.noaa.gov/text/drap_global_frequencies.txt"\n'
    )
    assert product.ext == "txt"


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        ('[[product]]\nname = "a"\n', "url"),
        ('[[product]]\nurl = "https://x/a.json"\n', "name"),
        ('[[product]]\nname = "a/b"\nurl = "https://x/a.json"\n', "name"),
        ('[[product]]\nname = "a"\nurl = "https://x/a"\n', "extension"),
        ('[[product]]\nname = "a"\nurl = "http://x/a.json"\n', "https"),
        (
            '[[product]]\nname = "a"\nurl = "https://x/a.json"\n'
            '[[product]]\nname = "a"\nurl = "https://x/b.json"\n',
            "twice",
        ),
        (
            '[[product]]\nname = "a"\nurl = "https://x/a.json"\n'
            "reduce = { head = 1, tail = 1, every = 0 }\n",
            "every",
        ),
        (
            '[[product]]\nname = "a"\nurl = "https://x/a.txt"\n'
            "reduce = { head = 1, tail = 1, every = 2 }\n",
            "JSON",
        ),
        (
            '[[product]]\nname = "a"\nurl = "https://x/a.json"\n'
            "reduce = { head = 1, tail = 1, every = 2, sample = 3 }\n",
            "sample",
        ),
    ],
)
def test_load_products_rejects_bad_entries(toml: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        rf.load_products(toml)


def test_repository_product_list_is_valid() -> None:
    products = rf.load_products(rf.DEFAULT_LIST.read_text(encoding="utf-8"))
    names = {p.name for p in products}
    assert "kp-3h" in names
    assert "ovation-aurora" in names
    assert all(p.url.startswith("https://services.swpc.noaa.gov/") for p in products)


# --- content checks ---------------------------------------------------------


def test_check_content_accepts_json_and_text() -> None:
    rf.check_content(b'[{"a": 1}]', "application/json", "json")
    rf.check_content(b":Product: x\n", "text/plain", "txt")


@pytest.mark.parametrize(
    ("raw", "content_type", "ext", "message"),
    [
        (b"", "application/json", "json", "empty"),
        (b"  \n", "text/plain", "txt", "empty"),
        (b"<!DOCTYPE html><html></html>", "application/json", "json", "HTML"),
        (b"[1, 2]", "text/html; charset=utf-8", "json", "HTML"),
        (b'[{"a": 1}, {"a"', "application/json", "json", "JSON"),
        (b"\n  <html>", "text/plain", "txt", "HTML"),
    ],
)
def test_check_content_rejects_bad_downloads(
    raw: bytes, content_type: str, ext: str, message: str
) -> None:
    with pytest.raises(rf.RecordError, match=message):
        rf.check_content(raw, content_type, ext)


def test_check_content_accepts_json_with_bom() -> None:
    rf.check_content(b'\xef\xbb\xbf[{"a": 1}]', "application/json", "json")


# --- reduction --------------------------------------------------------------


def _dumps(value: object) -> bytes:
    return json.dumps(value).encode()


def test_reduce_keeps_head_tail_and_every_nth_group() -> None:
    records = [{"time_tag": t, "v": t} for t in range(10)]
    reduced = rf.reduce_json(
        _dumps(records), rf.Reduction(head=2, tail=1, every=4, group="time_tag")
    )
    assert [r["v"] for r in json.loads(reduced)] == [0, 1, 4, 8, 9]


def test_reduce_keeps_whole_groups() -> None:
    records = [
        {"time_tag": "a", "source": "S"},
        {"time_tag": "a", "source": "A"},
        {"time_tag": "b", "source": "S"},
        {"time_tag": "c", "source": "S"},
        {"time_tag": "c", "source": "A"},
    ]
    reduced = rf.reduce_json(
        _dumps(records), rf.Reduction(head=1, tail=1, every=100, group="time_tag")
    )
    assert json.loads(reduced) == [records[0], records[1], records[3], records[4]]


def test_reduce_without_group_samples_single_elements() -> None:
    reduced = rf.reduce_json(
        _dumps(list(range(7))), rf.Reduction(head=1, tail=1, every=3)
    )
    assert json.loads(reduced) == [0, 3, 6]


def test_reduce_array_inside_object_by_index_group() -> None:
    grid = {
        "Observation Time": "2026-10-15T17:39:00Z",
        "coordinates": [[lon, lat, 0] for lon in range(6) for lat in (-1, 0, 1)],
    }
    reduced = json.loads(
        rf.reduce_json(
            _dumps(grid),
            rf.Reduction(head=1, tail=1, every=2, group=0, array="coordinates"),
        )
    )
    assert reduced["Observation Time"] == "2026-10-15T17:39:00Z"
    assert sorted({c[0] for c in reduced["coordinates"]}) == [0, 2, 4, 5]
    assert len(reduced["coordinates"]) == 4 * 3


def test_reduce_keeps_source_formatting() -> None:
    raw = b'[{"t": 1, "flux": 5.919231771400746e-09}, {"t": 2, "flux": 1e-05}]'
    reduced = rf.reduce_json(raw, rf.Reduction(head=5, tail=5, every=1))
    assert reduced == raw


def test_reduce_refuses_formatting_it_cannot_reproduce() -> None:
    raw = b'[{"Kp":1.00},{"Kp":2.00}]'
    with pytest.raises(rf.RecordError, match="formatting"):
        rf.reduce_json(raw, rf.Reduction(head=1, tail=1, every=1))


def test_reduce_rejects_missing_array() -> None:
    with pytest.raises(rf.RecordError, match="coordinates"):
        rf.reduce_json(
            _dumps({"other": []}),
            rf.Reduction(head=1, tail=1, every=1, array="coordinates"),
        )


def test_reduction_description() -> None:
    r = rf.Reduction(head=30, tail=30, every=30, group="time_tag")
    assert r.describe() == "first 30 and last 30 groups by time_tag, plus every 30th"
    grid = rf.Reduction(head=2, tail=2, every=1, group=0, array="coordinates")
    assert grid.describe() == (
        "coordinates: first 2 and last 2 groups by item 0, plus every 1st"
    )
    plain = rf.Reduction(head=1, tail=1, every=12)
    assert plain.describe() == "first 1 and last 1 elements, plus every 12th"


# --- paths and README -------------------------------------------------------


def test_fixture_path_uses_product_and_utc_date(tmp_path: Path) -> None:
    (product,) = rf.load_products(f'[[product]]\nname = "kp-3h"\nurl = "{URL}"\n')
    assert rf.fixture_path(tmp_path, product, WHEN) == (
        tmp_path / "kp-3h" / "2026-10-15.json"
    )


README = """# Fixtures

Intro.

<!-- recorded:begin -->
| File | Source | Recorded (UTC) | Size (bytes) | Notes |
|---|---|---|---|---|
| `b/2026-10-01.json` | https://x/b.json | 2026-10-01 10:00 | 10 | |
<!-- recorded:end -->

Hand-written section.
"""


def test_update_readme_adds_and_sorts_rows() -> None:
    row = rf.Row("a/2026-10-15.json", URL, WHEN, 42, "")
    text = rf.update_readme(README, [row])
    table = text.split("<!-- recorded:begin -->")[1].split("<!-- recorded:end -->")[0]
    lines = [line for line in table.splitlines() if line.startswith("| `")]
    assert lines == [
        f"| `a/2026-10-15.json` | {URL} | 2026-10-15 17:52 | 42 | |",
        "| `b/2026-10-01.json` | https://x/b.json | 2026-10-01 10:00 | 10 | |",
    ]
    assert text.endswith("Hand-written section.\n")


def test_update_readme_replaces_existing_row() -> None:
    row = rf.Row("b/2026-10-01.json", "https://x/b.json", WHEN, 99, "reduced")
    text = rf.update_readme(README, [row])
    assert "| 10 |" not in text
    assert (
        "| `b/2026-10-01.json` | https://x/b.json | 2026-10-15 17:52 | 99 | reduced |"
    ) in text


def test_update_readme_requires_markers() -> None:
    with pytest.raises(rf.RecordError, match="marker"):
        rf.update_readme("# Fixtures\n", [])


# --- recording end to end, with a fake download -----------------------------


def test_record_writes_files_and_readme(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    products = rf.load_products(
        f'[[product]]\nname = "kp-3h"\nurl = "{URL}"\n'
        '[[product]]\nname = "rtsw"\nurl = "https://x/rtsw.json"\n'
        'reduce = { group = "time_tag", head = 1, tail = 1, every = 10 }\n'
    )
    bodies = {
        URL: b'[{"time_tag":"2026-10-15T12:00:00","Kp":2.67}]',
        "https://x/rtsw.json": _dumps([{"time_tag": t} for t in range(5)]),
    }

    def fake_fetch(url: str) -> tuple[bytes, str]:
        return bodies[url], "application/json"

    rows = rf.record(products, tmp_path, fake_fetch, WHEN)

    kp = tmp_path / "kp-3h" / "2026-10-15.json"
    assert kp.read_bytes() == bodies[URL]
    rtsw = tmp_path / "rtsw" / "2026-10-15.json"
    assert json.loads(rtsw.read_bytes()) == [{"time_tag": 0}, {"time_tag": 4}]
    assert [r.path for r in rows] == ["kp-3h/2026-10-15.json", "rtsw/2026-10-15.json"]
    assert rows[1].notes.startswith(
        f"reduced from {len(bodies['https://x/rtsw.json'])}"
    )
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "`kp-3h/2026-10-15.json`" in readme
    assert "`rtsw/2026-10-15.json`" in readme


def test_record_writes_nothing_when_a_download_is_bad(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    products = rf.load_products(
        f'[[product]]\nname = "good"\nurl = "{URL}"\n'
        '[[product]]\nname = "bad"\nurl = "https://x/bad.json"\n'
    )

    def fake_fetch(url: str) -> tuple[bytes, str]:
        if url == URL:
            return b"[]", "application/json"
        return b"<html>moved</html>", "text/html"

    with pytest.raises(rf.RecordError, match="bad"):
        rf.record(products, tmp_path, fake_fetch, WHEN)
    assert not (tmp_path / "good").exists()
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == README


def test_record_rejects_naive_time(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="UTC"):
        rf.record([], tmp_path, lambda url: (b"", ""), datetime(2026, 1, 1))  # noqa: DTZ001
