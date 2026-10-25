"""What a product made of records says about the records it could not read.

The JSON products made of records (indices, solar wind, GOES, alerts) are
read record by record: one that cannot be read goes to the model's
``skipped`` instead of making the whole product fail.
"""

from dataclasses import dataclass

__all__ = ["SkippedRecord"]


@dataclass(frozen=True, slots=True)
class SkippedRecord:
    """A record of the source that the parser could not read.

    Attributes:
        index: 0-based position of the record in the JSON array.
        field: The field that is wrong, when one is.
        reason: What is wrong, for a person to read.
    """

    index: int
    field: str | None
    reason: str

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError(f"index must not be negative, got {self.index}")
