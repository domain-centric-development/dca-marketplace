"""The plan as the gate reads it: its levels, its hand-over, the files it plans, what it adopts, its digest."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .profile_facts import ByteSize
from .story_state import Detail
from .story_words import Place, ScenarioKey, Selector


class PlanLevels(Value):
    """The levels the plan gave: the keys its skeleton left without one, the keys it gave `browser-only`, the keys
    it gave `integration (adapter: …)` alone — an incoming adapter's translation, tested against a stubbed input
    port by design — and the keys it gave both shapes, the adapter's beside one through the real input port."""

    unfinished: typing.Tuple[ScenarioKey, ...]
    browser_only: typing.FrozenSet[ScenarioKey]
    adapter: typing.FrozenSet[ScenarioKey]
    both: typing.FrozenSet[ScenarioKey]


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
