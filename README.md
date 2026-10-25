# swpc-kit

Typed Python readers for the public data products of NOAA's Space Weather
Prediction Center: indices, solar wind, GOES, alerts, text bulletins, and the
OVATION and D-RAP grids, with GeoJSON and GeoTIFF export.

**Status: 0.2.0, not published on PyPI.** See `CHANGELOG.md`, `SPEC.md` for
what the library does and does not do, and `docs/FONTI.md` for what is known
about each SWPC format.

## Install

Requires Python 3.12 or later. From a checkout or straight from GitHub:

```bash
pip install "swpc-kit[client,geo] @ git+https://github.com/Tabrigos/swpc-kit"
```

The core (parsers, models, GeoJSON) uses only the standard library. The
extras add the HTTP client (`client`: httpx2) and the GeoTIFF export (`geo`:
numpy, rasterio).

## Products

| Product | Parser | Client method |
|---|---|---|
| Planetary K index, 3-hour | `parse_planetary_k_index` | `planetary_k_index` |
| Kp observed and forecast | `parse_planetary_k_index_forecast` | `planetary_k_index_forecast` |
| Kp, 1-minute estimates | `parse_planetary_k_index_1m` | `planetary_k_index_1m` |
| Kyoto Dst | `parse_kyoto_dst` | `kyoto_dst` |
| F10.7, 30 days | `parse_f107_flux_30_day` | `f107_flux_30_day` |
| NOAA space weather scales | `parse_noaa_scales` | `noaa_scales` |
| Real-time solar wind, magnetic field | `parse_rtsw_mag_1m` | `rtsw_mag_1m` |
| Real-time solar wind, plasma | `parse_rtsw_wind_1m` | `rtsw_wind_1m` |
| GOES X-ray flux | `parse_goes_xrays` | `goes_xrays` |
| GOES integral protons | `parse_goes_integral_protons` | `goes_integral_protons` |
| Alerts, warnings, watches | `parse_alerts` | `alerts` |
| 3-day forecast | `parse_three_day_forecast` | `three_day_forecast` |
| Geomagnetic forecast | `parse_geomagnetic_forecast` | `geomagnetic_forecast` |
| 27-day outlook | `parse_27_day_outlook` | `twenty_seven_day_outlook` |
| OVATION aurora grid | `parse_ovation_aurora` | `ovation_aurora` |
| D-RAP global frequencies | `parse_drap_global_frequencies` | `drap_global_frequencies` |

Parsers live in `swpc_kit.parse`, models in `swpc_kit.models`, the clients in
`swpc_kit.client`. The examples below run in the test suite
(`tests/test_readme.py`) against the files in `tests/fixtures/`.

## Parse content you already have

Parsers are pure functions: `str` or `bytes` in, a frozen dataclass out, with
every time an aware UTC `datetime`. Each model has `data_time`, the most
recent time its content declares, and `source_url`.

```pycon
>>> from pathlib import Path
>>> from swpc_kit.parse import parse_planetary_k_index
>>> raw = Path("tests/fixtures/kp-3h/2026-10-15.json").read_bytes()
>>> kp = parse_planetary_k_index(raw)
>>> kp.data_time
datetime.datetime(2026, 10, 15, 12, 0, tzinfo=datetime.timezone.utc)
>>> kp.values[-1].kp
2.67
```

SWPC changed several formats in 2026. Old and new formats give the same model:

```pycon
>>> old = Path("tests/fixtures/kp-3h/2026-10-15-built.json").read_bytes()
>>> old[:60]
b'[["time_tag","Kp","a_running","station_count"],["2026-10-08 '
>>> parse_planetary_k_index(old) == kp
True
```

Alerts keep their raw text and get typed fields where the form is known; the
code catalogue says what each message is:

```pycon
>>> from swpc_kit.parse import parse_alerts
>>> alerts = parse_alerts(Path("tests/fixtures/alerts/2026-10-15.json").read_bytes())
>>> message = alerts.messages[0]
>>> message.product_id, message.code, message.serial_number
('K04W', 'WARK04', 5435)
>>> message.valid_to
datetime.datetime(2026, 10, 14, 12, 0, tzinfo=datetime.timezone.utc)
>>> message.info.meaning
'Warning: Geomagnetic K-index of 4 expected'
```

The solar wind models keep every spacecraft and pick the active one; GOES
X-ray samples know their flare class:

```pycon
>>> from swpc_kit.parse import parse_goes_xrays, parse_rtsw_mag_1m
>>> mag = parse_rtsw_mag_1m(Path("tests/fixtures/rtsw-mag-1m/2026-10-15.json").read_bytes())
>>> latest = mag.latest_active()
>>> latest.source, latest.bt, latest.bz_gsm
('SOLAR1', 4.75, 2.13)
>>> xrays = parse_goes_xrays(
...     Path("tests/fixtures/goes-xrays-1-day/2026-10-15.json").read_bytes()
... )
>>> str(xrays.peak().flare_class)
'C3.9'
```

## Errors

