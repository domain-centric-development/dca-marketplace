"""A story's acceptance records, as a correction asks them."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.decision_record import RecordId
from ...domain.model.story import StoryId


class Acceptances(OutputPort, typing.Protocol):
    """What the acceptance records say about a delivered story."""

    def correction_of(self, story: StoryId) -> typing.Optional[RecordId]:
        """The last acceptance record, where a person answered it with a correction — None otherwise."""
        ...

    def cited(self, story: StoryId, record: RecordId) -> bool:
        """Whether the story names the record — the correction written into it."""
        ...

    def changed_since_accepted(self, story: StoryId) -> typing.Sequence[str]:
        """The criteria the story changed since an earlier acceptance took them, by key — none without one."""
        ...
