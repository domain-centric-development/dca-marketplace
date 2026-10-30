"""Delivery's rules, published: every rule the gate and the runner decide by, and the stage table they are placed in —
in delivery's published terms, plain data a reader translates into its own model.

    rule   {id, part: check | pass | decision, when, why, outcomes: [{state, said, goes: [stage | again | stop]}],
            reports: [...], stages: [...], kinds: [...], source, retired}
    stage  {name, kinds: [...], window, gate: before | after | none, in_order, pass_action}
    order  {kind: [stage, ...]}
    story  {stages: {stage: [{state, check}]}, refused: {check: n}} — what the gate found over one story
"""

from __future__ import annotations

import os
import typing

# The modules that register rules where they decide — imported for that, as the gate's composition root does.
from ..adapter.incoming.gate import gate_command  # noqa: F401
from ..adapter.outgoing.files.gate_reports import story_findings
from ..adapter.outgoing.process import runner_process  # noqa: F401
from ..adapter.outgoing.tools import tool_choice  # noqa: F401
from ..application.backlog import run_backlog  # noqa: F401
from ..application.delivery import (  # noqa: F401
    check_change, check_parity, claim_story, confirm_owned, integrate_story, pass_actions, process_checks, run_story,
    stage_checks)
from ..application.delivery.check_stage import CHECKS, PASS_RULES
from ..application.delivery.pipeline_rules import DECIDED, PipelineRule, RETIRED
from ..application.profile import profile_rules  # noqa: F401
from ..application.requests import request_queue, work_request  # noqa: F401
from ..application.schedule import schedule_backlog, stand_story  # noqa: F401
from ..domain.model.stage import ALL_KINDS, Pipeline, PIPELINE, StoryKind, Trait
from ...sharedkernel.adapter.outgoing.profile.profile_files import place, read_profile, resolve_profile, set_places

Published = typing.Dict[str, typing.Any]
KIND_ORDER = tuple(kind.value for kind in StoryKind)


def published(found: PipelineRule, part: str, stages: typing.Tuple[str, ...],
              kinds: typing.Iterable[StoryKind]) -> Published:
    """One rule as delivery publishes it: a gate rule's own stages and kinds where it narrows its check's."""
    chosen = set(found.kinds) if found.kinds else {kind.value for kind in kinds}
    return dict(id=found.id, part=part, when=found.when, why=found.why,
                outcomes=[dict(state=state, said=said, goes=list(dict(found.goes).get(state, ())))
                          for state, said in found.outcomes],
                reports=list(found.reports), stages=list(found.stages or stages),
                kinds=[kind for kind in KIND_ORDER if kind in chosen], source=found.source, retired="")


def pipeline_rules() -> typing.List[Published]:
    """Every rule of the gate and the runner, each once: the checks in their order, the pass actions per stage, the
    rest as their modules register them, the retired ones last."""
    found: typing.List[Published] = []
    for check in CHECKS:
        found += [published(r, "check", check.stages, check.kinds) for r in check.rules]
    for stage, rules in PASS_RULES.items():
        found += [published(r, "pass", (stage,), ALL_KINDS) for r in rules]
    found += [published(r, "decision", (), ALL_KINDS) for r in DECIDED]
    found += [dict(id=rule_id, part="decision", when="", why=why, outcomes=[], reports=[], stages=[], kinds=[], source="",
                   retired=why) for rule_id, why in RETIRED.items()]
    return found


def stage_rows() -> typing.List[Published]:
    """The stage table, as the rulebook places rules in it."""
    rows = []
    for row in PIPELINE:
        gate = "none" if Trait.GATED not in row.traits else "after" if Trait.POST_GATED in row.traits \
            or Trait.IN_ORDER not in row.traits else "before"
        rows.append(dict(name=row.name.value, kinds=[k for k in KIND_ORDER if StoryKind(k) in row.kinds],
                         window=row.window.value if row.window else "", gate=gate,
                         in_order=Trait.IN_ORDER in row.traits, pass_action=row.name.value in PASS_RULES))
    return rows


def kind_orders() -> typing.Dict[str, typing.List[str]]:
    """Each kind's run order — the stages after it (adopt, integrate) are the table's rows outside the order."""
    return {kind.value: [name.value for name in Pipeline.order(kind)] for kind in StoryKind}


def story_gate_findings(cwd: str, story_id: str) -> Published:
    """What the gate found over the story, read from the project <cwd>: the latest report per stage, the refusals per
    check."""
    set_places(read_profile(resolve_profile(None, cwd)))
    runs = place("runs")
    return story_findings(runs if os.path.isabs(runs) else os.path.join(cwd, runs), story_id)
