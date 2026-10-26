"""What a person means by `/factory-run <argument>` — decided here, not by a model: one word naming a story is that
story; one word naming none is an unknown id, never a new story (a typo stays a typo); more than one word is a wish,
for the backlog to turn into a story; nothing is the backlog."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .story import StoryId


class ArgumentMeaning(enum.Enum):
    """What the argument asks for."""

    BACKLOG = "backlog"     # nothing given: the backlog runs
    STORY = "story"         # one word, a story's id: that story runs
    UNKNOWN = "unknown"     # one word naming no story: refused, never taken for a new one
    WISH = "wish"           # more than one word: a wish the backlog turns into a story


class RunArgument(Value):
    """What follows `/factory-run`, as typed."""

    value: str

    def single_word(self) -> typing.Optional[RunArgument]:
        """The one word it is, where it is one — the word a story's id may be."""
        words = self.value.split()
        return RunArgument(words[0]) if len(words) == 1 else None

    def meaning(self, named: typing.Optional[StoryId]) -> ArgumentMeaning:
        """<named> is the story its single word names, or None."""
        words = self.value.split()
        if not words:
            return ArgumentMeaning.BACKLOG
        if len(words) > 1:
            return ArgumentMeaning.WISH
        return ArgumentMeaning.STORY if named is not None else ArgumentMeaning.UNKNOWN
