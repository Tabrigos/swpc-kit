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

## JSON and tables

`to_dict` turns any model into plain data for `json.dumps`, with times in
ISO 8601 and `Z`. `to_records` turns a product into flat rows, one per
record, with times kept as UTC `datetime`: ready for `csv.DictWriter` or
`pandas.DataFrame(rows)`, without depending on pandas.

```pycon
>>> from swpc_kit.export import to_dict, to_records
>>> from swpc_kit.parse import parse_kyoto_dst
>>> dst = parse_kyoto_dst(Path("tests/fixtures/dst/2026-10-15.json").read_bytes())
>>> to_dict(dst)["values"][-1]
{'time': '2026-10-15T17:00:00Z', 'dst': -20}
>>> to_records(dst)[-1]
{'time': datetime.datetime(2026, 10, 15, 17, 0, tzinfo=datetime.timezone.utc), 'dst': -20}
```

The rows of a product are its `values`; for the alerts its `messages`, for
the NOAA scales and the 27-day outlook its `days`, for the 3-day and
geomagnetic forecasts their Kp periods, for a grid its cells. A nested model
becomes prefixed columns (`g_scale`, `noaa_scale_level`). `to_records` also
takes a sequence of records, such as `wind.active_series()`. Both keep the
fields only: properties such as `data_time` stay on the model.

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
>>> drap.grid.value_near(-11.6, 300.8)  # the cell that holds the point
8.5
```

`value_near` takes longitudes in either convention and gives `None` for a
point no cell holds (outside the grid, or in a gap of a reduced OVATION
file).

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

`AsyncClient` parses in a thread, so a large file (the OVATION grid) does
not block the event loop.

`timeout` (30 seconds by default) applies to each phase of a request, as
httpx2 does: connecting, sending, and each wait for the next piece of the
reply. It is not a limit on the whole call. For one, wrap an `AsyncClient`
call in `asyncio.timeout()`. The arguments of both clients are checked
when the client is built: `timeout="30"` is a `TypeError` that says what it
wants.

### When SWPC moves a product or changes a format

- **A product that moved** answers `UnexpectedContent`, with `status` (301,
  404…) and, for a redirect, `location`. The client never follows redirects.
  Until a new version of swpc-kit knows the new address, give it to the
  client: `Client(urls={"kyoto_dst": "https://..."})`. The parsers also work
  on content you downloaded yourself, with `source_url=`.
- **A format that changed** in a way no parser knows (a field that is gone
  from every record, HTML, an unknown shape) is `UnexpectedContent`:
  stop and report it, a new version is needed. A known format with an
  inconsistent value is `ParseError`, which names the field and the record or
  line. Each parser reads every format of its product documented in
  `docs/FONTI.md`, old and new.
- Every error that goes through the client says which product and URL it
  comes from, in the message and in its `product` and `url` attributes.

### Records that could not be read

The products made of records (indices, solar wind, GOES, alerts) are read
record by record: one record with an impossible value, a repeated time or a
missing field goes to the model's `skipped` (index, field, reason) and the
others are read, so one bad record does not hide the whole file for the
hours or days it stays there. The product fails only when no record can be
read. The client logs a warning on the `swpc_kit.client` logger for each
product with skipped records. Bulletins and grids stay strict. The limits of
what is plausible are in `docs/FONTI.md`, "Plausibility limits".

## For AI assistants

The package ships an [Agent Skill](https://agentskills.io) for AI coding
assistants (Claude Code and others that read `SKILL.md` files) in
`swpc_kit/skill/swpc-kit/`, versioned with the package. It is plain Markdown:
`SKILL.md` is a hand-written guide, and `references/api.md` next to it lists
every model, field and method, generated from the code. The test suite fails
if either falls behind the code.

Assistants look for skills in the project, not inside installed packages. A
project copies the skill into `.claude/skills/swpc-kit/`, keeps the copy in
git and checks it against the installed version by hash, so the assistant
reads the guide of the version it actually uses:

```bash
python -m swpc_kit.skill install --target .claude/skills/swpc-kit
python -m swpc_kit.skill check   # exit 1 if the copy differs from the package
```

`install` writes only into `.claude/skills/swpc-kit` or
`.agents/skills/swpc-kit`, and never replaces a directory it did not write.
Run `check` in CI; after upgrading swpc-kit, run `install` again and review
the diff like any other change.

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
