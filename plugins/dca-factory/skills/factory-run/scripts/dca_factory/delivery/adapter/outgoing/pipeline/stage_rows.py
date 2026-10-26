"""The pipeline's stages as the adapters read them: one flat row per stage — the domain's `PIPELINE` in words and
flags —, the run orders by kind, the shared windows, the hand-over each stage writes."""

from __future__ import annotations

import typing

from ....domain.model.stage import (
    PIPELINE, Pipeline, Stage as PipelineStage, StoryKind, TESTED_KINDS as DOMAIN_TESTED_KINDS, Trait)
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
    """A stage of the domain's pipeline as the gate, the runner and the cli read it: words and flags."""
    return Stage(row.name.value, row.hand_over.value if row.hand_over else "",
                 row.window.value if row.window else "", tuple(k.value for k in StoryKind if k in row.kinds),
                 Trait.GATED in row.traits, Trait.POST_GATED in row.traits, tuple(c.value for c in row.commands),
                 Trait.TESTED in row.traits, Trait.RED in row.traits, tuple(h.value for h in row.sizes),
                 Trait.LISTS in row.traits, Trait.GUARDED in row.traits, Trait.SUITE in row.traits,
                 Trait.IN_ORDER in row.traits)


#: The pipeline, one row per stage — the domain's (`delivery/domain/model/stage.py`), in the adapters' words.
STAGES = tuple(flat_row(row) for row in PIPELINE)


STAGE = {stage.name: stage for stage in STAGES}


#: The hand-over each stage of the run order writes.
STAGE_FILES = {s.name: s.file for s in STAGES if s.in_order}


#: One process may carry several stages and mark its window under one name: the shared builder (plan to
#: tidy) and the shared verifier (judge, then document). The journal, the changed-files record and the
#: usage are that window's; every stage still writes its own file.
SHARED_WINDOWS = {w: tuple(s.name for s in STAGES if s.window == w)
                  for w in dict.fromkeys(s.window for s in STAGES if s.window)}


#: Extra profile commands run per stage, in this order.
STAGE_CHECKS = {s.name: s.commands for s in STAGES if s.gated}


#: The stages whose gate runs after their file is written, so a pass of that gate vouches for the file as it stands.
POST_GATED = tuple(s.name for s in STAGES if s.post_gated)


def stage_order(kind: str = "story") -> typing.Tuple[str, ...]:
    """The run order of a story of this kind, as the domain's pipeline orders it."""
    return tuple(name.value for name in Pipeline.order(StoryKind(kind)))


# Several stories are a loop over one story run, and the loop needs to know what comes next without
# anyone remembering it. So the state is read off the same files a single run leaves — stage files,
# refusal reports, the round counter, the verdict, the decision records — and never stored.
STAGE_ORDER = stage_order("story")


JOURNEY_ORDER = stage_order("journey")                       # nothing to build: the steps are delivered


ADOPT_ORDER = stage_order("adopt")                           # nothing built: the adopt gate delivers it


TASK_ORDER = stage_order("task")                             # nothing new to test: the existing suite holds


def order_for(kind: str) -> typing.Tuple[str, ...]:
    """The run order of a story of this kind, from the stage table."""
    return {"journey": JOURNEY_ORDER, "adopt": ADOPT_ORDER, "task": TASK_ORDER}.get(kind, STAGE_ORDER)


#: The checks about a hand-over's form — the domain's (`verdict.FORM_CHECKS`).
FORM_CHECKS = DOMAIN_FORM_CHECKS
