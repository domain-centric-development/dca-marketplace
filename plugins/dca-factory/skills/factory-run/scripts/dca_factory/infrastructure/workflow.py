"""The workflow this process runs stories through — its stages, then its rules, each from its repository, loaded once
per process before anything asks about a stage or a rule."""

from __future__ import annotations

from ..delivery.adapter.outgoing.workflow.rule_files import RuleFiles
from ..delivery.adapter.outgoing.workflow.stage_files import StageFiles
from ..delivery.application.delivery.pipeline_rules import load as load_rules, RULES
from ..delivery.application.delivery.pipeline_workflow import load as load_stages, loaded


def load_workflow() -> None:
    """The stages from `workflow/stages/`, the rules from `workflow/rules/` — the rules held against the stages and
    against every binding in the code; once per process."""
    if not loaded():
        load_stages(StageFiles())
    if not RULES:
        load_rules(RuleFiles())
