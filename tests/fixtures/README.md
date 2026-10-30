# Fixtures

Raw SWPC content used by the tests. Tests read these files and never use the
network. Data comes from NOAA SWPC (https://www.swpc.noaa.gov).

Files are kept byte for byte as served (`.gitattributes` turns off line-ending
conversion here), except the reductions described below. Five kinds of files
live in `tests/fixtures/<product>/`:

- `<YYYY-MM-DD>.<ext>`: **recorded** by `tools/record_fixtures.py` on that
  UTC date;
- `<YYYY-MM-DD>-live.<ext>`: **live**, downloaded on that UTC date at the
  moment a rare case was happening, kept as served (the recorder never
  writes these names, so a new recording cannot replace them);
- `<YYYY-MM-DD>-sample.<ext>`: **official sample** copied from SWPC, dated as
  listed on the SWPC server;
- `<YYYY-MM-DD>-built.<ext>`: **built** for the tests, dated when built;
- `<YYYY-MM-DD>-shared.<ext>`: **shared** by a user of the library, who
  downloaded it from SWPC on that UTC date, copied unchanged.

The whole directory must stay under 2 MiB (`tests/test_fixtures.py` checks it,
and that every file is listed in this README).

## Recorded

Re-record every product, or only some, with:

```bash
uv run python tools/record_fixtures.py
uv run python tools/record_fixtures.py kp-3h alerts
```

The product list is `tools/fixtures.toml`. The script refuses empty, HTML or
truncated downloads and writes nothing unless every product checks out; then
it rewrites the table below.

**Reductions.** Large JSON products are reduced by the same script, as set in
`tools/fixtures.toml`: it groups consecutive records sharing a key (the
`time_tag`, so all sources or energy bands of one instant stay together; for
OVATION, the longitude, so each kept longitude has all 181 latitudes), then
keeps the first and last groups plus every n-th group in between. The JSON is
re-serialised only when that reproduces the source formatting byte for byte,
so the kept records are exactly as served. Re-running the script re-downloads
and re-reduces; the reduction of a given file cannot be redone without the
original, which is not kept.

<!-- recorded:begin -->
| File | Source | Recorded (UTC) | Size (bytes) | Notes |
|---|---|---|---|---|
| `27-day-outlook/2026-10-15.txt` | https://services.swpc.noaa.gov/text/27-day-outlook.txt | 2026-10-15 17:57 | 1606 | |
| `3-day-forecast/2026-10-15.txt` | https://services.swpc.noaa.gov/text/3-day-forecast.txt | 2026-10-15 17:57 | 1919 | |
| `alerts/2026-10-15.json` | https://services.swpc.noaa.gov/products/alerts.json | 2026-10-15 17:57 | 53209 | |
| `drap/2026-10-15.txt` | https://services.swpc.noaa.gov/text/drap_global_frequencies.txt | 2026-10-15 17:57 | 42465 | |
| `dst/2026-10-15.json` | https://services.swpc.noaa.gov/products/kyoto-dst.json | 2026-10-15 17:57 | 7523 | |
| `f107-30-day/2026-10-15.json` | https://services.swpc.noaa.gov/products/10cm-flux-30-day.json | 2026-10-15 17:57 | 1370 | |
| `geomag-forecast/2026-10-15.txt` | https://services.swpc.noaa.gov/text/3-day-geomag-forecast.txt | 2026-10-15 17:57 | 879 | |
| `goes-electrons-1-day/2026-10-29.json` | https://services.swpc.noaa.gov/json/goes/primary/integral-electrons-1-day.json | 2026-10-29 14:27 | 4738 | reduced from 29477 bytes: first 12 and last 12 groups by time_tag, plus every 12th |
| `goes-flares-7-day/2026-10-29.json` | https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json | 2026-10-29 14:27 | 20287 | |
| `goes-flares-latest/2026-10-29.json` | https://services.swpc.noaa.gov/json/goes/primary/xray-flares-latest.json | 2026-10-29 14:27 | 420 | |
| `goes-protons-1-day/2026-10-15.json` | https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json | 2026-10-15 17:57 | 38825 | reduced from 241538 bytes: first 12 and last 12 groups by time_tag, plus every 12th |
| `goes-xrays-1-day/2026-10-15.json` | https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json | 2026-10-15 17:57 | 58813 | reduced from 655036 bytes: first 30 and last 30 groups by time_tag, plus every 20th |
| `kp-1m/2026-10-15.json` | https://services.swpc.noaa.gov/json/planetary_k_index_1m.json | 2026-10-15 17:57 | 27925 | |
| `kp-3h/2026-10-15.json` | https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json | 2026-10-15 17:57 | 4724 | |
| `kp-forecast/2026-10-15.json` | https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json | 2026-10-15 17:57 | 6906 | |
| `noaa-scales/2026-10-15.json` | https://services.swpc.noaa.gov/products/noaa-scales.json | 2026-10-15 17:57 | 1099 | |
| `ovation-aurora/2026-10-15.json` | https://services.swpc.noaa.gov/json/ovation_aurora_latest.json | 2026-10-15 17:57 | 38253 | reduced from 924383 bytes: coordinates: first 2 and last 2 groups by item 0, plus every 30th |
| `rtsw-mag-1m/2026-10-15.json` | https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json | 2026-10-15 17:57 | 94537 | reduced from 1466951 bytes: first 30 and last 30 groups by time_tag, plus every 30th |
| `rtsw-wind-1m/2026-10-15.json` | https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json | 2026-10-15 17:57 | 162894 | reduced from 2441848 bytes: first 30 and last 30 groups by time_tag, plus every 30th |
<!-- recorded:end -->

## Official samples

Example files published by SWPC with its Service Change Notices
(`https://services.swpc.noaa.gov/text/scn/`), copied unchanged on 2026-10-15.

| File | Source | Listed on | Size (bytes) | Notes |
|---|---|---|---|---|
| `3-day-forecast/2022-09-22-sample.txt` | https://services.swpc.noaa.gov/text/scn/fy22-kp/10-102_three_day_forecast_sample.txt | 2022-09-22 | 1672 | issued 2022 Apr 28; Kp table with a `(G1)` annotation |
| `kp-3h/2022-09-22-sample.json` | https://services.swpc.noaa.gov/text/scn/fy22-kp/10-102_noaa-planetary-k-index_sample.json | 2022-09-22 | 2723 | **old format**: array of arrays, quoted numbers, `time_tag` with `.000` |
| `kp-forecast/2022-09-22-sample.json` | https://services.swpc.noaa.gov/text/scn/fy22-kp/10-102_noaa-planetary-k-index-forecast_sample.json | 2022-09-22 | 3870 | **old format**: array of arrays, quoted numbers, `time_tag` without `.000` |

## Shared

Files that a user of the library downloaded from SWPC for its own tests and
shared with the project, copied unchanged: they hold cases the recorded files
of the day do not have. The date is the UTC day of the download, as the
content shows it.

| File | Source | Downloaded on | Size (bytes) | Notes |
|---|---|---|---|---|
| `goes-flares-7-day/2026-08-28-shared.json` | https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json | 2026-08-28 | 15755 | 41 flares, up to M6.9; four without `max_ratio` |

## Live

Files downloaded while a rare case was happening, by a one-off script that
read the product every 5 minutes with the recorder's User-Agent, kept byte
for byte as served.

| File | Source | Downloaded (UTC) | Size (bytes) | Notes |
|---|---|---|---|---|
| `goes-flares-7-day/2026-10-30-live.json` | https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json | 2026-10-30 13:22 | 15307 | same moment as the latest file below: the flare in progress is not in the list |
| `goes-flares-latest/2026-10-30-live.json` | https://services.swpc.noaa.gov/json/goes/primary/xray-flares-latest.json | 2026-10-30 13:22 | 365 | a flare in progress (begin 13:08 UTC): no peak, no end yet |

## Built

Old-format files built by `tools/build_old_format.py` from the recorded file
of the same day, with the same values, so that a parser can be checked to give
the same model for both formats. The layout follows the official 2022 Kp
sample: header row, then rows with every number quoted as written in the
source. `tests/test_build_old_format.py` checks that each file is exactly what
the script produces. Rebuild one with:

```bash
uv run python tools/build_old_format.py tests/fixtures/kp-3h/2026-10-15.json \
    tests/fixtures/kp-3h/2026-10-15-built.json --millis
```

| File | Built from | Built on | Size (bytes) | Notes |
|---|---|---|---|---|
| `dst/2026-10-15-built.json` | `dst/2026-10-15.json` | 2026-10-15 | 5022 | **old format**, `time_tag` without `.000` (hypothesis) |
| `f107-30-day/2026-10-15-built.json` | `f107-30-day/2026-10-15.json` | 2026-10-15 | 910 | **old format**, `time_tag` without `.000` (hypothesis) |
| `kp-3h/2026-10-15-built.json` | `kp-3h/2026-10-15.json` | 2026-10-15 | 2696 | **old format**, `time_tag` with `.000` as in the official sample |
