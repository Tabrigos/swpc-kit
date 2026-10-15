"""Typed readers for the public data products of NOAA SWPC.

The package has three layers, each usable on its own:

- :mod:`swpc_kit.parse`: pure functions that turn raw ``str``/``bytes`` into
  models (standard library only);
- :mod:`swpc_kit.models`: frozen dataclasses with UTC ``datetime`` fields;
- outputs: :mod:`swpc_kit.export` (GeoJSON, GeoTIFF) and
  :mod:`swpc_kit.client` (HTTP access, ``client`` extra).

Data comes from NOAA SWPC (https://www.swpc.noaa.gov). This project is not
affiliated with or endorsed by NOAA.
"""

from swpc_kit.errors import (
    ParseError,
    SourceNotReady,
    StaleData,
    SwpcError,
    UnexpectedContent,
)

__version__ = "0.1.0.dev0"

__all__ = [
    "ParseError",
    "SourceNotReady",
    "StaleData",
    "SwpcError",
    "UnexpectedContent",
    "__version__",
]
