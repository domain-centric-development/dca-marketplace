"""An outcome several use cases share."""

from __future__ import annotations

import dataclasses

from ....building_blocks import Refusal


@dataclasses.dataclass(frozen=True)
class NeedsSkill(Refusal):
    """Not settled without judgement: the files do not say everything the press implies, so the skill a session would
    run works it — nothing was written."""

    why: str = ""
