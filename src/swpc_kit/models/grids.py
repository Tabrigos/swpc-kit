"""Models for the gridded products: OVATION aurora and D-RAP.

Both products are values on a regular latitude/longitude grid. The values are
given at **cell centres**; a cell spans half a step on each side of its
centre. :class:`Grid` holds the axes, the values, the quantity and its units;
the product models add the times the content declares and its own text
fields. :class:`GridProduct` is what the exports in :mod:`swpc_kit.export`
accept.

A grid keeps the longitudes as the source delivers them (OVATION uses 0 to
359, D-RAP -178 to 178); :meth:`Grid.wrapped` turns them into -180 to 180 for
use on a map.
"""

import math
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from typing import Protocol

from swpc_kit.models._checks import check_utc

_TOLERANCE = 1e-9


def wrap_longitude(longitude: float) -> float:
    """Return ``longitude`` in degrees east, moved into [-180, 180).

    For example 0 stays 0, 180 becomes -180, 359 becomes -1.
    """
    return (longitude + 180.0) % 360.0 - 180.0


def _check_axis(name: str, axis: tuple[float, ...], step: float) -> None:
    if not axis:
        raise ValueError(f"{name} must not be empty")
    if not (math.isfinite(step) and step > 0):
        raise ValueError(f"{name} step must be a positive number, got {step!r}")
    first = axis[0]
    for previous, value in pairwise(axis):
        if not value > previous:
            raise ValueError(f"{name} must be strictly increasing, got {axis!r}")
    for value in axis:
        offset = (value - first) / step
        if abs(offset - round(offset)) > _TOLERANCE:
            raise ValueError(
                f"{name} value {value} is not on the grid of step {step} "
                f"starting at {first}"
            )


def _contiguous(axis: tuple[float, ...], step: float) -> bool:
    expected = round((axis[-1] - axis[0]) / step) + 1
    return len(axis) == expected


def _find(axis: tuple[float, ...], value: float) -> int | None:
    for index, item in enumerate(axis):
        if abs(item - value) <= _TOLERANCE:
            return index
    return None


def _holding(
    axis: tuple[float, ...], step: float, values: tuple[float, ...]
) -> int | None:
    """Index of the cell of ``axis`` whose span holds one of ``values``.

    ``values`` are the same point written in different conventions. On a
    border the cell after it wins, then the one before: so the last edge of
    the axis still belongs to its last cell.
    """
    lattice = {round((item - axis[0]) / step): i for i, item in enumerate(axis)}
    for after in (True, False):
        for value in values:
            position = (value - axis[0]) / step
            offset = math.floor(position + 0.5) if after else math.ceil(position - 0.5)
            if offset in lattice:
                return lattice[offset]
    return None


