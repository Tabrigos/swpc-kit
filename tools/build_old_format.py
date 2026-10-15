"""Build old-format fixtures from recorded new-format ones.

Until about 2026-03-31 (SCN 26-21) several SWPC products were arrays of
arrays: a first row with the column names, then one row per record with the
numbers quoted as strings. No real file of Dst or F10.7 in that format was
available, so this script rewrites a recorded file into it, keeping the same
values, so that a parser can be checked to give the same model for both.

The conversion follows the official 2022 Kp sample
(``tests/fixtures/kp-3h/2022-09-22-sample.json``): compact separators,
``time_tag`` as ``YYYY-MM-DD HH:MM:SS`` (with ``.000`` when ``--millis`` is
given), numbers quoted exactly as written in the source, ``null`` kept.

Usage::

    uv run python tools/build_old_format.py SOURCE TARGET [--millis]
"""

import argparse
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path

_TIME_TAG = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})")


def _old_time_tag(value: object, millis: bool) -> str:
    if not isinstance(value, str):
        raise ValueError(f"time_tag is not a string: {value!r}")
    match = _TIME_TAG.fullmatch(value)
    if match is None:
        raise ValueError(f"time_tag not in YYYY-MM-DDTHH:MM:SS form: {value!r}")
    return f"{match[1]} {match[2]}{'.000' if millis else ''}"


def to_old_format(raw: bytes, *, millis: bool) -> bytes:
    """Rewrite an array of objects as a header row plus rows of strings.

    Args:
        raw: A new-format product: a JSON array of objects with ``time_tag``.
        millis: Whether ``time_tag`` gets a ``.000`` suffix.

    Returns:
        The old-format document, compactly serialised.

    Raises:
        ValueError: If the document is not a non-empty array of objects with
            the same keys, or a ``time_tag`` has an unexpected form.
    """
    # Numbers stay as their source text, so 1.00 becomes "1.00", not "1.0".
    records = json.loads(raw, parse_float=str, parse_int=str)
    if (
        not isinstance(records, list)
        or not records
        or not all(isinstance(r, dict) for r in records)
    ):
        raise ValueError("expected a non-empty array of objects")
    columns = list(records[0])
    rows: list[list[object]] = [list(columns)]
    for index, record in enumerate(records):
        if list(record) != columns:
            raise ValueError(f"record {index} has different keys: {list(record)}")
        rows.append(
            [
                _old_time_tag(value, millis) if key == "time_tag" else value
                for key, value in record.items()
            ]
        )
    return json.dumps(rows, separators=(",", ":")).encode("utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the builder from the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--millis", action="store_true")
    args = parser.parse_args(argv)
    args.target.write_bytes(to_old_format(args.source.read_bytes(), millis=args.millis))
    return 0


if __name__ == "__main__":
    sys.exit(main())
