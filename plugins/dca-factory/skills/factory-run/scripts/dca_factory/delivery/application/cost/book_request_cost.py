"""Book a request's usage on the stories it worked on."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.usage import Shares, Usage
from ..shared.story_journal import StoryJournal, Window


@dataclasses.dataclass(frozen=True)
class BookRequestCostCommand:
    """A request's usage — one process, measured and priced by the runner; None where it is unknown."""

    request: str
    tool: str
    usage: typing.Optional[Usage]


@dataclasses.dataclass(frozen=True)
class CostBooked:
    """The windows the request opened; `booked` where its usage went onto them."""

    windows: typing.Tuple[Window, ...]
    booked: bool


class BookRequestCostInputPort(UseCase[BookRequestCostCommand, CostBooked], typing.Protocol):
    """Book a request's usage on the stories it worked on."""


class BookRequestCostUseCase:
    """One `usage` line on each window the request's process opened, an even share each. A request that opened no
    window — a description, a discovery — keeps its usage in the request journal alone."""

    def __init__(self, journal: StoryJournal) -> None:
        self._journal = journal

    def execute(self, command: BookRequestCostCommand) -> CostBooked:
        windows = tuple(self._journal.windows_opened_by(command.request))
        if not windows or command.usage is None:
            return CostBooked(windows, False)
        share = command.usage.share(Shares(len(windows)))
        for window in windows:
            self._journal.book(window, share, command.tool, command.request)
        return CostBooked(windows, True)
