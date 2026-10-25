# Sources and formats

Survey of 2026-10-15, done by reading the directory listings and some files
of `services.swpc.noaa.gov`, and the official SWPC pages. In T1 (same day)
the claims were checked against the fully downloaded files and against the
fixtures in `tests/fixtures/`: where it says **verified**, the reference is
the fixture named. Where a line still says **hypothesis**, it must be
verified before writing code on top of it. When a stage verifies or
disproves something, update this file.

## Directories

- `https://services.swpc.noaa.gov/json/`: among others `planetary_k_index_1m.json`,
  `ovation_aurora_latest.json`, `solar_regions.json`, `f107_cm_flux.json`,
  `icao-space-weather-advisories.json`; subdirectories `rtsw/`, `goes/`, `ace/`,
  `geospace/`, `lists/`, `solar-cycle/`, `stereo/`.
- `https://services.swpc.noaa.gov/products/`: `alerts.json`,
  `noaa-planetary-k-index.json`, `noaa-planetary-k-index-forecast.json`,
  `kyoto-dst.json`, `noaa-scales.json`, `10cm-flux-30-day.json`; subdirectory
  `summary/` (`10cm-flux.json`, `solar-wind-mag-field.json`,
  `solar-wind-speed.json`).
- `https://services.swpc.noaa.gov/text/`: `3-day-forecast.txt`,
  `3-day-geomag-forecast.txt`, `27-day-outlook.txt`,
  `drap_global_frequencies.txt`, `srs.txt`, `discussion.txt`, and others.
- `https://services.swpc.noaa.gov/text/scn/` contains **official sample
  files** attached to the SCNs, not the texts of the SCNs:
  - `fy22-kp/` (2022-09-22): samples of the **old format** of 3-hour Kp and
    forecast, plus 1-minute Kp, 3-day forecast and other texts. The useful
    ones are copied into `tests/fixtures/` (see the fixtures README).
  - `fy26-03/` (2026-02-27): samples of the **new format** (array of objects)
    of 3-hour Kp and forecast, Dst, `10cm-flux-30-day`, `10cm-flux` and the
    two solar wind summaries. Same format as the recorded fixtures: not
    copied.

All files recorded on 2026-10-15 are UTF-8 without BOM, with lines ended
by `\n`; the JSON files are on a single line, with no trailing `\n`; the
texts end with `\n`. The server sends `Last-Modified`, `ETag` and
`Cache-Control: max-age=60`.

## Indices

- **3-hour Kp** (`/products/noaa-planetary-k-index.json`, fixture
  `kp-3h/2026-10-15.json`), **verified**: array of 61 objects, ascending
  order, 7 and a half days at a 3-hour step. Compact format, numbers with
  two decimals (`"Kp":1.00`):
  `{"time_tag":"2026-10-08T00:00:00","Kp":1.00,"a_running":4,"station_count":8}`.
  `time_tag` without `Z`: to be read as UTC (reasonable **hypothesis**, to
  be stated in the docstring).
- **Kp forecast** (`noaa-planetary-k-index-forecast.json`),
  **verified**: 81 objects `{time_tag, kp, observed, noaa_scale}`, from 7
  days before to 3 days after. `observed` is `"observed"` (61),
  `"estimated"` (3) or `"predicted"` (17); `noaa_scale` is `null` or a
  string such as `"G1"`, `"G3"`. Careful: here the key is `kp`, in the
  3-hour Kp it is `Kp`.
  The `estimated` entries can be **in the future**: when recording at
  17:57 UTC, the 18:00 and 21:00 entries were already there. This is why
  the `data_time` of the forecast is the last `observed` entry.
- **Previous format** (until about 2026-03-31, SCN 26-21),
  **verified** on the official 2022 samples (`kp-3h/2022-09-22-sample.json`,
  `kp-forecast/2022-09-22-sample.json`): array of arrays, first row with the
  column names (the same as in the new format), then one row per record
  with the numbers in quotes and `null` without quotes. Compact format.
  `time_tag` with a space instead of the `T`: in the 3-hour Kp with
  milliseconds (`"2022-09-15 00:00:00.000"`), in the forecast without
  (`"2022-07-27 00:00:00"`). It also applied to Dst, `10cm-flux-30-day` and
  the solar wind summaries: for Dst and flux there is no real sample, and
  the `*-built.json` fixtures are built from the recorded ones. That their
  `time_tag` had no milliseconds is a **hypothesis**: the parser must
  accept both forms.
