"""Integrate a story: the main line merged into it — the integrate stage where git stops on a conflict —, squashed,
the gate once more on that tree, the main checkout fast-forwarded."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.story_state import Refusal
from ..shared.run_lines import RunLines
from ..shared.run_outcome import GateOutcome, MergeOutcome, RunOutcome
from ..shared.story_integration import StoryIntegration
from .pipeline_rules import decides
from .resolve_conflicts import ConflictResolution


@dataclasses.dataclass(frozen=True)
class IntegrateStoryCommand:
    story: str
    dry: bool = False


class IntegrateStoryInputPort(UseCase[IntegrateStoryCommand, typing.Optional[RunOutcome]], typing.Protocol):
    """Integrate a story: how it ends, or None where the gate refused it on the main line and the build stage runs
    again."""


class IntegrateStoryUseCase(IntegrateStoryInputPort):
    """Delivered is the integration — under the lock, journaled as the runner's own step. Again where the main line
    moved on meanwhile (three times at most); back to the integrate stage, not a round, where a resolution dropped the
    main line's side of a test (twice at most); a round from the build stage where the gate refused the story."""

    def __init__(self, integration: StoryIntegration, lines: RunLines) -> None:
        self._integration = integration
        self._lines = lines
        self._resolution = ConflictResolution(integration, lines)

    @decides(
        "RUN-INTEGRATE-1",
    )
    def execute(self, command: IntegrateStoryCommand) -> typing.Optional[RunOutcome]:
        story = command.story
        self._lines.out("── integrate")
        if command.dry:
            self._lines.out(f"   would merge {story}'s branch with the main line and fast-forward the main checkout")
            return RunOutcome.RAN_THROUGH
        ended = self._integration.step(story, lambda: self._attempts(story))
        if ended is not None:
            return ended
        # the integration took the links down; the build stage works with them again — and document.md is an
        # earlier pass's: the document stage writes it for the story as it now is, or its gate passes it as it is
        self._integration.relink(story)
        return None


    def _attempts(self, story: str) -> typing.Optional[RunOutcome]:
        """The integration, again where the main line moved meanwhile: how it ends, or None where the gate refused the
        story on the main line."""
        attempt, repairs = 0, 0
        while attempt < 3:
            attempt += 1
            self._integration.lock()
            try:
                merged, said = self._integration.prepare(story)
                self._lines.out(said)
                if merged is MergeOutcome.CONFLICTS:
                    stopped = self._resolution.resolve(story, said)
                    if stopped is not None:
                        return stopped
                elif merged is not MergeOutcome.MERGED:
                    self._lines.err(f"factory: {story} could not be merged with the main line — the worktree "
                                    f"{self._integration.worktree()} keeps it as it was.")
                    return RunOutcome.FAILED
                self._lines.out("── gate integrate")
                gated = self._integration.gate(story)
            finally:
                self._integration.unlock()
            if gated is GateOutcome.PASSED:
                self._lines.out(f"factory: story {story} is delivered on its branch and published — a person merges it."
                                if self._integration.published() else f"factory: story {story} is integrated and delivered.")
                return RunOutcome.RAN_THROUGH
            report = self._integration.report(story)
            refusals = report.integration()
            if Refusal.MOVED in refusals:
                self._lines.out(f"factory: the main line moved on while {story} was merged — merged again (attempt "
                                f"{attempt + 1}).")
                continue
            # the resolution dropped what the main line added to a test — the integrate stage's to put back
            if Refusal.MAIN_TESTS in refusals and repairs < 2:
                lost = self._integration.lost(story)
                if lost:
                    repairs += 1
                    attempt -= 1
                    self._lines.out(f"factory: the integrate gate named a test of the main line the resolution changed "
                                    f"— back to the integrate stage, not a round ({self._integration.lost_text(lost)}).")
                    self._integration.lock()
                    try:
                        stopped = self._resolution.resolve(story, "", lost)
                    finally:
                        self._integration.unlock()
                    if stopped is not None:
                        return stopped
                    continue
            if Refusal.CHECKOUT in refusals:
                self._lines.err(f"factory: the main checkout could not take {story} — see "
                                f"{self._integration.report_place(story)}; then: factory.sh run --story {story} --from "
                                "integrate")
                return RunOutcome.FAILED
            reason = report.environment()
            if reason is not None:
                self._lines.err(f"factory: gate 'integrate' refused on the environment, not on the story — "
                                f"{reason.value}")
                self._lines.err(f"factory:   no round is counted. Fix it, then: factory.sh run --story {story}")
                return RunOutcome.FAILED
            rounds = self._integration.bump(story)
            if rounds.converged():
                self._lines.err(f"factory: gate 'integrate' refused in round {rounds.value} — three rounds did not "
                                "converge. needs-human.")
                return RunOutcome.FAILED
            self._lines.err(f"factory: gate 'integrate' refused the story on the main line — round {rounds.value} runs "
                            "the build stage again with the gate's report.")
            return None
        self._lines.err(f"factory: the main line moved on three times while {story} was integrated — run it again.")
        return RunOutcome.FAILED
