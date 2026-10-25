"""What the main line and the checkout hold — asked by the schedule for the stories it may start, not for every story.

A gateway, not supplied facts: each answer costs a look into the repository, and the schedule needs it only for a
story that could run and for the checkout when nothing holds it; reading it up front would ask the repository once per
delivered story on every schedule."""

from __future__ import annotations

import typing

from ....building_blocks import DomainGateway
from ..model.story import StoryId
from ..model.story_state import Detail


class MainLine(DomainGateway, typing.Protocol):
    """The main line as the checkout has it."""

    def uncommitted(self, story: StoryId) -> typing.Optional[Detail]:
        """Why the story's file is not on the main line — not committed, or changed since —, or None."""
        ...

    def stray(self) -> typing.Tuple[Detail, ...]:
        """The files changed in the checkout that no story's run claims."""
        ...