- **1-minute Kp** (`/json/planetary_k_index_1m.json`, fixture
  `kp-1m/2026-10-15.json`), **verified**: 358 objects in ascending order,
  about 6 hours. `{"time_tag":"2026-10-15T11:51:00","kp_index":3,"estimated_kp":3.00,"kp":"3Z"}`.
  The suffix of `kp` encodes the third: `Z` whole, `P` plus a third, `M`
  minus a third (0.33 → `"0P"`, 0.67 → `"1M"`, 2.67 → `"3M"`, 3.00 →
  `"3Z"`), and `kp_index` is the digit of `kp`. The official 2022 sample
  (`fy22-kp/10-102_planetary_k_index_1m_sample.json`) **is not usable**: it
  has a UTF-8 BOM and a `\r\n` line break every ~2 KB, even mid-word, so it
  is not valid JSON.
- **Dst** (`kyoto-dst.json`), **verified**: 168 hourly objects
  `{"time_tag":"2026-10-08T18:00:00","dst":-17}`, 7 days.
- **30-day F10.7** (`10cm-flux-30-day.json`), **verified**: 30 objects
  `{"time_tag":"2026-09-15T20:00:00","flux":107}`, one per day at 20 UTC,
  integer flux.
- **NOAA scales** (`noaa-scales.json`, fixture `noaa-scales/2026-10-15.json`),
  **verified** in form: one object with keys `"-1"`, `"0"`, `"1"`, `"2"`,
  `"3"`, each with `DateStamp` (`"2026-10-15"`), `TimeStamp` (`"17:50:00"`)
  and the groups `R` (`Scale`, `Text`, `MinorProb`, `MajorProb`), `S`
  (`Scale`, `Text`, `Prob`), `G` (`Scale`, `Text`). All values are strings
  or `null` (`"Scale": "0"`, `"MinorProb": "20"`). **Hypothesis** from
  comparing the dates: `-1` is the scales observed in the previous 24
  hours, `0` the current ones, `1`–`3` the forecast for today and the next
  two days (with the probabilities and without `Scale` for R and S).
  `DateStamp`/`TimeStamp` are read as UTC: in the fixture, entry `0` says
  `17:54:00` and was recorded at 17:57 UTC (a clue, not documentation).

## Solar wind (RTSW)

