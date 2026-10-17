"""Checks shared by the model classes, run in ``__post_init__``."""

from collections.abc import Sized
from datetime import datetime, timedelta


def check_utc(name: str, value: datetime | None) -> None:
    """Raise ``ValueError`` unless ``value`` is ``None`` or an aware UTC time."""
    if value is not None and value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an aware datetime in UTC, got {value!r}")


def check_values(values: Sized) -> None:
    """Raise ``ValueError`` if ``values`` is empty."""
    if not values:
        raise ValueError("values must not be empty")
