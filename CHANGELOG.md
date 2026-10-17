# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [0.1.0] - 2026-10-17

First version. Not published on PyPI.

### Added

- Parsers (`swpc_kit.parse`) and frozen, typed models (`swpc_kit.models`) for
  the SWPC products of the first version:
  - indices: planetary K index (3-hour, forecast, 1-minute), Kyoto Dst, F10.7
    (30 days), NOAA space weather scales; the pre-2026 array-of-arrays
    formats are read too and give the same models;
  - real-time solar wind (magnetic field and plasma) with active-source
    selection; GOES X-ray flux with flare class and integral protons;
  - `alerts.json` messages, and the catalogue of message codes
    (`swpc_kit.codes`) checked against the official SWPC table;
  - text bulletins: 3-day forecast, geomagnetic forecast, 27-day outlook;
  - OVATION aurora and D-RAP grids in a common grid model.
- Typed errors under `SwpcError`: `SourceNotReady`, `UnexpectedContent`,
  `ParseError`, `StaleData`.
- GeoJSON export (`swpc_kit.export.to_geojson`, standard library) and GeoTIFF
  export (`swpc_kit.export.geotiff.write_geotiff`, `geo` extra: numpy,
  rasterio).
- Sync and async HTTP clients (`swpc_kit.client`, `client` extra: httpx2) with
  one method per product, conditional requests (`ETag`, `Last-Modified`),
  error classification and a `max_age` check on the time the content
  declares.
- Recorded fixtures and the tools that record them (`tools/`).

[0.1.0]: https://github.com/Tabrigos/swpc-kit/releases/tag/v0.1.0