- `/json/rtsw/rtsw_mag_1m.json` (~1.4 MB) and `/json/rtsw/rtsw_wind_1m.json`
  (~2.4 MB), reduced fixtures `rtsw-*-1m/2026-10-15.json`, **verified**:
  arrays of objects in **descending** order (most recent first),
  **24 hours**. Mag fields: `time_tag`, `active`, `source`, `range`,
  `scale`, `sensitivity`, `manual_mode`, `sample_size`, `bt`,
  `b{x,y,z}_{gse,gsm}`, `theta_*`, `phi_*`, `max_telemetry_flag`,
  `max_data_flag`, `overall_quality`. Plasma fields: `proton_*` and
  `alpha_*` (speed, density, temperature, GSE and GSM components,
  `*_sample_size`), seven `max_*` flags, `overall_quality`. Many fields can
  be `null` (ACE's velocity components, all the `alpha_*`);
  `max_data_flag` can be `-9999`.
- Python JSON format (separators `", "` and `": "`).
- **Sources** on 2026-10-15: `SOLAR1` (always `active: true`), `ACE` and
  `IMAP` (always `active: false`). Each instant has one or two records:
  usually SOLAR1 and ACE together. There are minutes with **only inactive
  records** (ACE alone, 15 in mag and 223 in plasma), so "the active record
  for an instant" can be missing.
- **IMAP** has `time_tag` values not aligned to the minute (almost always at
  `:01` seconds, sometimes others), so it never shares an instant with the
  other sources; on the recorded day it covers roughly from 20:27 to 15:54.
- Since 2026-06-30 the primary source is **SOLAR-1** (SWFO-L1), with ACE as
  backup; DSCOVR is no longer processed.
- **Verified in T3** on the reduced fixtures (223 mag records, 220 plasma):
  - IMAP's seconds depend on the file: in mag `:01` (21 records) and `:09`
    (one), in plasma always `:03` (28 records);
  - no instant has two active records; in mag 23 instants out of 137 lack
    the active record (22 IMAP only, one ACE only at 21:01 on the
    14th), in plasma 41 out of 134 (28 IMAP only, 13 ACE only);
  - `max_data_flag` is `-9999` for SOLAR1 and ACE in mag, `0` for IMAP; in
    plasma it is always `0`. That `-9999` is a fill value
    ("flag not available") is a **hypothesis**: the parser keeps it as is;
  - `range`, `scale` and `sensitivity` in mag are always `null`: their type
    cannot be inferred and the parser does not read them;
  - ACE and IMAP do not give the velocity components (`proton_v*` set to
    `null`); the `alpha_*` are `null` for all sources;
  - `-9999` never appears in the physical fields: that a missing value is
    always `null` is a **hypothesis**. The parser rejects (`ParseError`)
    impossible values: negative `bt`, speed, density and temperature,
    `theta_*` outside -90…90, `phi_*` outside 0…360 (in the fixture `phi`
    goes from 4.0 to 359.8);
  - `overall_quality`, `max_telemetry_flag` and `sample_size` (60 in mag, 1
    in plasma) always have the same value: the meaning of the flags is not
    documented.
- **Model choices** (T3): records are reordered oldest first, keeping the
  file order among those of the same instant; the active record of an
  instant is the one with `active: true` (if there were two, the first in
  the file wins); an instant with no active record stays without one, with
  no fallback to another source. Unknown sources stay strings.
  `data_time` is the last `time_tag` of any source; the freshness of the
  active source alone is `latest_active().time`.

## GOES

- `/json/goes/primary/` and `/secondary/`, files `*-6-hour`, `*-1-day`,
  `*-3-day`, `*-7-day`.
- `xrays-1-day.json` (reduced fixture `goes-xrays-1-day/2026-10-15.json`),
  **verified**: ascending order, one-minute step, two records per
  instant, one per band (`energy`: `"0.05-0.4nm"` and `"0.1-0.8nm"`).
  Fields: `time_tag` (with `Z`), `satellite` (18), `flux`, `observed_flux`,
  `electron_correction`, `electron_contaminaton` (spelled that way in the
  source: the typo is the real field name). Python JSON format.
- The flare class (A/B/C/M/X) is computed from the flux of the 0.1–0.8 nm
  band: A < 1e-7, B < 1e-6, C < 1e-5, M < 1e-4, X ≥ 1e-4 W/m², with the
  multiplier (M2.5 = 2.5e-5). The maximum of the recorded day is about
  C5.0 at 15:55 (not kept by the reduction; in the fixture the maximum is
  about C3.9).
- `integral-protons-1-day.json` (reduced fixture), **verified**:
  `{"time_tag":…,"satellite":18,"flux":5.38,"energy":">=1 MeV"}`, ascending
  order, 5-minute step (a few instants are missing), eight energies per
  instant: `>=1`, `>=5`, `>=10`, `>=30`, `>=50`, `>=60`, `>=100`,
  `>=500 MeV`.
- **Verified in T3** on the fixtures:
  - in the X-rays `flux` = `observed_flux` − `electron_correction`, but with
    a **floor** of 1e-9 (written `9.999999717180685e-10`, i.e. 1e-9 in
    single precision): in the 6 records where the difference is lower, or
    negative, `flux` equals that floor. It happens only in the
    0.05–0.4 nm band, always with `electron_contaminaton: true`. That the
    floor always applies is a **hypothesis**: the parser does not check the
    sign of the flux, and the flare class comes out `None` for a zero or
    negative flux;
  - `electron_contaminaton` is `true` only in the short band (100 records
    out of 129), never in the long one;
  - in the protons the eight energies of an instant are in string order
    (`>=1`, `>=10`, `>=100`, `>=30`, `>=5`, `>=50`, `>=500`, `>=60`), not
    in threshold order: the parser derives the threshold in MeV from the
    `>=N MeV` label and rejects (`ParseError`) a label of any other form.
- **Hypothesis**: the `*-6-hour`, `*-3-day`, `*-7-day` files and the
  `secondary/` directory have the same format as the primary's one-day
  files (the only ones recorded); the parsers accept them with
  `source_url=`.
- **Verified** on the SWPC pages (read on 2026-10-16):
  - `products/goes-proton-flux`: the `integral-protons` files give integral
    fluxes averaged over 5 minutes in protons/(cm² s sr) (= pfu) for the
    thresholds ≥1, 5, 10, 30, 50, 60, 100 and 500 MeV, the same as in the
    fixtures; alert thresholds 10…100 000 pfu at ≥10 MeV and 1 pfu at
    ≥100 MeV;
  - `products/goes-x-ray-flux`: 1-minute averages in the 0.1–0.8 nm and
    0.05–0.4 nm bands, data from the primary and the secondary satellite;
    maximum of an event = minute of the peak;
  - `phenomena/solar-flares-radio-blackouts`: the class is defined on the
    peak of the 0.1–0.8 nm band, in W/m², with A from 10⁻⁸, B from 10⁻⁷, C
    from 10⁻⁶, M from 10⁻⁵, X from 10⁻⁴.
- **Flare class** (T3): the multiplier is **truncated** to one decimal
  (3.95e-6 → C3.9; 9.99e-6 → C9.9, never C10.0), computed on the shortest
  decimal form of the flux, so 2.3e-5 gives M2.3. That SWPC truncates
  instead of rounding remains a **hypothesis** (the SWPC pages do not say):
  truncation is chosen because it keeps the letter consistent with the
  thresholds. The class is computed only on the 0.1–0.8 nm band; X has no
  ceiling (1.2e-3 → X12.0).

## Alerts

- `/products/alerts.json` (fixture `alerts/2026-10-15.json`), **verified**:
  81 objects `{product_id, issue_datetime, message}`, descending order,
  about 30 days. `issue_datetime` in the format `YYYY-MM-DD HH:MM:SS.mmm`.
- `message` mixes line breaks: in **every** message the first lines
  (header and blank line) end with `\r\n`, the rest can also end with `\n`.
  The parser must accept both.
- First three lines always present: `Space Weather Message Code: WARK04`,
  `Serial Number: 5435`, `Issue Time: 2026 Oct 13 2058 UTC`. Then the title
  (`ALERT:`, `WARNING:`, `EXTENDED WARNING:`, `WATCH:`, `CONTINUED ALERT:`,
  `CANCEL WATCH:`, `SUMMARY:`) and fields such as `Valid From:`,
  `Valid To:`, `Now Valid Until:`, `Threshold Reached:`,
  `Synoptic Period:`, `Active Warning:`, `Begin Time:`, `End Time:`,
  `Maximum Time:`, `Extension to Serial Number:`,
  `Continuation of Serial Number:`, `Cancel Serial Number:`, `Comment:`,
  `Potential Impacts:`.
- **Variants to handle**: `NOAA Scale:` (26 times) and `Noaa Scale:` (25);
  `Warning Condition:` and `Warning Conditions:`; `Estimate Velocity:` (not
  "Estimated").
- **Two families of codes.** The official table
  (`https://www.spaceweather.gov/content/subscription-services`) uses long
  codes such as `ALTK05`, `WARK04`, `WATA20`; the `product_id` values in
  `alerts.json` are short. **Mapping verified** on the text of the 81
  messages (each short code always has the same long code):

  | Short | Long | Short | Long |
  |---|---|---|---|
  | `K04W`…`K07W` | `WARK04`…`WARK07` | `TIIA` | `ALTTP2` |
  | `K04A`…`K07A` | `ALTK04`…`ALTK07` | `TIVA` | `ALTTP4` |
  | `A20F` | `WATA20` | `XM5A` | `ALTXMF` |
  | `A30F` | `WATA30` | `XM5S` | `SUMXM5` |
  | `EF3A` | `ALTEF3` | `SGIW` | `WARSUD` |
  | `MSIS` | `SUMSUD` | `BHIS` | `SUM10R` |

  In the official table `ATLK04` appears spelled that way (probable typo
  for `ALTK04`). The 2022 samples inside `swpclib` (`A20F`, `K05W`, `K05A`)
  are consistent.

Verified in T4 on the same fixture:

- `issue_datetime` always falls in the same minute as `Issue Time:` (from 0
  to 59 seconds later): the first is the precise time, the second is to the
  minute.
- The **serial number is not unique**: three `CONTINUED ALERT` of `ALTEF3`
  (issued on 6, 7 and 8 October) all have `Serial Number: 3752`; the last
  two end with a `CORRECTED` line and have
  `Continuation of Serial Number: 3752`, equal to their own.
- **Times in the text**: all in the form `2026 Oct 13 2058 UTC`
  (`Valid From`, `Valid To`, `Now Valid Until`, `Threshold Reached`,
  `Begin Time`, `Maximum Time`, `End Time`, `Observed`,
  `Original Issue Time`, `Max time`), except `Ip Shock: 2026-10-10 14:43`
  (in `WARSUD`, without `UTC`). `Valid To` uses `2359`, never `2400`;
  `2400` appears only in `Synoptic Period: 2100-2400`, which is an
  interval.
- `Max time:` (with a lowercase t) appears in 5 `CONTINUED ALERT` of
  `ALTEF3`, next to `Yesterday Maximum 2MeV Flux:`; the summaries have
  `Maximum Time:`.
- **NOAA scale** in 26 messages. When both spellings are present
  (`Noaa Scale:` among the fields, `NOAA Scale:` after a blank line) the
  value is the same; an `EXTENDED WARNING` of `WARK05` has only
  `NOAA Scale:`. Values: `G1 - Minor`, `G2 - Moderate`, `G3 - Strong`
  (`ALTK07`), `G3 - Greater` (`WARK07`, "K-index of 7 or greater"),
  `R2 - Moderate`. **Watches have no scale line**: the level is in the
  title (`Geomagnetic Storm Category G1 Predicted`) and after
  `Highest Storm Level Predicted by Day:` in a line such as
  `Oct 12:  None (Below G1)   Oct 13:  G1 (Minor)` (in the `CANCEL WATCH`:
  `Oct 11  : None (Below G1)`). The parser does not treat these lines as
  fields.
- Other fields seen: `Original Issue Time:`, `Cancelled Level Predicted:`,
  `Observed:`, `Deviation:`, `Station:`, `Peak Flux:`, `Duration:`,
  `Latest Penticton Noon Flux:`, `Xray Class:`, `Optical Class:` (also
  empty), `Location:`, `Yesterday Maximum 2MeV Flux:`, `Ip Shock:`. There
  are lines without `Name:` (`THIS SUPERSEDES ANY/ALL PRIOR WATCHES IN EFFECT`,
  `CORRECTED`, free sentences, the continuation of `Potential Impacts:`),
  and `Comment:` can contain long runs of spaces.
- **Hypothesis**: an empty array `[]` has never been seen; the parser reads
  it as "no messages" (not as `SourceNotReady`), because a period without
  alerts is a legitimate state.
- **Hypothesis** (unofficial source): in the 2022 samples inside `swpclib`
  all lines end with `\r\n`, they have `Active Warning: Yes` and
  `Synoptic Period: 0000-0300 UTC`, and `NOAA Scale:` appears only once.
  The parser also accepts this form (tested with built data).
- **Code catalog** (`swpc_kit/codes.py`): the 18 pairs in the table above
  are **verified** on the text of the messages, with meaning (from the
  title) and scale (from the `NOAA Scale:` line or, for watches, from the
  title).
- **Official table**, re-read on 2026-10-16
  (`https://www.spaceweather.gov/content/subscription-services`), columns
  code, title, WMO header (`WOXX..`), scale, impacts. It contains 39 long
  codes, now all in the catalog (a test checks this):
  - K-index: `ALTK04`…`ALTK09` (`ALTK08` = "Geomagnetic K-index of 8", G4;
    `ALTK09` G5), `WARK04`…`WARK07`; watches `WATA20`, `WATA30`, `WATA50`
    (G3), `WATA99` ("G4 or greater"); `SUMSUD`, `WARSUD`; `ALTEF3`;
  - protons ≥10 MeV: `ALTPX1`…`ALTPX5` and `SUMPX1`…`SUMPX5` (10, 100,
    1 000, 10 000, 100 000 pfu = S1…S5), `WARPX1` ("S1 or Greater");
    ≥100 MeV: `ALTPC0`, `SUMPC0`, `WARPC0` (1 pfu, no scale);
  - X-rays: `ALTXMF`, `SUMXM5` (R2), `SUMX01` (R3), `SUMX10` (R4),
    `SUMX20` (R5); radio: `ALTTP2`, `ALTTP4`, `SUM10R`.
  - `ATLK04` is spelled that way in the table (typo for `ALTK04`, confirmed
    by the messages). The row of the 245 MHz summary has `245MHz` in place
    of the code: it is not in the catalog.
- For the entries seen only in the table, long code, meaning and scale are
  **verified**. Only the short codes `K08A`, `K09A`, `A50F`, `A99F` remain
  **inferred**, following the pattern of the ones seen; for protons and
  X-rays the pattern cannot be guessed and the short code stays `None`.

## Text bulletins

Fixtures `3-day-forecast/`, `geomag-forecast/`, `27-day-outlook/`,
**verified**:

- Common header: `:Product: …` and `:Issued: 2026 Oct 15 1230 UTC`, then
  comments with `#`. The product name changes from file to file:
  `3-Day Forecast`, `Geomagnetic Forecast` (for `3-day-geomag-forecast.txt`),
  `27-day Space Weather Outlook Table 27DO.txt`.
- The tables have **trailing spaces** on their lines.
- `3-day-forecast.txt`: sections `A.` (sentence on the maximum observed and
  predicted Kp, then `NOAA Kp index breakdown Oct 15-Oct 17 2026` with
  eight rows `00-03UT` … `21-00UT` and three columns of Kp), `B.` (row
  `S1 or greater` with three percentages) and `C.` (rows `R1-R2` and
  `R3 or greater`). Each section has a multi-line `Rationale:`. The maximum
  observed Kp can be written as an integer (`was 3 (below NOAA`), with the
  sentence split over two lines. In the 2022 sample
  (`3-day-forecast/2022-09-22-sample.txt`) a table cell is `5.33 (G1)`: the
  NOAA scale is added next to the value.
- `3-day-geomag-forecast.txt`: `Observed Ap 13 Oct 013`, `Estimated Ap 14 Oct 011`,
  `Predicted Ap 15 Oct-17 Oct 010-008-005`, probabilities such as
  `Active 25/20/15` (active, minor storm, moderate, strong-extreme), then
  the Kp table with the same row layout as the 3-day forecast.
- `27-day-outlook.txt`: after the comments, 27 fixed-width rows,
  `2026 Oct 12     120          16          4` = date, 10.7 cm flux, Ap,
  maximum Kp; the issue of 2026-10-12 starts from the same day.

Verified in T5 on the same fixtures, and used by the parsers
(`swpc_kit/parse/bulletins.py`):

- The cells of the Kp tables **always have two decimals** (`2.00`,
  `0.67`), in whole thirds, in all three fixtures (2022 and 2026); the
  parser requires it, so a cut-off value (`1.6`, `1`) is not taken as
  valid. The Kp in the sentences, instead, can be an integer (`was 3`).
- The day columns are written `Oct 15` (month day) in the tables and
  `13 Oct` (day month) in the Ap rows and in the titles of the geomagnetic
  forecast, without a year: the parser picks the year that puts the date
  closest to the `:Issued:`. How SWPC writes the title
  `NOAA Kp index breakdown …` across the year boundary (perhaps
  `Dec 31-Jan 02 2027`) is a **hypothesis**: the parser does not read it.
- The sections of the 3-day forecast start with `A. `, `B. `, `C. `; the
  sentences on the maximum Kp must be read after joining the split lines.
- In the geomagnetic forecast of 2026-10-14 the observed Ap is for the day
  before the issue, the estimated one for the same day, the forecast for
  the next three days; the parser only checks that the Ap forecast, the
  probabilities and the Kp table have the same days.
- The three files end with `\n`: content that does not end with a line
  break and has an error on the last line is treated as truncated
  (`SourceNotReady`).

**Hypotheses** (one fixture or none, to be rechecked when the chance
comes):

- That the annotations in the cells are only `(G1)`…`(G5)`: only `(G1)`
  seen.
- That `Rationale:` can have several paragraphs: not seen; the parser keeps
  them separated by a blank line.
- That the 27-day outlook always has **27** rows: the name and the fixture
  say so; the parser requires 27 (fewer = truncated, more = `ParseError`).
- For the three bulletins no earlier formats are known, nor SCNs that
  change them: the parser accepts only the one in the fixtures.

## Grids

- **OVATION** (`/json/ovation_aurora_latest.json`, ~0.9 MB, reduced fixture
  `ovation-aurora/2026-10-15.json`), **verified** on the full file: keys
  `Observation Time`, `Forecast Time` (with `Z`), `Data Format`
  (`"[Longitude, Latitude, Aurora]"`), `coordinates`, plus
  `"type": "MultiPoint"` (verified in T6 on the fixture; the parser ignores
  it). Python JSON format (separators `", "` and `": "`). `coordinates` has
  65 160 triples of integers: longitude 0–359 as the outer loop, latitude
  -90…90 as the inner loop, step 1 (360×181). Values 0–35 on the recorded
  day (0–33 in the fixture). That the value is the aurora probability in
  percent remains a **hypothesis**: the file does not say so; the model
  uses `units = "%"` anyway and states it in the docstring.
  The product page
  (`https://www.spaceweather.gov/products/aurora-30-minute-forecast`, read
  on 2026-10-16) says that the model computes the aurora intensity and that
  the "aurora viewing probability" is derived from it with a linear
  relation, but does not give the unit of the JSON values (which it calls
  "auroral data in grid format"): the hypothesis is plausible, not
  verified.
  The fixture keeps 15 integer longitudes (0, 1, 30, 60, … 330, 358, 359),
  so it is **not** a complete grid: the parser reads it only with
  `partial=True`, and the full-grid tests build the grid in code.
- The OVATION parser (T6) does not depend on the order of the triples, but
  wants each point exactly once and each longitude present with all 181
  latitudes. It accepts `Data Format` with different spacing or case; a
  different order of the three fields is `UnexpectedContent`. Non-integer
  values are anticipated but not seen: the parser accepts them (≥ 0), with
  no ceiling at 100 while the unit is a hypothesis.
- **D-RAP** (`/text/drap_global_frequencies.txt`, full fixture
  `drap/2026-10-15.txt`), **verified**: first line `# DRAP Tabular Values`,
  then `#` comments with `Product Valid At : 2026-10-15 17:54 UTC`,
  `Estimated Recovery Time : No Estimate`, `X-RAY Message :`,
  `X-RAY Warning :`, `Proton Message :`, `Proton Warning :` (the warnings
  can be empty, even with trailing spaces), and
  `# Frequency (MHz) as a function of Latitude and Longitude`; then a
  header row with 90 longitudes from -178 to 178 in steps of 4, a dashed
  row and 90 latitude rows from 89 to -89 in steps of 2, in the form
  ` 89 |  0.0  0.0 …` (latitude in 3 characters, values in 5), frequencies
  in MHz with one decimal (0.0–9.4 on the recorded day). 111 lines ended by
  `\n`.
- **Meaning, verified** on the official documentation
  (`https://www.spaceweather.gov/content/global-d-region-absorption-prediction-documentation`,
  read on 2026-10-16): the global map gives the **Highest Affected
  Frequency** (HAF), i.e. the frequency that loses 1 dB in vertical
  propagation from the ground to the ionosphere and back; lower frequencies
  lose more. The polar maps use 10 dB, but they are not in this file. The
  model uses `quantity = "highest affected frequency"`, in MHz.
- The same page says that the "Tabular Values" are at steps of 5° of
  latitude and 15° of longitude: the 2026-10-15 file is instead at
  2° × 4°. The documentation is older than the file; the parser does not
  fix the steps.
- **Messages, verified** on the same page: `X-RAY Message` is
  `Normal x-ray background`, `Elevated x-ray flux`, `Moderate x-ray flux`
  (M1–M5), `Strong x-ray flux` (M5–X1), `Severe x-ray flux` (X1–X20) or
  `Extreme x-ray flux`; `Proton Message` is `Normal proton background`,
  `Minor`/`Moderate`/`Strong`/`Severe`/`Extreme proton flux` (thresholds
  10, 100, 1 000, 10 000, 100 000 pfu at ≥10 MeV). The model keeps them as
  text.
- `Estimated Recovery Time`: the page describes a clock in minutes
  (computed after the peak of a flare above M1 or from a proton event), but
  not the text of the file when there is an estimate: the format remains a
  **hypothesis** (only `No Estimate` seen) and the model keeps it as text.
- The D-RAP parser (T6) wants a table that covers the globe: regular
  longitudes from -180 + step/2 to 180 - step/2, regular latitudes from one
  pole to the other. A table that stops before the opposite pole, or a
  short last line in a text without a trailing `\n`, is `SourceNotReady`; a
  short or malformed line in the middle is `ParseError` with the line.
- For the GeoTIFF: the coordinates are cell centers on a regular lat/lon
  grid (EPSG:4326). The OVATION longitude (0–359) must be rotated to
  -180…180 for use on a map: the export does this, the model keeps the data
  as it arrives. With the centers at ±90 and at -180, the OVATION cell
  edges extend half a degree beyond (raster from -180.5 to 179.5 and from
  -90.5 to 90.5); the GeoJSON instead clips the polygons at ±90 and splits
  in two those that straddle the antimeridian.

## HTTP client (T7, 2026-10-16)

- **State of httpx, verified on PyPI** (JSON API of `pypi.org`,
  2026-10-16): the latest stable release of `httpx` is **0.28.1 of
  2024-12-06**; after it there are only development releases
  `1.0.dev2`…`1.0.dev6` (the last on 2026-08-31). `httpcore` is stuck at
  1.0.9 of 2025-04-24.
- **`httpx2`** (`https://github.com/pydantic/httpx2`, BSD-3-Clause, Python
  ≥ 3.10): 2.13.1 of 2026-09-23, releases every few weeks. Its description
  on PyPI says that it is the continuation of httpx, taken over by Pydantic
  "so that users have a reliably maintained path forward -
  including timely security updates". Same API (`httpx2.Client`,
  `AsyncClient`, `MockTransport`, exceptions
  `TransportError`/`TimeoutException`), module `httpx2`, `py.typed`
  marker. Depends on `httpcore2` (pinned to the same version), `anyio`,
  `idna`, `truststore` (uses the system certificates).
