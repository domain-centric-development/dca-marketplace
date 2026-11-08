"""Resolve the conflicts a merge of the main line into a story stopped on: the integrate stage resolves them, then the
merge is committed and squashed."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.run_lines import RunLines
from ..shared.run_outcome import RunOutcome
from ..shared.story_integration import Lost, StoryIntegration


@dataclasses.dataclass(frozen=True)
class ResolveConflictsCommand:
    """The story, what the merge said (its `conflict: <path>` lines), and the test lines a resolution dropped, where a
    repair starts with them."""

    story: str
    said: str
    lost: Lost = ()


class ResolveConflictsInputPort(UseCase[ResolveConflictsCommand, typing.Optional[RunOutcome]], typing.Protocol):
    """Resolve a merge's conflicts: None when the resolution holds, else how the run ends."""


class ConflictResolution:
    """A merge of the main line into the story that stopped on conflicts (`conflict: <path>` lines in <said>):
        the integrate stage resolves them, then the merge is committed and squashed. A resolution that dropped what
        the main line added to a test goes back to the same stage, naming the lines, at most twice — never to a person,
        and never to the story's own stages, whose gates would call it the story's change. `lost` starts with such a
        repair. None when it holds, else how the run ends."""

    def __init__(self, integration: StoryIntegration, lines: RunLines) -> None:
        self._integration = integration
        self._lines = lines

    def resolve(self, story: str, said: str, lost: Lost = ()) -> typing.Optional[RunOutcome]:
        conflicts = "".join(line[len("conflict: "):] + " " for line in said.split("\n") if line.startswith("conflict: "))
        for attempt in (1, 2, 3):
            stopped = self._integration.session(story, conflicts, lost)
            if stopped is not None:
                return stopped
            lost = self._integration.lost(story)
            if not lost:
                return None
            if attempt < 3:
                self._lines.out(f"factory: the resolution of {story} changed a test the main line holds — "
                                f"{self._integration.lost_text(lost)}; back to the integrate stage (attempt "
                                f"{attempt + 1}).")
        self._lines.err(f"factory: three resolutions of {story} kept dropping the main line's side of a test — "
                        f"{self._integration.lost_text(lost)}. needs-human: the worktree "
                        f"{self._integration.worktree()} holds the merge.")
        return RunOutcome.FAILED


class ResolveConflictsUseCase(ResolveConflictsInputPort):
    """Resolve the conflicts of one story's merge (`ConflictResolution`)."""

    def __init__(self, integration: StoryIntegration, lines: RunLines) -> None:
        self._resolution = ConflictResolution(integration, lines)

    def execute(self, command: ResolveConflictsCommand) -> typing.Optional[RunOutcome]:
        return self._resolution.resolve(command.story, command.said, command.lost)
