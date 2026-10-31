"""The workflow a story runs through, wherever it is kept — Markdown files beside the pipeline today."""

from __future__ import annotations

import typing

from ....building_blocks import Repository
from ...domain.model.workflow import Workflow, WorkflowName


class WorkflowRepository(Repository[Workflow, WorkflowName], typing.Protocol):
    """The workflows by their names — today the one every story runs, `delivery`."""
