# swpc-kit — specification

## Goal

A Python library that turns the public products of NOAA SWPC
(`services.swpc.noaa.gov`) into typed models, reliable when the source changes
format, stops or responds badly, and that exports the grids (OVATION, D-RAP)
to GeoJSON and GeoTIFF.

Who uses it: a backend that ingests space weather data (for example a FastAPI
service), an analysis script, a notebook.

## What it does not do

- No charts, no interface, no database or on-disk cache.
- No physical models or forecasts of its own: it reads what SWPC publishes.
- No products from other agencies (NASA DONKI, iSWA, GFZ) in the first version.
- No images (coronagraphs, SUVI, animations).

## Architecture

Three layers, each usable on its own, plus the skill that describes them:

1. **Parsers** (`swpc_kit.parse.*`): pure functions, `str | bytes` → model.
   Standard library only.
2. **Models** (`swpc_kit.models.*`): frozen, typed dataclasses, with UTC
   `datetime`. Each product has a model with `issued` / `observed` /
   `valid_from` / `valid_to` where the source provides them, and `source_url`.
3. **Outputs**:
   - `swpc_kit.export.data` (standard library): `to_dict` for JSON and
     `to_records` for tables;
   - `swpc_kit.export.geojson` (standard library);
   - `swpc_kit.export.geotiff` (`geo` extra, with `numpy` and `rasterio`);
   - `swpc_kit.client` (`client` extra, with `httpx2`, the maintained
     continuation of httpx: see `docs/FONTI.md`): downloads, recognizes the
     source's errors, calls the parser.
4. **Skill for AI assistants** (`swpc_kit/skill/`): instructions in the Agent
   Skills format (`SKILL.md` written by hand, `references/api.md` generated
   from the code), versioned with the package; the tests keep them aligned with
   the API. It follows the shared standard for library skills (schema 1), the
   same in the other packages by the same author (for example politefetch):
   - `swpc_kit/skill/__init__.py` is a copy of the shared module: only the
     constants above its dividing line are this package's, and a test checks
     the fingerprint of the rest;
   - `python -m swpc_kit.skill path | show | check | install --target DIR`.
     Only `install` writes, and only into `.claude/skills/swpc-kit` or
     `.agents/skills/swpc-kit`; it replaces a directory only if it holds the
     `.skill-libreria.json` marker of this package;
   - a project keeps its copy in git and compares it with the installed
     package by content hash (line endings normalized), never by version.
     Nothing discovers skills among the installed packages: the project lists
     the libraries it wants;
   - skills live only in projects, never in `~/.claude/skills`.

```python
from swpc_kit.client import Client
from swpc_kit.export import to_geojson
from swpc_kit.parse import parse_planetary_k_index

kp = parse_planetary_k_index(raw_bytes)  # no network
with Client() as c:
    kp = c.planetary_k_index()  # network
    oval = c.ovation_aurora()
    to_geojson(oval, threshold=10)
```

The exact names are decided in the stages; this is the framework.

## Products in the first version

| Group | Products | Stage |
|---|---|---|
| Indices | 3-hour Kp and forecast, 1-minute Kp, F10.7, Kyoto Dst, NOAA scales (`noaa-scales.json`) | T2 |
| Solar wind | 1-minute RTSW mag and plasma (SOLAR-1, ACE), with choice of the active source | T3 |
| GOES | X-ray flux (with flare class A/B/C/M/X), integral protons | T3 |
| Alerts | `alerts.json`, parsing of the message text, code catalog | T4 |
| Bulletins | 3-day forecast, geomagnetic forecast, 27-day outlook | T5 |
| Grids | OVATION aurora, D-RAP | T6 |

## Errors

A hierarchy under `SwpcError`:

- `SourceNotReady`: truncated or empty data (unclosed JSON, half-written file).
  It really happens: SWPC sometimes serves a file while rewriting it. It is a
  transient state, not a bug: the caller retries later.
- `UnexpectedContent`: the source responds with something else (an HTML page,
  a redirect to an announcements page, a format that no parser knows).
- `ParseError`: the format is the expected one but a field is inconsistent. The
  message says which field and which line.
- `StaleData` (only in the client, and only if the caller passes a maximum
  age): the data is older than expected.

## Freshness

The age of the data is measured **on the time the content declares**
(`Observation Time`, `:Issued:`, the last `time_tag`), never on the HTTP
outcome: a `304 Not Modified` or a recent modification date does not say that
the data is new. Every model exposes `data_time` (the most recent time in the
content), and the client accepts `max_age`.

## Changing formats

SWPC changes its formats with advance notice (the SCNs, *Service Change
Notices*). In 2026 the 3-hour Kp and other products moved from "array of arrays
with the header row" to "array of objects", with the numbers no longer in
quotes. A parser recognizes **all** the formats documented in `docs/FONTI.md`
and returns the same model.

## Quality

- Python 3.12 or later; `uv` for environment and build (`hatchling`).
- `mypy --strict`, `ruff check`, `ruff format`, `pytest` clean; CI on GitHub
  Actions that runs the same commands.
- Every parser has tests on real fixtures and on hand-built edge cases (missing
  field, truncated, out-of-range values, inactive source).
- Public API documented in the docstrings; README with runnable examples; skill
  for AI assistants with examples run by the tests.

## License

MIT (`LICENSE`), copyright Sidereus Team. SWPC data is public and is not
covered by the license; NOAA asks for attribution and not to imply its
endorsement: the README says so.