- **Choice**: the `client` extra uses `httpx2>=2.13`. Only
  `swpc_kit/client/_httpx.py` imports the library; the clients depend on
  the `Transport`/`AsyncTransport` protocol, so going back to `httpx` (or
  using something else) touches a single module. Alternatives considered:
  `niquests` (active, requests API), `aiohttp` (async only), `requests`
  (sync only).
- **Verified live** on 2026-10-16 (manual check, not a test): the client
  downloads and parses all 16 products of the day; SWPC sends **weak**
  `ETag`s (`W/"12c4-…"`) and `Last-Modified`, and answers
  `304 Not Modified` to the conditional request with `If-None-Match`.

## Plausibility limits (T14, 2026-10-25)

SWPC documents no fill value for the physical fields (that a missing value
is always `null` is a **hypothesis**, see "Solar wind"). So the parsers do
not turn any value into `None`: a value beyond these limits makes the record
**skipped** (`skipped` of the model, with the reason), and the other records
are read. The limits are deliberately far beyond anything measured, to catch
fill values such as `99999` or `-99999` and changes of unit, never a real
extreme. They are **choices**, not documented by SWPC:

| Field | Limit | Why |
|---|---|---|
| Dst | -2000 to 500 nT | the strongest storm measured is about -590 nT (1989); estimates for 1859 go to about -1700 nT |
| F10.7 | 30 to 5000 sfu | the quiet Sun stays above about 60 sfu; flare-enhanced daily values stay well below 5000 |
| RTSW field strength `bt` and each component | ±1000 nT | at L1 the field rarely exceeds 100 nT |
| RTSW proton and alpha speed | up to 5000 km/s | the fastest solar wind measured is below 3000 km/s |
| GOES X-ray flux (`flux`, `observed_flux`) | up to 0.1 W/m² (X1000) | about 35 times the strongest flare recorded (X28, 2.8e-3 W/m², November 2003) |
| GOES integral proton flux | up to 1e8 pfu | the largest events stay below 1e6 pfu, even at ≥1 MeV |

