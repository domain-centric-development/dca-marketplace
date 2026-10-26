"""What a story does to the spec, as the spec's open host service derives it from the story, its plan and the spec."""

from __future__ import annotations

import dataclasses
import typing

#: A criterion: its key, the feature it stands under ("" for the context itself), its lines.
Criterion = typing.Tuple[str, str, typing.Tuple[str, ...]]


@dataclasses.dataclass(frozen=True)
class SpecDeltaFacts:
    """The story's spec, its feature, its criteria and those the spec holds, the verb the spec derives per key, and
    the plan's delta: the keys it moves, those it removes with why, the rules it renames with the keys that follow
    them, the features it brings."""

    context: str
    feature: str
    story: typing.Tuple[Criterion, ...]
    held: typing.Tuple[Criterion, ...]
    verbs: typing.Mapping[str, str]
    moves: typing.FrozenSet[str]
    removes: typing.Mapping[str, str]
    renames: typing.Tuple[typing.Tuple[str, str, typing.Tuple[str, ...]], ...]
    features: typing.Tuple[str, ...]


class SpecDeltas(typing.Protocol):
    def facts(self, story: str) -> typing.Optional[SpecDeltaFacts]:
        """The story's delta; None for a story that names no spec."""
        ...
