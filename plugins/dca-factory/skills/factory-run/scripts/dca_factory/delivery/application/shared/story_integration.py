"""What a story's integration asks of the factory around it: the lock, the merge, the integrate stage, the gate."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.story_state import GateReport, Rounds

#: What a resolution lost of the main line's tests: (test file, [line, …]).
Lost = typing.Sequence[typing.Tuple[str, typing.Sequence[str]]]


class StoryIntegration(OutputPort, typing.Protocol):
    """One story's integration into the main line, from its worktree."""

    def lock(self) -> None:
        """One integration at a time: the git work in the main checkout runs under a lock."""
        ...

    def unlock(self) -> None:
        ...

    def step(self, story: str, work: typing.Callable[[], typing.Optional[int]]) -> typing.Optional[int]:
        """<work> journaled as the runner's own integrate step."""
        ...

    def prepare(self, story: str) -> typing.Tuple[int, str]:
        """The main line merged into the story's branch: 0, 3 stopped on conflicts (`conflict: <path>` lines), else
        it could not be merged — with the lines it said."""
        ...

    def session(self, story: str, conflicts: str, lost: Lost) -> typing.Optional[int]:
        """One stage-integrate session over the conflicts, or the repair of what a resolution lost, then the merge
        committed and squashed: None when it is, else the run's exit."""
        ...

    def lost(self, story: str) -> Lost:
        """What the resolution dropped of the main line's tests."""
        ...

    def lost_text(self, lost: Lost) -> str:
        ...

    def gate(self, story: str) -> int:
        """The integrate gate on the merged tree."""
        ...

    def report(self, story: str) -> GateReport:
        ...

    def report_place(self, story: str) -> str:
        ...

    def published(self) -> bool:
        """The project publishes a delivered story as its branch, merged by a person."""
        ...

    def worktree(self) -> str:
        """The story's worktree, as a person finds it."""
        ...

    def relink(self, story: str) -> None:
        """The links the integration took down put back, and the document marked an earlier pass's."""
        ...

    def bump(self, story: str) -> Rounds:
        ...