Consistency checks, also by record:

- **1-minute Kp**, **verified** on the fixture (358 records, no exception):
  `kp_index` is the digit of the `kp` label, and `estimated_kp` rounded to
  thirds is the label (`Z` whole, `P` plus a third, `M` minus a third). A
  record where they disagree is skipped.
- **Quoted numbers** (old format) must be plain decimals: `0_5`, `+5`,
  `nan`, `inf` are not numbers here, although Python's `float()` accepts
  them. Spaces around the number are accepted.
- **3-day forecast**: a storm scale such as `(G1)` needs a Kp of at least
  4.67 (5-): a `2.00 (G2)` cell is a `ParseError` (the bulletins stay
  strict). Which third starts each level above G1 is a **hypothesis** not
  checked: the fixture has a single scale cell, `5.33 (G1)`.

## Known changes (SCN)

- **SCN 26-21** (2026-03-02): new JSON formats from about 2026-03-31, old
  ones deprecated from 2026-04-30.
- **Solar wind** (2026-06-30): end of DSCOVR, SOLAR-1 primary, ACE as
  backup; IMAP on its way. On 2026-10-15 the IMAP records are already in
  the RTSW files, inactive.
- **SCN 26-39**: shutdown of GeoAlert (`geoalert.txt`) planned for
  2026-05-19, but the file was still present on 2026-10-15. Out of scope
  for the first version.
