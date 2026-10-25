"""An epic, as the other aggregates reference it."""

from __future__ import annotations

import dataclasses

from ....building_blocks import Id


@dataclasses.dataclass(frozen=True)
class EpicId(Id):
    """The name of one epic: its folder under the epics, or the `id:` of its `epic.md`."""

    value: str
