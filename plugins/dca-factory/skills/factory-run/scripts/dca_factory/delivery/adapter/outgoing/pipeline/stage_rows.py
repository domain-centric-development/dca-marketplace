"""The workflow's stages as the adapters read them: one flat row per stage — the loaded workflow's in words and flags
—, the run orders by kind, the shared windows, the hand-over each stage writes. Functions, asked when they run: the
workflow is loaded by the composition root, after the modules are imported."""

from __future__ import annotations

import typing

from ....application.delivery.pipeline_workflow import workflow
from ....domain.model.stage import Stage as PipelineStage, StoryKind, TESTED_KINDS as DOMAIN_TESTED_KINDS, Trait
from ....domain.model.verdict import FORM_CHECKS as DOMAIN_FORM_CHECKS


class Stage(typing.NamedTuple):
    """One row of the pipeline, flat — the domain's `Stage` in words and flags."""
    name: str
    #: the hand-over it writes under the run folder ("" — a gate-only step)
    file: str = ""
    #: the shared process that may carry it ("builder", "verifier"), "" — its own
    window: str = ""
    #: the story kinds that run it (story, journey, adopt, task)
    kinds: typing.Tuple[str, ...] = ("story",)
    #: a gate runs for it (`--stage <name>`)
    gated: bool = True
    #: that gate runs after its file is written, so a pass vouches for the file
    post_gated: bool = False
    #: the profile's extra commands its gate runs, in this order; a key not
    #: declared is skipped and named — a gate failing on a command nobody configured gets switched off
    commands: typing.Tuple[str, ...] = ()
    #: its gate runs the mapped tests (red or green) and the checks before them
    tested: bool = False
    #: a story's mapped tests are red at its gate (a journey's and an adoption's green)
    red: bool = False
    #: the hand-overs whose size its gate weighs against the criteria
    sizes: typing.Tuple[str, ...] = ()
    #: its hand-over lists the files it changed, and its gate holds it to that list
    lists: bool = False
    #: it writes production code, under the profile's guard skill (`carrier.guard`)
    guarded: bool = False
    #: its gate runs the policy's required suites whole
    suite: bool = False
    #: a step of the story's run order (adopt and integrate are steps after it)
    in_order: bool = True


#: The kinds of story, in the domain's order.
ALL_KINDS = tuple(kind.value for kind in StoryKind)


#: A task (WP-106) changes nothing an actor sees — a refactoring, a finding without a change of behaviour, a dependency
#: or build change: no criterion, so no test stage; the existing suite, run whole, is its evidence.
TESTED_KINDS = tuple(kind.value for kind in StoryKind if kind in DOMAIN_TESTED_KINDS)


def flat_row(row: PipelineStage) -> Stage:
    """A stage of the workflow as the gate, the runner and the cli read it: words and flags."""
    return Stage(row.name.value, row.hand_over.value if row.hand_over else "",
                 row.window.value if row.window else "", tuple(k.value for k in StoryKind if k in row.kinds),
                 Trait.GATED in row.traits, Trait.POST_GATED in row.traits, tuple(c.value for c in row.commands),
                 Trait.TESTED in row.traits, Trait.RED in row.traits, tuple(h.value for h in row.sizes),
                 Trait.LISTS in row.traits, Trait.GUARDED in row.traits, Trait.SUITE in row.traits,
                 Trait.IN_ORDER in row.traits)


def all_stages() -> typing.Tuple[Stage, ...]:
    """The workflow's stages, one flat row each — the loaded workflow's (`workflow/stages/`), in the adapters' words."""
    return tuple(flat_row(row) for row in workflow().stages)


def stage_named() -> typing.Dict[str, Stage]:
    return {stage.name: stage for stage in all_stages()}


def stage_files() -> typing.Dict[str, str]:
    """The hand-over each stage of the run order writes."""
    return {s.name: s.file for s in all_stages() if s.in_order}


def stage_windows() -> typing.Dict[str, typing.Tuple[str, ...]]:
    """One process may carry several stages and mark its window under one name: the shared builder (plan to tidy) and
    the shared verifier (judge, then document). The journal, the changed-files record and the usage are that window's;
    every stage still writes its own file."""
    stages = all_stages()
    return {w: tuple(s.name for s in stages if s.window == w) for w in dict.fromkeys(s.window for s in stages if s.window)}


def stage_commands() -> typing.Dict[str, typing.Tuple[str, ...]]:
    """Extra profile commands run per stage, in this order."""
    return {s.name: s.commands for s in all_stages() if s.gated}


def post_gated_stages() -> typing.Tuple[str, ...]:
    """The stages whose gate runs after their file is written, so a pass of that gate vouches for the file as it
    stands."""
    return tuple(s.name for s in all_stages() if s.post_gated)


# Several stories are a loop over one story run, and the loop needs to know what comes next without
# anyone remembering it. So the state is read off the same files a single run leaves — stage files,
# refusal reports, the round counter, the verdict, the decision records — and never stored.
def stage_order(kind: str = "story") -> typing.Tuple[str, ...]:
    """The run order of a story of this kind, as the workflow orders it — a journey builds nothing, an adopted story is
    not built, a task has nothing new to test."""
    return tuple(name.value for name in workflow().order(StoryKind(kind)))


def order_for(kind: str) -> typing.Tuple[str, ...]:
    """The run order of a story of this kind — an unknown kind runs a story's."""
    return stage_order(kind if kind in ALL_KINDS else "story")


#: The checks about a hand-over's form — the domain's (`verdict.FORM_CHECKS`).
FORM_CHECKS = DOMAIN_FORM_CHECKS