- **SCN 26-35**: shutdown of the CTIPe TEC model, replaced by GloTEC.
- The content pages of `swpc.noaa.gov` redirect to `www.spaceweather.gov`;
  `services.swpc.noaa.gov` still responds. Notices and archive:
  `https://www.weather.gov/notification/`; `services.swpc.noaa.gov/text/scn/`
  contains the SCN sample files (see "Directories").

## Lessons from those already using this data

- SWPC sometimes serves a **truncated** JSON while rewriting it: that is
  `SourceNotReady`, not a parser error.
- A NOAA source that has moved can answer with a redirect to an HTML page:
  a client that follows redirects gets HTML instead of the data
  (`UnexpectedContent`).
- The modification date of a file does not tell the age of its content:
  look at the time written inside.

## Existing libraries (2026-10-15)

We did not find one that covers everything with typed models, parsing of
messages and bulletins, and export of the grids. Fragments:

- `sunpy`: only the solar cycle predictions (sunspots, F10.7).
- `swvo` (GFZ, Apache-2.0): from SWPC only Kp and F10.7.
- `spaceweather` (pyspaceweather): indices from Celestrak, GFZ, OMNI; not
  SWPC.
- `solar-mcp`, `spaceweather-mcp`: MCP servers, not libraries.

### `swpclib` and `nws-aurora` (assessed in T0, 2026-10-15)

