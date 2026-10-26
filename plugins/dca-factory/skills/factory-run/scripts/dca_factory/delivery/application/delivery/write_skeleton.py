"""Write the skeleton a stage starts its hand-over from — the plan's criteria, the files a stage changed, the
document's paths: what the pipeline knows, so the stage never types it."""

from __future__ import annotations

import dataclasses
import enum
import typing

from ....building_blocks import UseCase
from ..shared.hand_over_skeletons import HandOverSkeletons


class Skeleton(enum.Enum):
    PLAN = "plan"           # plan.md, before the plan stage
    FILES = "files"         # the file list of the test, build or tidy hand-over
    DOCUMENT = "document"   # document.md, before the document stage


@dataclasses.dataclass(frozen=True)
class WriteSkeletonCommand:
    skeleton: Skeleton
    story: str
    stage: str = ""          # the stage whose file list (FILES)


class WriteSkeletonInputPort(UseCase[WriteSkeletonCommand, int], typing.Protocol):
    """Its exit."""


class WriteSkeletonUseCase:
    def __init__(self, skeletons: HandOverSkeletons) -> None:
        self._skeletons = skeletons

    def execute(self, command: WriteSkeletonCommand) -> int:
        if command.skeleton is Skeleton.PLAN:
            return self._skeletons.plan(command.story)
        if command.skeleton is Skeleton.FILES:
            return self._skeletons.files(command.story, command.stage)
        return self._skeletons.document(command.story)
