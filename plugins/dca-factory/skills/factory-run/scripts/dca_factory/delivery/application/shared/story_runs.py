"""What the runs know about the stories: the checkout's holders, a gate's pass, the passes and claims kept."""

from __future__ import annotations

import typing

from ...domain.model.moment import Moment
from ...domain.model.story import Delivery, StoryId


class StoryRuns(typing.Protocol):
    """The stories' runs, as a command beside a run asks them."""

    def holding_checkout(self, exclude: StoryId) -> typing.Sequence[StoryId]:
        """The other stories with unfinished code in the checkout — past their test stage, not delivered."""
        ...

    def gate_passed(self, story: StoryId) -> bool:
        """Whether the gate's pass that delivered the story is on record."""
        ...

    def keep_pass(self, story: StoryId) -> str:
        """The pass the story ran, kept aside before it runs again from plan — where it went, "" without a run."""
        ...

    def keep_claim(self, story: StoryId, claim: Delivery, at: Moment) -> str:
        """The claim a delivery made, kept as a line of the story's evidence — where it went."""
        ...
