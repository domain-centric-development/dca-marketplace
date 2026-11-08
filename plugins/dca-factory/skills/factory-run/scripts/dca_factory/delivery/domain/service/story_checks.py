"""What a story must be for a stage to run on it: in a context, released, its happy path marked, not stuck in rounds,
and the person's own parts as the person left them."""

from __future__ import annotations

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage import StoryKind
from ..model.story import ReleaseState, Story
from ..model.stage_story import ContractNumber, OPEN_ROW
from ..model.story_state import MAX_ROUNDS
from ..model.verdict import CheckName, Findings, Said

STORY = CheckName("story")
APPROVED = CheckName("approved")
JOURNEY = CheckName("journey")
TASK = CheckName("task")
HAPPY_PATH = CheckName("happy-path")
ROUNDS = CheckName("rounds")
OWNED = CheckName("owned")
BRIEF = CheckName("brief")

#: The contract that marks one happy path per story.
HAPPY_PATH_CONTRACT = ContractNumber(9)


class StoryChecks(DomainService):
    """The story's own checks, over the story as the gate reads it."""

    @staticmethod
    def context(story: Story, evidence: StageEvidence) -> Findings:
        if not story.content.context.value:
            return (STORY.fail(Said(f"{evidence.place_of(story.id).value}: front matter has no `context:` — a story names the bounded "
                                    f"context it changes")),)
        return (STORY.ok(Said(f"{story.id.value} in context {story.content.context.value} with {len(story.content.criteria)} "
                              f"criterion(s)")),)

    @staticmethod
    def status(story: Story, evidence: StageEvidence) -> Findings:
        """A story a human has not released is not a story the pipeline builds. A story without the field at all is
        not blocked — the project may not use the field."""
        state, where = story.release_state(), evidence.place_of(story.id).value
        if state is ReleaseState.UNMARKED:
            return (APPROVED.skip(Said(f"{where}: no `status:` field — nothing to release")),)
        if state is ReleaseState.RELEASED:
            return (APPROVED.ok(Said("story is approved")),)
        if state is ReleaseState.ADOPTED:
            return (APPROVED.ok(Said("story is adopted — it describes behaviour the project already has; adopted, "
                                     "never built")),)
        if state is ReleaseState.DELIVERED:
            on = story.delivery.on.value if story.delivery else ""
            return (APPROVED.ok(Said(f"story is delivered ({on or 'no date'}) — checked, nothing runs")),)
        written = story.content.written_status.value
        said = f"status is {written!r}" if written else "no `status:` — the profile's `release: required` reads it as a draft"
        return (APPROVED.fail(Said(
            f"{where}: {said} — a human releases the story (`status: approved`) before code is written. The most "
            f"expensive mistake is well-built wrong code.")),)

    @staticmethod
    def happy_path(story: Story, contract: ContractNumber, evidence: StageEvidence) -> Findings:
        """Exactly one happy path per story, marked in the backlog — never picked by a plan. A journey has none: it is
        a guard, not acceptance, and it names the stories it depends on. A task has no criterion at all."""
        if story.kind is StoryKind.JOURNEY:
            walks = story.walks()
            if not walks:
                return (JOURNEY.fail(Said(
                    f"{evidence.place_of(story.id).value}: a `kind: journey` item names the stories whose steps it walks under "
                    f"`depends_on:` — it becomes ready when they are delivered")),)
            return (JOURNEY.ok(Said(f"journey over {', '.join(s.value for s in walks)}")),)
        if story.kind is StoryKind.TASK:
            return StoryChecks.task(story, evidence)
        if story.kind is StoryKind.ADOPT:
            return (HAPPY_PATH.skip(Said("an adopted story tests nothing new — the levels are the existing tests'")),)
        if contract.value < HAPPY_PATH_CONTRACT.value:
            return (HAPPY_PATH.skip(Said(f"the profile declares contract {contract.value} — the happy-path mark is "
                                         f"contract {HAPPY_PATH_CONTRACT.value}'s")),)
        happy = story.happy_path()
        if happy is not None:
            return (HAPPY_PATH.ok(Said(f"happy path: {happy.value}")),)
        marked = [key.value for key in story.content.happy_paths]
        return (HAPPY_PATH.fail(Said(
            f"{evidence.place_of(story.id).value}: {len(marked)} scenarios marked `(happy path)` — exactly one per story shows its value "
            f"and gets the end-to-end test; mark it in the backlog (`#### <key> (happy path)`)"
            + (f": {', '.join(marked)}" if marked else ""))),)

    @staticmethod
    def task(story: Story, evidence: StageEvidence) -> Findings:
        """A task changes nothing an actor sees — so it has no criterion (a criterion is behaviour, and behaviour is a
        story's, with a red test), and the finding rows it closes are there and open."""
        if story.content.criteria:
            return (TASK.fail(Said(
                f"{evidence.place_of(story.id).value}: a `kind: task` has acceptance criteria "
                f"({', '.join(key.value for key in story.content.criteria)}) — a criterion is behaviour; behaviour that "
                f"changes is a story with a red test")),)
        wrong = []
        for row in story.content.closes:
            state = evidence.finding_row(row)
            if state is None:
                wrong.append(f"{row.value} (no such finding row)")
            elif state != OPEN_ROW:
                wrong.append(f"{row.value} ({state.value} already)")
        if wrong:
            return (TASK.fail(Said(
                f"`closes:` names rows a task cannot close: {'; '.join(wrong)} — `<story>#<n>`, an open row of that "
                f"story's findings.md, or `<name>#<n>` of a project finding file")),)
        closes = [row.value for row in story.content.closes]
        return (TASK.ok(Said("a task: no criterion, the existing suite is its evidence"
                             + (f"; closes {', '.join(closes)}" if closes else ""))),)

    @staticmethod
    def rounds(story: Story, evidence: StageEvidence) -> Findings:
        """The repeat counter lives in a file, so an in-session run cannot lose count and a resumed run sees the same
        number."""
        record = evidence.rounds(story.id)
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
    def owned(story: Story, evidence: StageEvidence) -> Findings:
        """Inside a window, and after one that changed what is the person's, the gate refuses."""
        owned = evidence.owned(story)
        if owned.marked:
            return (OWNED.fail(Said(
                f"{', '.join(p.value for p in owned.marked)} changed under a stage — a person looks at it and "
                f"confirms (`factory-cli.py --owned-confirm {story.id.value}`) before the story runs on")),)
        if owned.changed:
            return (OWNED.fail(Said(
                f"{', '.join(p.value for p in owned.changed)} changed while this stage runs — the story and the "
                f"answers are the person's; a stage writes its question into a record, never an answer, and never "
                f"the story")),)
        if owned.changed is not None:
            return (OWNED.ok(Said("the story and the answers are as the stage found them")),)
        return ()
