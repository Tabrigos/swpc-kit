# swpc-kit

Typed Python readers for the public data products of NOAA's Space Weather
Prediction Center: indices, solar wind, GOES, alerts, text bulletins, and the
OVATION and D-RAP grids, with GeoJSON and GeoTIFF export.

**Status: beta.** 0.3.0 is the first version published on PyPI; the API
may still change before 1.0, and every change is in `CHANGELOG.md`. See
`SPEC.md` for what the library does and does not do, and `docs/FONTI.md`
for what is known about each SWPC format.

## Install

Requires Python 3.12 or later; the tests run on Linux and Windows.

```bash
pip install swpc-kit              # parsers, models, JSON, GeoJSON, GeoTIFF
pip install "swpc-kit[client]"    # plus the HTTP client (httpx2)
```

The library uses only the standard library, GeoTIFF export included; the
`client` extra adds only httpx2.

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
every time an aware UTC `datetime`. Each model has `data_time`, the time its
data describes and never a forecast time (the last observed value, the
observation time of a grid, the issue time of a bulletin; the docstring of
each model says which), and `source_url`.

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

Every error about the data or the source is a `swpc_kit.SwpcError` (a
mistake in the call is a `TypeError` or a `ValueError`). `SourceNotReady`
means try again later (SWPC sometimes serves a file while rewriting it);
its subclass `RateLimited` is a `429`, a refusal that waits for the next
run. `UnexpectedContent` means
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

GeoTIFF, which GDAL, rasterio and QGIS open:

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
Requests are conditional: when the `ETag` of a file has not changed, SWPC
answers `304 Not Modified` and the previous model is reused. The `ETag` may
also change when the content does not, so a `304` is a saving, not a
promise.

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

### Trying again

`SourceNotReady` is the only error worth retrying: SWPC is busy (`5xx`), the
network failed, or the file was caught while SWPC was rewriting it. Wait, and
wait longer each time; give up after a few attempts.

A `429` raises `RateLimited`, a subclass of `SourceNotReady`, but it is a
refusal: SWPC asks you to slow down. Do not retry it in the same run: stop,
try at the next run of your job, and make the runs less frequent.
`retry_after` holds the `Retry-After` header, if SWPC sent one.

```python
import time

from swpc_kit import RateLimited, SourceNotReady
from swpc_kit.client import Client


def fetch_with_retry(fetch, attempts=4, wait=30.0):
    """Call fetch(); on SourceNotReady wait and try again, doubling the wait."""
    for attempt in range(attempts):
        try:
            return fetch()
        except RateLimited:
            raise  # a refusal: stop until the next run
        except SourceNotReady:
            if attempt == attempts - 1:
                raise
            time.sleep(wait * 2**attempt)


with Client() as client:
    dst = fetch_with_retry(client.kyoto_dst)
    print(dst.values[-1].dst)
```

Do not retry `UnexpectedContent` or `ParseError` in a loop: the answer will
be the same until SWPC or swpc-kit changes. `StaleData` means SWPC has not
updated the product yet: try at the next run of your job, not within
seconds. The client does not wait for `Retry-After` and keeps its `ETag`s
in memory only, so keep one `Client` for the life of your program.

### Downloading with your own code

The client sends its requests through a transport, httpx2 by default. To
send them another way and keep the rest of the client, pass
`transport=`: any object with `get(url, *, headers, timeout)`, which
returns an `HttpResponse`, and `close()` (`aclose()` for `AsyncClient`).
It must not follow redirects, and must raise `SourceNotReady` when SWPC
cannot be reached.

If your program already downloads through a layer of its own (a scheduler,
a rate limiter, a cache), keep it and use the parsers. `check_response`
reads the status and the headers the way the client does, with no network:

```python
from pathlib import Path

from swpc_kit.http import check_response
from swpc_kit.parse import parse_planetary_k_index

# The status, headers and body that your own code downloaded.
url = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
status, headers = 200, {"Content-Type": "application/json"}
body = Path("tests/fixtures/kp-3h/2026-10-15.json").read_bytes()

check_response(status, headers, url=url)
kp = parse_planetary_k_index(body, source_url=url)
print(kp.values[-1].kp)
```

- It returns for a **200** that is not an HTML page. A `SourceNotReady`
  from the parser after that is a file caught while SWPC was rewriting it:
  try again later, by the rules of your layer.
- **408, 425, 5xx** (and a timeout or a network failure, which your code
  sees first) raise `SourceNotReady`: try again later. If your layer
  records failures and pauses the host, "later" is its next run, never a
  loop in the same process.
- **429** raises `RateLimited`: slow down, honour `retry_after`, and do not
  retry in the same run.
- **A redirect, a 404 or any other status**, or an HTML page, raise
  `UnexpectedContent`: stop. SWPC moved or changed the product, or the URL
  is wrong.
- **304** raises `ValueError`: only your code holds the copy it refers to.

Then measure the age on `data_time`, not on the HTTP headers: a `304` or a
recent `Last-Modified` does not say that the data is new.

### With a politefetch gate

[politefetch](https://pypi.org/project/politefetch/) keeps a program polite
to a source: a daily cap, a minimum interval, a pause after failures, a
host frozen after a `429`, all recorded across restarts. swpc-kit does not
depend on it; the two meet in your code. The gate must hear about a body
that the parser refused, without keeping its `ETag`: otherwise the next
conditional request gets a `304` for a broken file.

```python
from swpc_kit import SourceNotReady, SwpcError
from swpc_kit.http import check_response


def fetch_politely(gate, http, url, parse, copy=None):
    """Download url through gate.attempt() and parse it; copy answers a 304."""
    with gate.attempt(url) as attempt:
        # Without a copy, a 304 would be of no use: ask for the whole body.
        headers = attempt.conditional_headers if copy is not None else {}
        response = http.get(url, headers=headers)
        status = response.status_code
        if status == 304 and copy is not None:
            attempt.response(status, headers=response.headers)
            return copy
        try:
            check_response(status, response.headers, url=url)
            model = parse(response.content, source_url=url)
        except SwpcError as error:
            if not 200 <= status < 300:
                # The gate reads the status: a 429 freezes, a 5xx pauses.
                attempt.response(status, headers=response.headers)
            else:
                # The gate takes any 2xx as a good answer: a refused body is
                # a failure instead, and its validators are not kept.
                ready = isinstance(error, SourceNotReady)
                shape = "not_ready" if ready else "unexpected_content"
                attempt.failure(shape, status=status, headers=response.headers)
            raise
        attempt.response(status, headers=response.headers)
        return model
```

`http` is your HTTP client (httpx, for instance) and `parse` one of the
parsers. In async code, write `async with` and `await`.

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
