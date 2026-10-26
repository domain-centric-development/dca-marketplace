"""Integrate a story: the main line merged into it — the integrate stage where git stops on a conflict —, squashed,
the gate once more on that tree, the main checkout fast-forwarded."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.service.story_route import Refusal, StoryRoute
from ..shared.run_lines import RunLines
from ..shared.story_integration import Lost, StoryIntegration


@dataclasses.dataclass(frozen=True)
class IntegrateStoryCommand:
    story: str
    dry: bool = False


class IntegrateStoryInputPort(UseCase[IntegrateStoryCommand, typing.Optional[int]], typing.Protocol):
    """Integrate a story: its exit, or None where the gate refused it on the main line and the build stage runs
    again."""


class IntegrateStoryUseCase:
    """Delivered is the integration — under the lock, journaled as the runner's own step. Again where the main line
    moved on meanwhile (three times at most); back to the integrate stage, not a round, where a resolution dropped the
    main line's side of a test (twice at most); a round from the build stage where the gate refused the story."""

    def __init__(self, integration: StoryIntegration, lines: RunLines) -> None:
        self._integration = integration
        self._lines = lines

    def execute(self, command: IntegrateStoryCommand) -> typing.Optional[int]:
        story = command.story
        self._lines.out("── integrate")
        if command.dry:
            self._lines.out(f"   would merge {story}'s branch with the main line and fast-forward the main checkout")
            return 0
        code = self._integration.step(story, lambda: self._attempts(story))
        if code is not None:
            return code
        # the integration took the links down; the build stage works with them again — and document.md is an
        # earlier pass's: the document stage writes it for the story as it now is, or its gate passes it as it is
        self._integration.relink(story)
        return None

    def resolve(self, story: str, said: str, lost: Lost = ()) -> typing.Optional[int]:
        """A merge of the main line into the story that stopped on conflicts (`conflict: <path>` lines in <said>):
        the integrate stage resolves them, then the merge is committed and squashed. A resolution that dropped what
        the main line added to a test goes back to the same stage, naming the lines, at most twice — never to a person,
        and never to the story's own stages, whose gates would call it the story's change. `lost` starts with such a
        repair. None when it holds, else the run's exit."""
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
        return 1

    def _attempts(self, story: str) -> typing.Optional[int]:
        """The integration, again where the main line moved meanwhile: an exit, or None where the gate refused the
        story on the main line."""
        attempt, repairs = 0, 0
        while attempt < 3:
            attempt += 1
            self._integration.lock()
            try:
                code, said = self._integration.prepare(story)
                self._lines.out(said)
                if code == 3:
                    stopped = self.resolve(story, said)
                    if stopped is not None:
                        return stopped
                elif code != 0:
                    self._lines.err(f"factory: {story} could not be merged with the main line — the worktree "
                                    f"{self._integration.worktree()} keeps it as it was.")
                    return 1
                self._lines.out("── gate integrate")
                code = self._integration.gate(story)
            finally:
                self._integration.unlock()
            if code == 0:
                self._lines.out(f"factory: story {story} is delivered on its branch and published — a person merges it."
                                if self._integration.published() else f"factory: story {story} is integrated and delivered.")
                return 0
            report = self._integration.report(story)
            refusals = StoryRoute.integration(report)
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
                        stopped = self.resolve(story, "", lost)
                    finally:
                        self._integration.unlock()
                    if stopped is not None:
                        return stopped
                    continue
            if Refusal.CHECKOUT in refusals:
                self._lines.err(f"factory: the main checkout could not take {story} — see "
                                f"{self._integration.report_place(story)}; then: factory.sh run --story {story} --from "
                                "integrate")
                return 1
            reason = StoryRoute.environment(report)
            if reason is not None:
                self._lines.err(f"factory: gate 'integrate' refused on the environment, not on the story — "
                                f"{reason.value}")
                self._lines.err(f"factory:   no round is counted. Fix it, then: factory.sh run --story {story}")
                return 1
            rounds = self._integration.bump(story)
            if StoryRoute.converged(rounds):
                self._lines.err(f"factory: gate 'integrate' refused in round {rounds.value} — three rounds did not "
                                "converge. needs-human.")
                return 1
            self._lines.err(f"factory: gate 'integrate' refused the story on the main line — round {rounds.value} runs "
                            "the build stage again with the gate's report.")
            return None
        self._lines.err(f"factory: the main line moved on three times while {story} was integrated — run it again.")
        return 1
