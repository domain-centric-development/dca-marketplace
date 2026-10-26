"""What a plan changes in the spec."""

from __future__ import annotations

import dataclasses
import enum
import typing

from ....building_blocks import Value
from .criterion import CriterionKey, FeatureName, Place, RuleText


class Verdict(enum.Enum):
    """What a story's criterion is to the spec: new, the same word for word, or changed."""

    ADDS = "adds"
    HOLDS = "holds"
    CHANGES = "changes"


class Reason(Value):
    """Why a criterion is removed, as the plan says it — empty where it says nothing."""

    value: str


class Move(Value):
    """A criterion leaving one place for another."""

    source: Place
    destination: Place


class Rename(Value):
    """A rule reworded: its old text, its new one."""

    old: RuleText
    new: RuleText


class Delta(Value):
    """The plan's `## Spec delta`: criteria added, changed, held, removed (with why), rules renamed, criteria moved
    between features, features born."""

    adds: typing.FrozenSet[CriterionKey] = frozenset()
    changes: typing.FrozenSet[CriterionKey] = frozenset()
    holds: typing.FrozenSet[CriterionKey] = frozenset()
    removes: typing.Mapping[CriterionKey, Reason] = dataclasses.field(default_factory=dict)
    renames: typing.Tuple[Rename, ...] = ()
    moves: typing.Mapping[CriterionKey, Move] = dataclasses.field(default_factory=dict)
    features: typing.FrozenSet[FeatureName] = frozenset()

    def named(self, verdict: Verdict) -> typing.FrozenSet[CriterionKey]:
        """The keys the delta names with this verb."""
        return {Verdict.ADDS: self.adds, Verdict.CHANGES: self.changes, Verdict.HOLDS: self.holds}[verdict]


class Problem(Value):
    """What is wrong with a delta or with where a story puts its criteria, in one sentence."""

    value: str
