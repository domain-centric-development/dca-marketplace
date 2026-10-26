"""Take a published story's delivery back on its branch, so it is delivered again on the main line as it is now."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.published_branches import PublishedBranches, TakenBack


@dataclasses.dataclass(frozen=True)
class TakeBackDeliveryCommand:
    story: str


class TakeBackDeliveryInputPort(UseCase[TakeBackDeliveryCommand, typing.Optional[TakenBack]], typing.Protocol):
    """Take a published delivery back; None where the story has no published branch."""


class TakeBackDeliveryUseCase:
    """A published branch whose merge request lost the race goes back to before its delivery, so the integrate step
    merges the remote main line and the delivering gate merges again under the new rules. The spec is never resolved
    by text."""

    def __init__(self, branches: PublishedBranches) -> None:
        self._branches = branches

    def execute(self, command: TakeBackDeliveryCommand) -> typing.Optional[TakenBack]:
        if not self._branches.published(command.story):
            return None
        return self._branches.take_back(command.story)
