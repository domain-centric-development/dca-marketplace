"""What the integrate gate holds a story to: its branch carries the main line and nothing half-merged, and the
merge's resolution kept the main line's side of every test it met."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage_story import Presence, StageStory
from ..model.verdict import CheckName, Finding, Findings, Said

INTEGRATE = CheckName("integrate")
CONFLICTS = CheckName("conflicts")
MOVED = CheckName("moved")
MAIN_TESTS = CheckName("main-tests")


class IntegrationChecks(DomainService):
    """The integrate gate's own checks."""

    @staticmethod
    def integrated(story: StageStory, evidence: StageEvidence) -> Findings:
        """No unmerged path, no conflict marker in a file the story's commit changes, and its commit sits on the
        target's tip — a target that moved since is integrated again (`moved`), not refused."""
        facts = evidence.integration(story.story)
        if facts.worktree is Presence.ABSENT:
            return (INTEGRATE.fail(Said(
                f"the integrate gate runs in the story's worktree, with {facts.home_variable.value} naming the main "
                f"checkout — the runner's integrate step starts it")),)
        if facts.recorded is Presence.ABSENT:
            return (INTEGRATE.fail(Said(
                f"no target recorded for {story.story.value} (<evidence>/<story>/target) — the worktree was not made "
                f"by the runner")),)
        if facts.unmerged:
            return (CONFLICTS.fail(Said("unmerged: " + ", ".join(p.value for p in facts.unmerged)
                                        + " — the merge is not finished")),)
        found = [CONFLICTS.fail(Said("a conflict marker is left in " + ", ".join(p.value for p in facts.marked)))
                 if facts.marked else
                 CONFLICTS.ok(Said("no unmerged path, no conflict marker in the story's files"))]
        if facts.moved is Presence.PRESENT:
            found.append(MOVED.fail(Said(f"{facts.target.value} moved on since the story was merged with it — the "
                                         f"integrate step merges again")))
        return tuple(found)

    @staticmethod
    def main_tests(story: StageStory, evidence: StageEvidence) -> Findings:
        """A line the main line added to a test while the story ran — another story's case — that the story's tree
        lacks is the resolution's change, never the story's: refused here by name, and the runner sends it back to
        the integrate stage."""
        facts = evidence.main_tests(story.story)
        if facts is None:
            return ()
        found: typing.List[Finding] = []
        for adapted in facts.adapted:
            lines = [line.value for line in adapted.lines]
            found.append(MAIN_TESTS.note(Said(
                f"{adapted.place.value}: {len(lines)} line(s) of the main line call what the story re-signed — taken "
                f"as adapted, not asked back: {', '.join(repr(line) for line in lines[:2])}"
                + (" …" if len(lines) > 2 else ""))))
        for place, ids in facts.waived:
            found.append(MAIN_TESTS.note(Said(
                f"{place.value} keeps the resolution {', '.join(i.value for i in ids)} answered — the main line's "
                f"lines there are not asked back")))
        if facts.lost.value:
            found.append(MAIN_TESTS.fail(Said(
                f"the merge's resolution changed a test the main line holds: {facts.lost.value} — the integrate stage "
                f"puts the main line's side back (`git show {facts.target.value}:<file>`) beside the story's")))
        else:
            found.append(MAIN_TESTS.ok(Said("every test the main line changed while the story ran keeps the main "
                                            "line's side")))
        return tuple(found)
