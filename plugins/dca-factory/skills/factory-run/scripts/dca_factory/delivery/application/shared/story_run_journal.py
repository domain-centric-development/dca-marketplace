"""The tracker of a story's process: what its journal and its files say about where the story stands — read, never
decided here; the rounds counted."""

from __future__ import annotations

import typing

from ....building_blocks import Store
from ...domain.model.stage import StageName, StoryKind
from ...domain.model.story_state import GateReport, Judged, Rounds


class StoryRunJournal(Store, typing.Protocol):
    """One story's run as its journal and its files keep it, in the checkout or the worktree the story runs in. The
    executive (`RunStoryUseCase`) reads where the story stands here and decides with the workflow."""

    def open_decisions(self, story: str) -> typing.List[str]:
        """The records of the story nobody answered yet, as a person reads their places."""
        ...

    def kind(self, story: str) -> StoryKind:
        ...

    def red_stale(self, story: str, start: StageName) -> bool:
        """The story's tests changed after the test stage saw them fail: said and journaled — the red proof is about
        an earlier version."""
        ...

    def report(self, story: str, stage: str) -> GateReport:
        """The gate's last refusal of the stage."""
        ...

    def artefact(self, story: str, stage: str) -> str:
        """The stage's hand-over, as a person reads its place."""
        ...

    def holds(self, story: str, stage: str) -> bool:
        """The stage's hand-over exists."""
        ...

    def refused_before(self, story: str, stage: str) -> bool:
        """The stage's gate refused the story before."""
        ...

    def delivered(self, story: str) -> bool:
        ...

    def asks_human(self, story: str, stage: str) -> bool:
        """The stage's hand-over ends with a needs-human section."""
        ...

    def sent_back(self, story: str) -> bool:
        """The build stage found a defect in a test's own code (`back: test` in its file)."""
        ...

    def repaired(self, story: str) -> bool:
        """The shared builder repaired what the build stage sent back before it tidied."""
        ...

    def red_proof(self, story: str) -> bool:
        """The story's tests were seen red."""
        ...

    def red_ledger(self, story: str) -> str:
        """The red proof's place, as a person reads it."""
        ...

    def bump(self, story: str) -> Rounds:
        """One more round counted."""
        ...

    def resumes(self, story: str) -> typing.Optional[StageName]:
        """Where the story's state says it runs from now; None where it runs nowhere."""
        ...

    def verdict(self, story: str) -> Judged:
        ...

    def back(self, story: str) -> typing.Optional[StageName]:
        """The stage the judge sends the story back to; None where it names none."""
        ...

    def in_worktree(self) -> bool:
        """The story runs in its worktree, integrated once delivered."""
        ...
