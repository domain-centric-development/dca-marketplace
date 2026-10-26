"""Who asks or answers."""

from __future__ import annotations


from ....building_blocks import Value


class Person(Value):
    """Who asks or answers, as they name themselves — one line, its spaces collapsed."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", " ".join(self.value.split()))
