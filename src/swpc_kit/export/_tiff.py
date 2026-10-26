"""The TIFF container behind :mod:`swpc_kit.export.geotiff`.

:func:`encode` lays out a little-endian classic TIFF with one image: the
header, one directory of tags, the tag values that do not fit in their
entry, then the strips of pixel data. It knows nothing about GeoTIFF or
GDAL: the caller chooses the tags and compresses the strips.
"""

import struct
from collections.abc import Sequence

__all__ = ["ASCII", "DOUBLE", "LONG", "SHORT", "STRIP_OFFSETS", "encode"]

ASCII = 2
SHORT = 3
LONG = 4
DOUBLE = 12

STRIP_OFFSETS = 273
"""The tag whose values :func:`encode` fills in: where each strip starts."""

_FORMATS = {SHORT: "H", LONG: "I", DOUBLE: "d"}

type Entry = tuple[int, int, Sequence[int] | Sequence[float] | str]
"""A tag: its number, its TIFF type and its values (text for ``ASCII``)."""


def _pack(kind: int, values: Sequence[int] | Sequence[float] | str) -> bytes:
    if isinstance(values, str):
        return values.encode("ascii") + b"\0"
    return struct.pack(f"<{len(values)}{_FORMATS[kind]}", *values)


def encode(entries: Sequence[Entry], strips: Sequence[bytes]) -> bytes:
    """Return the bytes of a TIFF file with these tags and strips.

    Args:
        entries: The tags of the image, in any order. They must not include
            :data:`STRIP_OFFSETS`, which is computed here.
        strips: The pixel data, one compressed strip per item, top first.
    """
    placeholder: Entry = (STRIP_OFFSETS, LONG, [0] * len(strips))
    tags = sorted([*entries, placeholder], key=lambda entry: entry[0])
    directory_size = 2 + 12 * len(tags) + 4
    # Tag values longer than four bytes go after the directory, each on an
    # even offset; the strips follow them.
    raws = [_pack(kind, values) for _, kind, values in tags]
    spill = sum(len(raw) + len(raw) % 2 for raw in raws if len(raw) > 4)
    start = 8 + directory_size + spill
    offsets = [start + sum(map(len, strips[:i])) for i in range(len(strips))]

    directory = bytearray(struct.pack("<H", len(tags)))
    extra = bytearray()
    for tag, kind, values in tags:
        raw = _pack(kind, offsets if tag == STRIP_OFFSETS else values)
        count = len(raw) if kind == ASCII else len(values)
        if len(raw) <= 4:
            directory += struct.pack("<HHI", tag, kind, count) + raw.ljust(4, b"\0")
        else:
            at = 8 + directory_size + len(extra)
            directory += struct.pack("<HHII", tag, kind, count, at)
            extra += raw + b"\0" * (len(raw) % 2)
    directory += struct.pack("<I", 0)  # no next image
    return b"II*\0" + struct.pack("<I", 8) + directory + extra + b"".join(strips)