@dataclass(frozen=True, slots=True)
class Grid:
    """Values on a regular latitude/longitude grid, at cell centres.

    The axes lie on a regular lattice of the given steps, but they may have
    gaps: a grid read from a reduced file (see :func:`~swpc_kit.parse.grids.
    parse_ovation_aurora`) keeps only some longitudes. :attr:`is_contiguous`
    tells the two apart.

    Attributes:
        latitudes: Cell-centre latitudes in degrees north, strictly
            increasing (south to north), within [-90, 90].
        longitudes: Cell-centre longitudes in degrees east, strictly
            increasing, within [-180, 360), as the source delivers them.
        latitude_step: Height of a cell in degrees.
        longitude_step: Width of a cell in degrees.
        values: One row per latitude, in the order of ``latitudes``; each row
            has one value per longitude, in the order of ``longitudes``.
        quantity: What the values are, such as ``"aurora"``.
        units: Units of the values, such as ``"MHz"``.

    Raises:
        ValueError: If the axes are empty, unordered, off the lattice or out
            of range, or the values do not match the axes or are not finite.
    """

    latitudes: tuple[float, ...]
    longitudes: tuple[float, ...]
    latitude_step: float
    longitude_step: float
    values: tuple[tuple[float, ...], ...]
    quantity: str
    units: str

    def __post_init__(self) -> None:
        _check_axis("latitudes", self.latitudes, self.latitude_step)
        _check_axis("longitudes", self.longitudes, self.longitude_step)
        if self.latitudes[0] < -90 or self.latitudes[-1] > 90:
            raise ValueError("latitudes must lie within [-90, 90]")
        if self.longitudes[0] < -180 or self.longitudes[-1] >= 360:
            raise ValueError("longitudes must lie within [-180, 360)")
        if self.longitudes[-1] - self.longitudes[0] >= 360:
            raise ValueError("longitudes must span less than 360 degrees")
        if len(self.values) != len(self.latitudes):
            raise ValueError(
                f"{len(self.values)} rows for {len(self.latitudes)} latitudes"
            )
        for row in self.values:
            if len(row) != len(self.longitudes):
                raise ValueError(
                    f"a row has {len(row)} values for {len(self.longitudes)} longitudes"
                )
            if not all(math.isfinite(v) for v in row):
                raise ValueError("values must be finite numbers")

    @property
    def shape(self) -> tuple[int, int]:
        """Number of latitudes and of longitudes."""
        return len(self.latitudes), len(self.longitudes)

    @property
    def is_contiguous(self) -> bool:
        """Whether both axes have no gaps between their first and last value."""
        return _contiguous(self.latitudes, self.latitude_step) and _contiguous(
            self.longitudes, self.longitude_step
        )

    def value_at(self, latitude: float, longitude: float) -> float:
        """Return the value of the cell centred at ``latitude``, ``longitude``.

        The longitude may be given in either convention (``-1`` and ``359``
        are the same cell).

        Raises:
            KeyError: If no cell of the grid is centred there.
        """
        row = _find(self.latitudes, latitude)
        column = _find(self.longitudes, longitude)
        if column is None:
            column = _find(self.longitudes, longitude - 360.0)
        if column is None:
            column = _find(self.longitudes, longitude + 360.0)
        if row is None or column is None:
            raise KeyError((latitude, longitude))
        return self.values[row][column]

    def value_near(self, latitude: float, longitude: float) -> float | None:
        """Return the value of the cell that holds the point, or ``None``.

        A cell spans half a step on each side of its centre. A point on the
        border between two cells takes the cell to its north or east; the
        outer edges of the grid belong to its outer cells. The longitude may
        be given in either convention (-180 to 180 or 0 to 360).

        Returns:
            The value, or ``None`` if no cell holds the point: outside the
            grid, or in a gap of a reduced grid.

        Raises:
            ValueError: If the latitude is not within [-90, 90] or the
                longitude not within [-180, 360].
        """
        if not (math.isfinite(latitude) and -90 <= latitude <= 90):
            raise ValueError(f"latitude must lie within [-90, 90], got {latitude!r}")
        if not (math.isfinite(longitude) and -180 <= longitude <= 360):
            raise ValueError(
                f"longitude must lie within [-180, 360], got {longitude!r}"
            )
        row = _holding(self.latitudes, self.latitude_step, (latitude,))
        column = _holding(
            self.longitudes,
            self.longitude_step,
            (longitude, longitude - 360.0, longitude + 360.0),
        )
        if row is None or column is None:
            return None
        return self.values[row][column]

    def cells(self) -> Iterator[tuple[float, float, float]]:
        """Yield ``(latitude, longitude, value)`` for every cell, row by row."""
        for latitude, row in zip(self.latitudes, self.values, strict=True):
            for longitude, value in zip(self.longitudes, row, strict=True):
                yield latitude, longitude, value

    def wrapped(self) -> "Grid":
        """Return the same grid with longitudes in [-180, 180).

        Columns are reordered so that longitudes stay increasing. A grid
        already in that range is returned unchanged.

        Raises:
            ValueError: If the wrapped longitudes do not fit one lattice
                (360 is not a multiple of the step).
        """
        if self.longitudes[0] >= -180 and self.longitudes[-1] < 180:
            return self
        order = sorted(
            range(len(self.longitudes)),
            key=lambda j: wrap_longitude(self.longitudes[j]),
        )
        return Grid(
            latitudes=self.latitudes,
            longitudes=tuple(wrap_longitude(self.longitudes[j]) for j in order),
            latitude_step=self.latitude_step,
            longitude_step=self.longitude_step,
            values=tuple(tuple(row[j] for j in order) for row in self.values),
            quantity=self.quantity,
            units=self.units,
        )


