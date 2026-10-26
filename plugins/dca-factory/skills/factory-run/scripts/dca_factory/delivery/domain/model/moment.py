"""When something happened."""

from __future__ import annotations

import re

from ....building_blocks import Value

#: A moment as the project's files write it: UTC, to the second.
MOMENT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class Moment(Value):
    """When something happened, in UTC to the second — `2026-10-25T10:00:00Z`."""

    value: str

    def __post_init__(self) -> None:
        if not MOMENT.match(self.value):
            raise ValueError(f"{self.value!r} is no moment (YYYY-MM-DDTHH:MM:SSZ)")
