"""What a story's run asks of the factory around it: its files, its gates, and the processes that carry its stages."""

from __future__ import annotations

import typing

from ...domain.model.stage import StageName, StoryKind
from ...domain.model.story_state import GateReport, Rounds, VerdictWord


class StoryStages(typing.Protocol):
    """One story's stages as the runner carries them, in the checkout or the worktree the story runs in."""

    def open_decisions(self, story: str) -> typing.List[str]:
        """The records of the story nobody answered yet, as a person reads their places."""
        ...

    def kind(self, story: str) -> StoryKind:
        ...

    def red_stale(self, story: str, start: StageName) -> bool:
        """The story's tests changed after the test stage saw them fail: said and journaled — the red proof is about
        an earlier version."""
        ...

    def pause(self, story: str) -> None:
        """Between two stages: a `stop` request, then the requests about other stories."""
        ...

    def gate(self, stage: str, story: str) -> int:
        """The gate's exit: 0 passed, 3 waits for a person's acceptance, else refused."""
        ...

    def quiet_gate(self, stage: str, story: str) -> int:
        """The gate asked only whether a file already holds — its lines unread."""
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

    def stopped_for_human(self, story: str, stage: str) -> int:
        """The records the needs-human section names, said with how to resume: 3 when it names one, else 1."""
        ...

    def stage(self, story: str, stage: str) -> int:
        """The stage in a process of its own: 0 when it ran and wrote its file, else the run's exit."""
        ...

    def dry(self, story: str, stage: str) -> None:
        """What the stage's process would be started with, said."""
        ...

    def builder(self, story: str, stages: typing.Sequence[str], start: str, dry: bool) -> int:
        """The shared builder carrying <stages> in one process: 0 when it ran, else the run's exit."""
        ...

    def reviews(self, story: str, dry: bool) -> int:
        """One process per review perspective, at once: 0, or the run's exit when they may not be dispatched."""
        ...

    def verifier(self, story: str, stages: typing.Sequence[str], dry: bool) -> int:
        """The shared verifier carrying <stages> in one process: 0 when it ran, else the run's exit."""
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

    def verdict(self, story: str) -> VerdictWord:
        ...

    def back(self, story: str) -> typing.Optional[StageName]:
        """The stage the judge sends the story back to; None where it names none."""
        ...

    def in_worktree(self) -> bool:
        """The story runs in its worktree, integrated once delivered."""
        ...

    def integrate(self, story: str, dry: bool) -> typing.Optional[int]:
        """The story integrated into the main line: its exit, or None where the gate refused it there and the build
        stage runs again."""
        ...
