"""Delivery's rules, published: every rule the gate and the runner decide by, and the stage table they are placed in —
in delivery's published terms, plain data a reader translates into its own model.

    rule   {id, part: check | pass | decision, when, why, outcomes: [{state, said, goes: [stage | again | stop]}],
            reports: [...], stages: [...], kinds: [...], source (its file), bound (the code that binds it), retired}
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
from ..adapter.outgoing.workflow.rule_files import RuleFiles
from ..adapter.outgoing.workflow.stage_files import StageFiles
from ..application.delivery.check_stage import CHECKS, PASS_RULES
from ..application.delivery.pipeline_rules import Bound, DECIDED, load, RULES
from ..application.delivery.pipeline_workflow import load as load_stages, loaded, workflow
from ..application.profile import profile_rules  # noqa: F401
from ..application.requests import request_queue, work_request  # noqa: F401
from ..application.schedule import schedule_backlog, stand_story  # noqa: F401
from ..domain.model.stage import StoryKind, Trait
from ..domain.model.workflow_rule import WorkflowRule
from ...sharedkernel.adapter.outgoing.profile.profile_files import place, read_profile, resolve_profile, set_places

Published = typing.Dict[str, typing.Any]
KIND_ORDER = tuple(kind.value for kind in StoryKind)


def published(bound: typing.Optional[Bound], found: WorkflowRule) -> Published:
    """One rule as delivery publishes it: its own stages and kinds where it narrows the code that binds it."""
    stages = [s.value for s in found.stages] or list(bound.stages if bound else ())
    chosen = {k.value for k in found.kinds} or {k.value for k in (bound.kinds if bound else ())}
    return dict(id=found.id.value, part=found.part.value, when=found.when.value, why=found.why.value,
                outcomes=[dict(state=o.state.value, said=o.said.value, goes=[t.value for t in o.goes])
                          for o in found.outcomes],
                reports=[r.value for r in found.reports], stages=stages,
                kinds=[kind for kind in KIND_ORDER if kind in chosen],
                source=found.written.value if found.written else "", bound=bound.place if bound else "",
                retired=found.retired.value if found.retired else "")


def held() -> None:
    """The workflow's stages and rules, loaded where this process has not yet."""
    if not loaded():
        load_stages(StageFiles())
    if not RULES:
        load(RuleFiles())


def pipeline_rules() -> typing.List[Published]:
    """Every rule of the gate and the runner, each once: the checks in their order, the pass actions per stage, the
    decisions as their modules bind them, then what the rules hold that no code binds — retired, or a problem."""
    held()
    order = [b for check in CHECKS for b in check.rules] + [b for bs in PASS_RULES.values() for b in bs] + DECIDED
    found = [published(b, RULES[b.rule]) for b in order if b.rule in RULES]
    seen = {b.rule for b in order}
    found += [published(None, r) for rule_id, r in sorted(RULES.items()) if rule_id not in seen]
    return found


def stage_rows() -> typing.List[Published]:
    """The stage table, as the rulebook places rules in it."""
    held()
    rows = []
    for row in workflow().stages:
        gate = "none" if Trait.GATED not in row.traits else "after" if Trait.POST_GATED in row.traits \
            or Trait.IN_ORDER not in row.traits else "before"
        rows.append(dict(name=row.name.value, kinds=[k for k in KIND_ORDER if StoryKind(k) in row.kinds],
                         window=row.window.value if row.window else "", gate=gate,
                         in_order=Trait.IN_ORDER in row.traits, pass_action=row.name.value in PASS_RULES,
                         about=row.about.value if row.about else "",
                         source=written.value if (written := workflow().written(row.name)) else ""))
    return rows


def kind_orders() -> typing.Dict[str, typing.List[str]]:
    """Each kind's run order — the stages after it (adopt, integrate) are the table's rows outside the order."""
    held()
    return {kind.value: [name.value for name in workflow().order(kind)] for kind in StoryKind}


def story_gate_findings(cwd: str, story_id: str) -> Published:
    """What the gate found over the story, read from the project <cwd>: the latest report per stage, the refusals per
    check."""
    set_places(read_profile(resolve_profile(None, cwd)))
    runs = place("runs")
    return story_findings(runs if os.path.isabs(runs) else os.path.join(cwd, runs), story_id)
