"""The plan as the gate reads it: its levels, its hand-over, the files it plans, what it adopts, its digest."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .profile_facts import ByteSize, ContractNumber
from .story_state import Detail
from .story_words import Place, ScenarioKey, Selector


class PlannedTest(Value):
    """The adapter test the plan names for a criterion's adapter shape — `<Class>#<method>`, named after the state it
    shows — or none, where the shape names no test."""

    key: ScenarioKey
    test: typing.Optional[Selector]

    def found_in(self, selectors: typing.Iterable[Selector]) -> bool:
        """Whether one of the criterion's mapped tests is this one: the same method, in a class of the same simple
        name — the plan may name the class without its package."""
        if self.test is None:
            return False
        cls, _, method = self.test.value.partition("#")
        simple = cls.rsplit(".", 1)[-1]
        for selector in selectors:
            other, _, other_method = selector.value.partition("#")
            if other_method == method and other.rsplit(".", 1)[-1] == simple:
                return True
        return False


class PlanLevels(Value):
    """The levels the plan gave: the keys its skeleton left without one, the keys it gave `browser-only`, the keys
    it gave `integration (adapter: …)` alone — an incoming adapter's translation, tested against a stubbed input
    port by design — and the keys it gave both shapes, the adapter's beside one through the real input port."""

    unfinished: typing.Tuple[ScenarioKey, ...]
    browser_only: typing.FrozenSet[ScenarioKey]
    adapter: typing.FrozenSet[ScenarioKey]
    both: typing.FrozenSet[ScenarioKey]
    named: typing.Tuple[PlannedTest, ...] = ()


class HandOverSize(Value):
    """A hand-over and the bytes of it the stage wrote."""

    name: HandOverName
    size: ByteSize


class HandOverName(Value):
    value: str


class FileChange(enum.Enum):
    NEW = "new"
    REMOVED = "removed"


class PlannedFile(Value):
    """A file the plan's `## Files` says becomes new or is removed, and whether it is there after the build."""

    place: Place
    change: FileChange
    _exists: bool

    @property
    def exists(self) -> bool:
        """Whether the file is there after the build."""
        return self._exists


class AdoptRow(Value):
    """A scenario the plan found holding on today's code alone, with the test that shows it."""

    key: ScenarioKey
    test: Selector
    _present: bool

    @property
    def present(self) -> bool:
        """Whether the test is there."""
        return self._present


class PlanAdoption(Value):
    """The plan's `## Adopt`: the scenarios of the story that hold already and no delivered story carries."""

    rows: typing.Tuple[AdoptRow, ...]

    def whole(self) -> Detail:
        """Why the whole story is adopted, as its answered line says it: every scenario holds, with the test that
        shows it."""
        return Detail("every scenario holds on today's code, and no delivered story carries it — the plan adopted the "
                      "story: " + self.held().value)

    def held(self) -> Detail:
        """The scenarios that hold, each with the test that shows it: `key (test), …`."""
        return Detail(", ".join(f"{row.key.value} ({row.test.value})" for row in self.rows))

    def keys(self) -> typing.Tuple[ScenarioKey, ...]:
        """The scenarios that hold."""
        return tuple(row.key for row in self.rows)


class PlannedDigest(enum.Enum):
    """The story against the digest its plan gate recorded: no digest, the story changed since, or the same."""

    MISSING = "missing"
    CHANGED = "changed"
    SAME = "same"


class PlanStamp(enum.Enum):
    """What the journal knows of the plan as it stands: a passing plan gate stamped it with its contract; plan gates
    passed before stamps existed and none stamped it; or no gate has passed it yet — a new or changed plan."""

    STAMPED = "stamped"
    BEFORE_STAMPS = "before stamps"
    NEW = "new"


#: The contract a plan from before the stamps is held to: the one before the first check of the plan's form
#: (`tests-planned`, contract 34). A plan keeps the rules it was written under.
UNSTAMPED_PLAN_CONTRACT = ContractNumber(33)


class PlanOrigin(Value):
    """Under which contract the story's plan came about, as the journal records it."""

    stamp: PlanStamp
    contract: typing.Optional[ContractNumber] = None

    def held_to(self, profile: ContractNumber) -> ContractNumber:
        """The contract a check of the plan's form holds this plan to: the profile's, but never a later one than the
        plan was written under — a check introduced after the plan came about does not reach back to it."""
        if self.stamp is PlanStamp.STAMPED and self.contract is not None:
            return ContractNumber(min(profile.value, self.contract.value))
        if self.stamp is PlanStamp.BEFORE_STAMPS:
            return ContractNumber(min(profile.value, UNSTAMPED_PLAN_CONTRACT.value))
        return profile
