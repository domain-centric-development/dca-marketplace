"""Where a stage, or a process that is none, sits in a report: the story's run order, the rest beside it."""

from __future__ import annotations

import typing

from ...domain.model.stage import StoryKind, Window
from ..delivery.pipeline_workflow import workflow


def process_ranks() -> typing.Dict[str, typing.Tuple[str, float]]:
    """Where a process that is no stage of the workflow sits among the stages: beside a stage of a shared window, by
    an offset — the shared builder after the last stage it carries, the reviews just before the verifier's first
    stage, which converges them, the shared verifier after that stage."""
    builder = [s.name.value for s in workflow().in_window(Window.BUILDER)]
    verifier = [s.name.value for s in workflow().in_window(Window.VERIFIER)]
    return {"builder": (builder[-1], 0.5), "review:": (verifier[0], -0.2), "verifier": (verifier[0], 0.5)}

#: The backlog before every stage, the decisions after them.
OUTSIDE_RANKS = {"backlog": -1, "decisions": 98}


def stage_rank(stage: str) -> float:
    """Stage order for reports: the workflow's run order, the processes beside the stages they carry."""
    order = tuple(name.value for name in workflow().order(StoryKind.STORY))
    if stage in order:
        return order.index(stage)
    process = "review:" if stage.startswith("review:") else stage
    ranks = process_ranks()
    if process in ranks:
        anchor, offset = ranks[process]
        return order.index(anchor) + offset
    return OUTSIDE_RANKS.get(stage, 99)

