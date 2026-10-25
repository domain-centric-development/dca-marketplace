"""Where a stage, or a process that is none, sits in a report: the story's run order, the rest beside it."""

from __future__ import annotations

from ...domain.model.stage import PIPELINE, Pipeline, StoryKind, Window

ORDER = tuple(name.value for name in Pipeline.order(StoryKind.STORY))
BUILDER = [s.name.value for s in PIPELINE if s.window == Window.BUILDER]
VERIFIER = [s.name.value for s in PIPELINE if s.window == Window.VERIFIER]

#: Where a process that is no stage of the table sits among the stages: beside a stage of a shared window, by an
#: offset — the shared builder after the last stage it carries, the reviews just before the verifier's first stage,
#: which converges them, the shared verifier after that stage.
PROCESS_RANKS = {"builder": (BUILDER[-1], 0.5), "review:": (VERIFIER[0], -0.2), "verifier": (VERIFIER[0], 0.5)}

#: The backlog before every stage, the decisions after them.
OUTSIDE_RANKS = {"backlog": -1, "decisions": 98}


def stage_rank(stage: str) -> float:
    """Stage order for reports: the table's run order, the processes beside the stages they carry."""
    if stage in ORDER:
        return ORDER.index(stage)
    process = "review:" if stage.startswith("review:") else stage
    if process in PROCESS_RANKS:
        anchor, offset = PROCESS_RANKS[process]
        return ORDER.index(anchor) + offset
    return OUTSIDE_RANKS.get(stage, 99)

