"""Learning's own words: a story and a record as delivery names them, a count, a piece of text, a moment."""

from __future__ import annotations

from ....building_blocks import Id, Value


class StoryId(Id):
    """A story, by the id delivery gives it."""

    value: str


class RecordId(Id):
    """A lesson record, by its id in the decision inbox."""

    value: str


class Count(Value):
    value: int


class Detail(Value):
    """A piece of text as written — a key, a sentence, a source."""

    value: str


class Moment(Value):
    """When something was asked, as UTC ISO 8601."""

    value: str
