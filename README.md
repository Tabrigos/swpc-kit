# swpc-kit

Typed Python readers for the public data products of NOAA's Space Weather
Prediction Center: indices, solar wind, GOES, alerts, text bulletins, and the
OVATION and D-RAP grids, with GeoJSON and GeoTIFF export.

**Status: in development, not released.** The index parsers (Kp, Dst,
F10.7, NOAA scales) are in; the rest is in progress. See `SPEC.md` for what
the library will do and `docs/TAPPE.md` for the plan.

## Design

- **Parsers** (`swpc_kit.parse`): pure functions from raw `str`/`bytes` to
  models, standard library only, no I/O.
- **Models** (`swpc_kit.models`): frozen dataclasses with UTC `datetime`
  fields and the time the content declares (`data_time`).
- **Outputs**: GeoJSON export (standard library), GeoTIFF export (`geo`
  extra), and an HTTP client (`client` extra).
- **Typed errors** under `SwpcError`: `SourceNotReady` (truncated or empty
  data, try again later), `UnexpectedContent` (an HTML page or an unknown
  format), `ParseError` (a known format with an inconsistent value), and
  `StaleData` (older than the age the caller accepts).

## Development

Requires Python 3.12 or later and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Tests never use the network: they read the files in `tests/fixtures/`.

## Data and attribution

Data comes from NOAA SWPC (https://www.swpc.noaa.gov). This project is not
affiliated with or endorsed by NOAA.
