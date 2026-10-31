"""A stage of the workflow: what it writes, which process may carry it, which stories run it, and what its gate holds it
to. Which stages there are, in which order, is the workflow's (`workflow.py`), loaded from its repository."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import Value


#: A hand-over's file name — one word or a hyphenated phrase, `.md`, no folder.
HAND_OVER = re.compile(r"[a-z][a-z-]*\.md")

#: A key of the stack profile — `format`, `e2eTest`, `test.integration`.
PROFILE_KEY = re.compile(r"[a-z][A-Za-z0-9]*(\.[a-z][a-z0-9-]*)?")


class StageName(Value):
    """A stage by its name — `plan`, `build`, `integrate`. Read from a decision record as its author wrote it, so it is
    not held to a form: whether the pipeline knows the stage is the stage table's question."""

    value: str


class HandOver(Value):
    """A hand-over file a stage writes under the run folder — `plan.md`."""

    value: str

    def __post_init__(self) -> None:
        if not HAND_OVER.fullmatch(self.value):
            raise ValueError(f"{self.value!r} is no hand-over file name")


class ProfileCommand(Value):
    """A command the stack profile declares under this key — `architecture`, `format`."""

    value: str

    def __post_init__(self) -> None:
        if not PROFILE_KEY.fullmatch(self.value):
            raise ValueError(f"{self.value!r} is no key of the stack profile")


class StageText(Value):
    """What a stage is for, in a person's words — the workflow carries it, the factory decides nothing on it."""

    value: str


class StoryKind(enum.Enum):
    """What a story is: a change an actor sees, a journey across delivered stories, behaviour adopted as it is, or a
    task that changes nothing an actor sees (a refactoring, a dependency, a finding without a change of behaviour)."""

    STORY = "story"
    JOURNEY = "journey"
    ADOPT = "adopt"
    TASK = "task"


class SpecHome(enum.Enum):
    """Where a story's criteria hold once it is delivered: a journey's among the project's journeys, with no feature;
    every other kind's in its context, under its feature or the context's own."""

    JOURNEYS = "journeys"
    CONTEXT = "context"

    @classmethod
    def of(cls, kind: StoryKind) -> SpecHome:
        return cls.JOURNEYS if kind is StoryKind.JOURNEY else cls.CONTEXT


class Window(enum.Enum):
    """The shared process that may carry several stages under one name."""

    BUILDER = "builder"
    VERIFIER = "verifier"


class Trait(enum.Enum):
    """What holds for a stage:

    - GATED       a gate runs for it (`--stage <name>`);
    - POST_GATED  that gate runs after its file is written, so a pass vouches for the file;
    - TESTED      its gate runs the mapped tests (red or green) and the checks before them;
    - RED         a story's mapped tests are red at its gate (a journey's and an adoption's green);
    - LISTS       its hand-over lists the files it changed, and its gate holds it to that list;
    - GUARDED     it writes production code, under the profile's guard skill;
    - SUITE       its gate runs the policy's required suites whole;
    - IN_ORDER    a step of the story's run order (adopt and integrate are steps after it)."""

    GATED = "gated"
    POST_GATED = "post_gated"
    TESTED = "tested"
    RED = "red"
    LISTS = "lists"
    GUARDED = "guarded"
    SUITE = "suite"
    IN_ORDER = "in_order"


ALL_KINDS = frozenset(StoryKind)

#: The kinds whose criteria are proven by tests: a task has none — the existing suite, run whole, is its evidence.
TESTED_KINDS = frozenset((StoryKind.STORY, StoryKind.JOURNEY, StoryKind.ADOPT))


class Stage(Value):
    """One stage of the workflow."""

    name: StageName
    hand_over: typing.Optional[HandOver] = None
    window: typing.Optional[Window] = None
    kinds: typing.FrozenSet[StoryKind] = frozenset((StoryKind.STORY,))
    traits: typing.FrozenSet[Trait] = frozenset((Trait.GATED, Trait.IN_ORDER))
    #: the profile's extra commands its gate runs, in this order; a key not declared is skipped and named — a gate
    #: failing on a command nobody configured gets switched off
    commands: typing.Tuple[ProfileCommand, ...] = ()
    #: the hand-overs whose size its gate weighs against the criteria
    sizes: typing.Tuple[HandOver, ...] = ()
    #: what it is for, as a person reads it
    about: typing.Optional[StageText] = None
