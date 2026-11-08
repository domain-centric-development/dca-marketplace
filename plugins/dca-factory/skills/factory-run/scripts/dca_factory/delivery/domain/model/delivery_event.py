"""What every event of the delivery context carries: when it happened, and the story it concerns where it concerns
one — the journal it is kept in follows from it."""

from __future__ import annotations

import typing

from .moment import Moment
from .story import StoryId


@typing.runtime_checkable
class DeliveryEvent(typing.Protocol):
    """An event of the delivery context: its moment, its story or none (a record of the project's own)."""

    @property
    def at(self) -> Moment: ...

    @property
    def story(self) -> typing.Optional[StoryId]: ...