class GridProduct(Protocol):
    """A product made of a grid and the times its content declares.

    :class:`OvationAurora` and :class:`DrapFrequencies` follow it; the
    exports accept anything that does.
    """

    @property
    def grid(self) -> Grid:
        """The values and their axes."""
        ...

    @property
    def source_url(self) -> str:
        """Where the content came from."""
        ...

    @property
    def data_time(self) -> datetime:
        """The time the data describes, in UTC."""
        ...

    @property
    def times(self) -> Mapping[str, datetime]:
        """Every time the content declares, by name, in UTC."""
        ...


@dataclass(frozen=True, slots=True)
class OvationAurora:
    """The OVATION aurora nowcast: a global 1-degree grid.

    The source does not state what the values are. They are integers, 0 to
    a few tens; reading them as the probability of visible aurora in percent
    is an assumption (``docs/FONTI.md``), which ``grid.units`` (``"%"``)
    follows.

    Attributes:
        grid: The values, with longitudes 0 to 359 as delivered.
        observation_time: ``Observation Time`` of the source.
        forecast_time: ``Forecast Time`` of the source (about an hour after
            the observation).
        source_url: Where the content came from.

    Raises:
        ValueError: If a time is not an aware datetime in UTC.
    """

    grid: Grid
    observation_time: datetime
    forecast_time: datetime
    source_url: str

    def __post_init__(self) -> None:
        check_utc("observation_time", self.observation_time)
        check_utc("forecast_time", self.forecast_time)

    @property
    def data_time(self) -> datetime:
        """The observation time."""
        return self.observation_time

    @property
    def times(self) -> dict[str, datetime]:
        """``observation_time`` and ``forecast_time``."""
        return {
            "observation_time": self.observation_time,
            "forecast_time": self.forecast_time,
        }


@dataclass(frozen=True, slots=True)
class DrapFrequencies:
    """D-RAP: D-region absorption, as a frequency on a global grid.

    The source only says "Frequency (MHz) as a function of Latitude and
    Longitude". Reading it as the highest frequency affected by
    D-region absorption, as ``grid.quantity`` does, is an assumption
    (``docs/FONTI.md``).

    The text fields are copied from the comment lines of the source, as
    data; an empty field is ``None``.

    Attributes:
        grid: Frequencies in MHz, on a 2 by 4 degree grid.
        valid_at: ``Product Valid At`` of the source.
        estimated_recovery_time: ``Estimated Recovery Time``, as written
            (for example ``"No Estimate"``).
        xray_message: ``X-RAY Message``.
        xray_warning: ``X-RAY Warning``.
        proton_message: ``Proton Message``.
        proton_warning: ``Proton Warning``.
        source_url: Where the content came from.

    Raises:
        ValueError: If ``valid_at`` is not an aware datetime in UTC.
    """

    grid: Grid
    valid_at: datetime
    estimated_recovery_time: str | None
    xray_message: str | None
    xray_warning: str | None
    proton_message: str | None
    proton_warning: str | None
    source_url: str

    def __post_init__(self) -> None:
        check_utc("valid_at", self.valid_at)

    @property
    def data_time(self) -> datetime:
        """The time the product is valid at."""
        return self.valid_at

    @property
    def times(self) -> dict[str, datetime]:
        """``valid_at``."""
        return {"valid_at": self.valid_at}
