"""The pipeline's stages: what each one writes, which process may carry it, which stories run it, and what its gate
holds it to. Everything the gate, the cli and the runner know about a stage is here; nothing else names a stage to
decide on it."""

from __future__ import annotations

import dataclasses
import enum
import typing

from ....building_blocks import DomainService, Value


@dataclasses.dataclass(frozen=True)
class StageName(Value):
    """A stage by its name — `plan`, `build`, `integrate`."""

    value: str


@dataclasses.dataclass(frozen=True)
class HandOver(Value):
    """A hand-over file a stage writes under the run folder — `plan.md`."""

    value: str


@dataclasses.dataclass(frozen=True)
class ProfileCommand(Value):
    """A command the stack profile declares under this key — `architecture`, `format`."""

    value: str


class StoryKind(enum.Enum):
    """What a story is: a change an actor sees, a journey across delivered stories, behaviour adopted as it is, or a
    task that changes nothing an actor sees (a refactoring, a dependency, a finding without a change of behaviour)."""

    STORY = "story"
    JOURNEY = "journey"
    ADOPT = "adopt"
    TASK = "task"


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


@dataclasses.dataclass(frozen=True)
class Stage(Value):
    """One row of the pipeline."""

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


def stage(name: StageName, hand_over: typing.Optional[HandOver] = None, window: typing.Optional[Window] = None,
          kinds: typing.FrozenSet[StoryKind] = frozenset((StoryKind.STORY,)), traits: typing.Iterable[Trait] = (),
          without: typing.Iterable[Trait] = (), commands: typing.Tuple[ProfileCommand, ...] = (),
          sizes: typing.Tuple[HandOver, ...] = ()) -> Stage:
    """A row: gated and in the run order unless <without> says otherwise, with the further <traits>."""
    held = (frozenset((Trait.GATED, Trait.IN_ORDER)) | frozenset(traits)) - frozenset(without)
    return Stage(name, hand_over, window, kinds, held, commands, sizes)


ARCHITECTURE, FORMAT = ProfileCommand("architecture"), ProfileCommand("format")

PIPELINE: typing.Tuple[Stage, ...] = (
    stage(StageName("plan"), HandOver("plan.md"), Window.BUILDER, ALL_KINDS),
    stage(StageName("test"), HandOver("tests.md"), Window.BUILDER, TESTED_KINDS,
          (Trait.LISTS, Trait.POST_GATED, Trait.TESTED, Trait.RED), sizes=(HandOver("plan.md"), HandOver("tests.md"))),
    stage(StageName("build"), HandOver("build.md"), Window.BUILDER, frozenset((StoryKind.STORY, StoryKind.TASK)),
          (Trait.LISTS, Trait.GUARDED, Trait.POST_GATED, Trait.TESTED, Trait.SUITE), commands=(ARCHITECTURE, FORMAT),
          sizes=(HandOver("build.md"),)),
    # The tidy stage changes no behaviour, so its whole claim is that everything still holds: the same commands
    # as the build stage, run again after the refactor.
    stage(StageName("tidy"), HandOver("tidy.md"), Window.BUILDER, frozenset((StoryKind.STORY, StoryKind.TASK)),
          (Trait.LISTS, Trait.GUARDED, Trait.POST_GATED, Trait.TESTED, Trait.SUITE), commands=(ARCHITECTURE, FORMAT),
          sizes=(HandOver("tidy.md"),)),
    stage(StageName("judge"), HandOver("judge.md"), Window.VERIFIER, ALL_KINDS, without=(Trait.GATED,)),
    stage(StageName("document"), HandOver("document.md"), Window.VERIFIER,
          frozenset((StoryKind.STORY, StoryKind.JOURNEY, StoryKind.TASK)), (Trait.POST_GATED,),
          commands=(ARCHITECTURE,), sizes=(HandOver("judge.md"), HandOver("document.md"))),
    # Nothing built: the adopt gate delivers an adopted story after its judge.
    stage(StageName("adopt"), kinds=frozenset((StoryKind.ADOPT,)), without=(Trait.IN_ORDER,)),
    # The story on the main line as it is now: everything the tidy gate holds the story to, once more.
    stage(StageName("integrate"), HandOver("integrate.md"), kinds=ALL_KINDS, traits=(Trait.TESTED, Trait.SUITE),
          without=(Trait.IN_ORDER,), commands=(ARCHITECTURE, FORMAT)),
)


class Pipeline(DomainService):
    """The run order of a story, by its kind."""

    @staticmethod
    def order(kind: StoryKind) -> typing.Tuple[StageName, ...]:
        return tuple(s.name for s in PIPELINE if Trait.IN_ORDER in s.traits and kind in s.kinds)
