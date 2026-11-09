"""What a stage worked from and may not change: the brief it was given, the person's parts and the rounds run."""

from __future__ import annotations

import typing

from ....building_blocks import Value
from .story_state import Detail, Rounds
from .story_words import Place
from .verdict import CheckName, Findings, Said


class RoundsRecord(Value):
    """The rounds a story ran without converging, as its counter holds them — None where the counter is no number."""

    place: Place
    rounds: typing.Optional[Rounds]


class OwnedPart(Value):
    """Something of the person's a stage may not change: the story, an answer."""

    value: str


class OwnedFacts(Value):
    """What a stage changed of the person's: the parts a past window marked, and those changed while this one runs —
    None where nothing records what they were."""

    marked: typing.Tuple[OwnedPart, ...]
    changed: typing.Optional[typing.Tuple[OwnedPart, ...]]


class BriefFacts(Value):
    """Which brief a stage worked from: the digest of the one the runner gave it — None where it gave none, a stage
    run by hand —, the one its hand-over <place> names — None where it names none."""

    place: Place
    given: typing.Optional[Detail]
    named: typing.Optional[Detail]

    def findings(self) -> Findings:
        """A stage the runner gave a brief names it in its hand-over: one that worked from another brief, or names
        none, is refused — what it was told is not what it did."""
        if self.given is None:
            return ()
        if self.named is None:
            return (CheckName("brief").fail(Said(
                f"{self.place.value} names no brief — end it with the line `brief: {self.given.value}`, the digest "
                f"the brief you were given ends with, after reading that brief")),)
        if self.named != self.given:
            return (CheckName("brief").fail(Said(
                f"{self.place.value} names the brief {self.named.value}, but the stage was given "
                f"{self.given.value} — read the brief you were given and work by it")),)
        return (CheckName("brief").ok(Said(f"the stage worked from the brief it was given ({self.given.value})")),)
