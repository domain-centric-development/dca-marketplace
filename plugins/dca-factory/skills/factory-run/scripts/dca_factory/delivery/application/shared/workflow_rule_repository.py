"""The rules of the workflow, wherever they are kept — Markdown files beside the pipeline today."""

from __future__ import annotations

import typing

from ....building_blocks import Repository
from ...domain.model.jump import RuleId
from ...domain.model.workflow_rule import WorkflowRule


class WorkflowRuleRepository(Repository[WorkflowRule, RuleId], typing.Protocol):
    """Every rule of the gate and the runner, retired ones included."""

    def all(self) -> typing.Sequence[WorkflowRule]:
        """Every rule, in the order of their ids."""
        ...