Read from their sources on PyPI. Neither of the two covers a relevant part
of `SPEC.md`: the project goes ahead.

- **`swpclib` 4.3.7** (MIT, 2024-04-18, depends on `aiohttp`, `pillow`,
  `click`; the README says "Features: TODO"). An asynchronous `Runner`
  class that downloads and returns untyped **dictionaries**: F10.7
  (`/json/f107_cm_flux.json`), Boulder K, predicted Fredericksburg A,
  observed sunspots, 1-minute Kp, `solar_probabilities.json`,
  `alerts.json`, and GIF animations (SUVI, OVATION, LASCO, D-RAP) assembled
  with Pillow. Errors are **swallowed**: `print(repr(e))` and a `None`
  value. Message dates stay without a time zone (`datetime.now()` compared
  with UTC times). It does not cover 3-hour Kp, Dst, scales, RTSW, GOES,
  bulletins, grids, nor the new 2026 formats. A single test.
- **`nws-aurora` 0.0.6** (MIT, 2024-09-18, depends on `requests`, `bs4`,
  `geojson`, `pytz`, `click`). Aurora only: list of the OVATION images (by
  scraping the HTML index of the directory), OVATION grid as a
  `FeatureCollection` of **points** with longitude 0–359 as is, and
  `aurora-nowcast-hemi-power.txt` read by skipping 16 fixed lines. No
  types, no error handling.
- **Name**: `swpc-kit` (and `swpc_kit`, `swpckit`) free on PyPI on
  2026-10-15 (404 response from the JSON API). PyPI can still reject a name
  at first publication: recheck before publishing.

Two useful things read in their sources, from **unofficial** sources:

- `swpclib` contains three `alerts.json` samples from 2022-09-27, cited in
  "Alerts" above.
- `nws-aurora` contains an OVATION grid from 2024-09-18, already converted:
  65 160 points, longitude 0–359 (360 values), latitude -90…90 (181
  values). Consistent with the grid verified in T1.
