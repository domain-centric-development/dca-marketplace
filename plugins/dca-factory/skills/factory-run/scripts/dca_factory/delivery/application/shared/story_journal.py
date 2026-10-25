"""A story's journal, as the use cases read and add to it."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import Store
from ...domain.model.story import StoryId
from .story_claims import ClaimHeld
from ...domain.model.usage import Usage


@dataclasses.dataclass(frozen=True)
class Window:
    """A part of a story's work outside a stage, by its name — opened by a request's process on the story."""

    story: StoryId
    name: str


class StoryJournal(Store, typing.Protocol):
    """Each story's journal: one event a line, the story's record."""

    def question_pass_ran(self, story: StoryId) -> bool:
        """Whether the story's question pass ran on the story as it stands — its last `questioned` mark names the
        story's digest now."""
        ...

    def windows_opened_by(self, request: str) -> typing.Sequence[Window]:
        """Every window a request's process opened, story by story in the order of their journals."""
        ...

    def book(self, window: Window, usage: Usage, tool: str, request: str) -> None:
        """One `usage` line on the window: the share of a request's usage, its tool and the request."""
        ...

    def delivered_over_claim(self, story: StoryId, who: str) -> None:
        """A note that the story was delivered by hand over another factory's claim, by force."""
        ...

    def owned_confirmed(self, story: StoryId, parts: typing.Sequence[str]) -> None:
        """The person confirmed what a stage changed of theirs."""
        ...

    def claimed_elsewhere(self, story: StoryId, held: ClaimHeld) -> None:
        """A note that another factory holds the story."""
        ...
