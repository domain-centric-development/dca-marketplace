"""The steps of a story's process: a gate, a stage in a process of its own, a shared window, the reviews, the
integration — commands the executive gives, carried out outside the application."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from .run_outcome import GateOutcome, RunOutcome


class StageSteps(OutputPort, typing.Protocol):
    """The steps the executive of a story's process takes, each through this port."""

    def pause(self, story: str) -> None:
        """Between two stages: a `stop` request, then the requests about other stories."""
        ...

    def gate(self, stage: str, story: str) -> GateOutcome:
        """The stage's gate over the story: passed, waits for a person's acceptance, or refused."""
        ...

    def quiet_gate(self, stage: str, story: str) -> GateOutcome:
        """The gate asked only whether a file already holds — its lines unread."""
        ...

    def stopped_for_human(self, story: str, stage: str) -> RunOutcome:
        """The records the needs-human section names, said with how to resume: waits for a person where it names
        one, else failed."""
        ...

    def stage(self, story: str, stage: str) -> RunOutcome:
        """The stage in a process of its own: ran through when it ran and wrote its file, else how the run ends."""
        ...

    def dry(self, story: str, stage: str) -> None:
        """What the stage's process would be started with, said."""
        ...

    def builder(self, story: str, stages: typing.Sequence[str], start: str, dry: bool) -> RunOutcome:
        """The shared builder carrying <stages> in one process: ran through when it ran, else how the run ends."""
        ...

    def reviews(self, story: str, dry: bool) -> RunOutcome:
        """One process per review perspective, at once: ran through, or how the run ends when they may not be
        dispatched."""
        ...

    def verifier(self, story: str, stages: typing.Sequence[str], dry: bool) -> RunOutcome:
        """The shared verifier carrying <stages> in one process: ran through when it ran, else how the run ends."""
        ...

    def integrate(self, story: str, dry: bool) -> typing.Optional[RunOutcome]:
        """The story integrated into the main line — the integration's own use case behind this port —: how it ends,
        or None where the gate refused it there and the build stage runs again."""
        ...
