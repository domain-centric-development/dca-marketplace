"""What a story must be for a stage to run on it: in a context, released, its happy path marked, not stuck in rounds,
and the person's own parts as the person left them."""

from __future__ import annotations

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage import StoryKind
from ..model.stage_story import ContractNumber, OPEN_ROW, StageStory
from ..model.story_state import MAX_ROUNDS
from ..model.verdict import CheckName, Findings, Said

STORY = CheckName("story")
APPROVED = CheckName("approved")
JOURNEY = CheckName("journey")
TASK = CheckName("task")
HAPPY_PATH = CheckName("happy-path")
ROUNDS = CheckName("rounds")
OWNED = CheckName("owned")

#: The contract that marks one happy path per story.
HAPPY_PATH_CONTRACT = ContractNumber(9)


class StoryChecks(DomainService):
    """The story's own checks, over the story as the gate reads it."""

    @staticmethod
    def context(story: StageStory) -> Findings:
        if not story.context.value:
            return (STORY.fail(Said(f"{story.place.value}: front matter has no `context:` — a story names the bounded "
                                    f"context it changes")),)
        return (STORY.ok(Said(f"{story.story.value} in context {story.context.value} with {len(story.criteria)} "
                              f"criterion(s)")),)

    @staticmethod
    def status(story: StageStory) -> Findings:
        """A story a human has not released is not a story the pipeline builds. A story without the field at all is
        not blocked — the project may not use the field."""
        status = story.status.value
        if not status:
            return (APPROVED.skip(Said(f"{story.place.value}: no `status:` field — nothing to release")),)
        if status == "approved":
            return (APPROVED.ok(Said("story is approved")),)
        if status == "adopted":
            return (APPROVED.ok(Said("story is adopted — it describes behaviour the project already has; adopted, "
                                     "never built")),)
        if status == "delivered":
            return (APPROVED.ok(Said(f"story is delivered ({story.delivered_on.value or 'no date'}) — checked, "
                                     f"nothing runs")),)
        return (APPROVED.fail(Said(
            f"{story.place.value}: status is {status!r} — a human releases the story (`status: approved`) before code "
            f"is written. The most expensive mistake is well-built wrong code.")),)

    @staticmethod
    def happy_path(story: StageStory, contract: ContractNumber, evidence: StageEvidence) -> Findings:
        """Exactly one happy path per story, marked in the backlog — never picked by a plan. A journey has none: it is
        a guard, not acceptance, and it names the stories it depends on. A task has no criterion at all."""
        if story.kind is StoryKind.JOURNEY:
            if not story.depends_on:
                return (JOURNEY.fail(Said(
                    f"{story.place.value}: a `kind: journey` item names the stories whose steps it walks under "
                    f"`depends_on:` — it becomes ready when they are delivered")),)
            return (JOURNEY.ok(Said(f"journey over {', '.join(s.value for s in story.depends_on)}")),)
        if story.kind is StoryKind.TASK:
            return StoryChecks.task(story, evidence)
        if story.kind is StoryKind.ADOPT:
            return (HAPPY_PATH.skip(Said("an adopted story tests nothing new — the levels are the existing tests'")),)
        if contract.value < HAPPY_PATH_CONTRACT.value:
            return (HAPPY_PATH.skip(Said(f"the profile declares contract {contract.value} — the happy-path mark is "
                                         f"contract {HAPPY_PATH_CONTRACT.value}'s")),)
        marked = [key.value for key in story.happy_paths]
        if len(marked) == 1:
            return (HAPPY_PATH.ok(Said(f"happy path: {marked[0]}")),)
        return (HAPPY_PATH.fail(Said(
            f"{story.place.value}: {len(marked)} scenarios marked `(happy path)` — exactly one per story shows its value "
            f"and gets the end-to-end test; mark it in the backlog (`#### <key> (happy path)`)"
            + (f": {', '.join(marked)}" if marked else ""))),)

    @staticmethod
    def task(story: StageStory, evidence: StageEvidence) -> Findings:
        """A task changes nothing an actor sees — so it has no criterion (a criterion is behaviour, and behaviour is a
        story's, with a red test), and the finding rows it closes are there and open."""
        if story.criteria:
            return (TASK.fail(Said(
                f"{story.place.value}: a `kind: task` has acceptance criteria "
                f"({', '.join(key.value for key in story.criteria)}) — a criterion is behaviour; behaviour that "
                f"changes is a story with a red test")),)
        wrong = []
        for row in story.closes:
            state = evidence.finding_row(row)
            if state is None:
                wrong.append(f"{row.value} (no such finding row)")
            elif state != OPEN_ROW:
                wrong.append(f"{row.value} ({state.value} already)")
        if wrong:
            return (TASK.fail(Said(
                f"`closes:` names rows a task cannot close: {'; '.join(wrong)} — `<story>#<n>`, an open row of that "
                f"story's findings.md, or `<name>#<n>` of a project finding file")),)
        closes = [row.value for row in story.closes]
        return (TASK.ok(Said("a task: no criterion, the existing suite is its evidence"
                             + (f"; closes {', '.join(closes)}" if closes else ""))),)

    @staticmethod
    def rounds(story: StageStory, evidence: StageEvidence) -> Findings:
        """The repeat counter lives in a file, so an in-session run cannot lose count and a resumed run sees the same
        number."""
        record = evidence.rounds(story.story)
        if record is None:
            return ()
        if record.rounds is None:
            return (ROUNDS.fail(Said(f"{record.place.value}: not a number")),)
        rounds = record.rounds.value
        if rounds >= MAX_ROUNDS:
            return (ROUNDS.fail(Said(
                f"{record.place.value}: {rounds} rounds without convergence — stop and escalate. A loop that finds "
                f"the same thing three times finds it the fourth time too.")),)
        return (ROUNDS.ok(Said(f"round {rounds + 1} of at most {MAX_ROUNDS}")),)

    @staticmethod
    def owned(story: StageStory, evidence: StageEvidence) -> Findings:
        """Inside a window, and after one that changed what is the person's, the gate refuses."""
        owned = evidence.owned(story)
        if owned.marked:
            return (OWNED.fail(Said(
                f"{', '.join(p.value for p in owned.marked)} changed under a stage — a person looks at it and "
                f"confirms (`factory-cli.py --owned-confirm {story.story.value}`) before the story runs on")),)
        if owned.changed:
            return (OWNED.fail(Said(
                f"{', '.join(p.value for p in owned.changed)} changed while this stage runs — the story and the "
                f"answers are the person's; a stage writes its question into a record, never an answer, and never "
                f"the story")),)
        if owned.changed is not None:
            return (OWNED.ok(Said("the story and the answers are as the stage found them")),)
        return ()