Every error is a `swpc_kit.SwpcError`. `SourceNotReady` means try again later
(SWPC sometimes serves a file while rewriting it), `UnexpectedContent` means
the source answered with something else (an HTML page, an unknown format),
`ParseError` names the field and the record or line that is wrong, and
`StaleData` comes from the client's `max_age` check.

```pycon
>>> from swpc_kit import SourceNotReady
>>> parse_planetary_k_index(raw[:100])
Traceback (most recent call last):
  ...
swpc_kit.errors.SourceNotReady: truncated JSON: ...
>>> parse_planetary_k_index(b"<html><body>Moved</body></html>")
Traceback (most recent call last):
  ...
swpc_kit.errors.UnexpectedContent: got HTML or XML instead of JSON
```

## Export the grids

GeoJSON needs only the standard library; longitudes come out in -180…180.

```pycon
>>> from swpc_kit.export import to_geojson
>>> from swpc_kit.parse import parse_drap_global_frequencies
>>> drap = parse_drap_global_frequencies(
...     Path("tests/fixtures/drap/2026-10-15.txt").read_bytes()
... )
>>> drap.grid.quantity, drap.grid.units, drap.grid.shape
('highest affected frequency', 'MHz', (90, 90))
>>> collection = to_geojson(drap, threshold=5)
>>> collection["type"], len(collection["features"])
('FeatureCollection', 1835)
```

GeoTIFF needs the `geo` extra:

```python
from pathlib import Path

from swpc_kit.export.geotiff import write_geotiff
from swpc_kit.parse import parse_drap_global_frequencies

drap = parse_drap_global_frequencies(
    Path("tests/fixtures/drap/2026-10-15.txt").read_bytes()
)
write_geotiff(drap, "drap.tif")  # EPSG:4326, times in the tags
```

## Fetch from SWPC

The client (`client` extra) downloads, classifies the errors of the source,
parses, and checks the age of the data on the time the content declares.
Requests are conditional: an unchanged file comes back as `304 Not Modified`
and the previous model is reused.

```python
from datetime import timedelta

from swpc_kit import StaleData, SwpcError
from swpc_kit.client import Client

with Client(max_age=timedelta(hours=6)) as client:
    try:
        kp = client.planetary_k_index()
    except StaleData as exc:
        print("too old:", exc)
    except SwpcError as exc:
        print("try again later:", exc)
    else:
        print(kp.data_time, kp.values[-1].kp)
```

The same with `asyncio`:

```python
import asyncio

from swpc_kit.client import AsyncClient


async def main() -> None:
    async with AsyncClient() as client:
        dst, alerts = await asyncio.gather(client.kyoto_dst(), client.alerts())
        print(dst.values[-1].dst, len(alerts.messages))


asyncio.run(main())
```

## For AI assistants

The package ships an [Agent Skill](https://agentskills.io) that tells coding
assistants (Claude Code and others that read `SKILL.md` files) how to use the
library, so they do not have to read its source. It is plain Markdown: the
guide is `src/swpc_kit/skill/swpc-kit/SKILL.md`, and `references/api.md` next
to it lists every model, field and method, generated from the code. The skill
carries the version of the package it describes, and the test suite fails if
it falls behind the code.

Assistants look for skills in the project, not inside installed packages.
The simplest way to keep the right copy there is a `SessionStart` hook in the
project's `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$CLAUDE_PROJECT_DIR\" && uv run --quiet python -m swpc_kit.skill sync"
          }
        ]
      }
    ]
  }
}
```

(Without uv, use the project's interpreter: `.venv/bin/python -m
swpc_kit.skill sync`.) At every session start, `sync` copies the skill of
each installed package that ships one into `.claude/skills/<name>/`, updates
copies whose version changed, removes those of packages no longer installed,
and prints one line such as `skills: swpc-kit 0.2.0`. It never makes the
session fail: problems go to stderr as warnings. The copies it creates hold a
`.gitignore` that keeps them out of git, and a `.package-skill` file that
marks them as managed; a skill directory without that file is never touched.

To keep a copy under version control instead, install it by hand and refresh
it after upgrading:

```bash
python -m swpc_kit.skill install   # into .claude/skills/swpc-kit/
python -m swpc_kit.skill check     # is the installed copy current?
```

Other packages can take part: a package declares its skill in the
`agent_skills` entry point group, pointing at a module with a `bundled()`
function that returns the skill directory (see `swpc_kit/skill/__init__.py`
and the `[project.entry-points.agent_skills]` table in `pyproject.toml`).

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Tests never use the network: they read the files in `tests/fixtures/`
(recorded from SWPC, see `tests/fixtures/README.md`).

`SPEC.md`, `AGENTS.md` and `docs/FONTI.md` are in English. The development
history (`docs/TAPPE.md`, `docs/DIARIO.md`) is in Italian.

## Data and attribution

Data comes from NOAA SWPC (https://www.swpc.noaa.gov). This project is not
affiliated with or endorsed by NOAA.

## License

The code is MIT, see `LICENSE`. The SWPC data, including the fixtures
recorded in `tests/fixtures/`, are public NOAA products and are not covered
by this license.
