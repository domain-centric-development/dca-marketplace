"""Where a story stands — decided over the facts its story file and its run left, never over a clock."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService
from ..model.decision_record import ANSWERED_STATES, DecisionState, RecordId, RecordKind, WAITING
from ..model.stage import HandOver, Pipeline, StageName, StoryKind
from .story_route import StoryRoute
from ..model.story_state import (
    AcceptanceVerdict, Detail, Mark, MAX_ROUNDS, RunFacts, StateName, Standing, StoryFront, VerdictWord)

PLAN, BUILD, TEST, JUDGE, DOCUMENT = (StageName(n) for n in ("plan", "build", "test", "judge", "document"))
ADOPT, INTEGRATE = StageName("adopt"), StageName("integrate")
ORDER = Pipeline.order(StoryKind.STORY)
NO_VERDICT = VerdictWord("")


def file_of(stage: StageName) -> HandOver:
    return Pipeline.hand_over(stage) or HandOver("")


class StoryStanding(DomainService):
    """A story's state and the stage it runs from: first from what the story says about itself, then — for a
    released story — from its run."""

    @staticmethod
    def before_run(front: StoryFront) -> typing.Optional[Standing]:
        """Where a story stands that does not run — None for one released to run."""
        story, status = front.story.value, front.status.value
        # Before anything the story says about itself: a stage may have written it (WP-94).
        if Mark.OWNED_CHANGED in front.marks:
            return Standing(StateName.STOPPED, None, Detail(
                f"the story or an answer changed under a stage — a person looks at "
                f"it, then `factory-cli.py --owned-confirm {story}`"))
        if status == "superseded":
            return Standing(StateName.SUPERSEDED, None, Detail("replaced by another story"))
        # Delivered is delivered: the gate wrote it into the story, and nothing under the run folder — a refusal
        # left from an earlier round, a deleted folder — changes that.
        if front.delivered_by is not None:
            by = front.delivered_by.value
            return Standing(StateName.DELIVERED, None, Detail(f"claimed by {by}" if by.startswith("hand") else ""))
        # Several factories (WP-93): a story this factory published waits for its merge; one another factory
        # claimed is theirs — read off the last fetch, written only where the profile opts in.
        if Mark.PUBLISHED in front.marks:
            return Standing(StateName.PUBLISHED, None, Detail(
                "published as its branch — waits for its merge on the remote main "
                "line; `factory.sh integrate " + story + "` publishes it again "
                "after another landed"))
        if front.claimant:
            return Standing(StateName.CLAIMED, None, Detail(f"claimed by {front.claimant.value}"))
        if status and status not in ("approved", "adopted"):
            return Standing(StateName.UNRELEASED, None, Detail(f"status {status} — a human releases it first"))
        return None

    @staticmethod
    def in_run(front: StoryFront, run: RunFacts) -> Standing:
        """Where a released story stands in its run."""
        texts = run.hand_overs
        if run.unreadable:
            return Standing(StateName.STOPPED, None, run.unreadable)
        waiting = [r.id.value for r in run.records if r.state in WAITING]
        if waiting:
            return Standing(StateName.WAITING, None, Detail("decision " + ", ".join(waiting)))
        answered: typing.Dict[typing.Optional[StageName], RecordId] = {}
        resolved: typing.Dict[RecordId, typing.Optional[StageName]] = {}
        for record in run.records:
            if record.kind == RecordKind.ACCEPTANCE:
                resolved[record.id] = record.resumes
                continue                             # answered through the document gate, not a stage
            facts = texts.get(record.resumes) if record.resumes else None
            if record.state in ANSWERED_STATES:
                resolved[record.id] = record.resumes
            # The record's `stage:` applies the answer — usually the stage that asked, for a judge's
            # story conflict the stage the answer lands in. Until that stage's file cites the id, it is next.
            if record.state == DecisionState.ANSWERED and (
                    facts is None or record.id in (facts.asks or ()) or record.id.value not in facts.text.value):
                answered.setdefault(record.resumes, record.id)
        # A story changed since its plan runs from plan, before any answer's stage: that stage would build on a plan
        # of the story as it was (#158). The gate's own `answered:` line takes the planned digest anew, so it does not.
        if texts and Mark.CHANGED_SINCE_PLAN in run.marks:
            return Standing(StateName.IN_PROGRESS, PLAN, Detail(
                "the story changed after it was planned — every stage runs again"))
        if answered:
            stage = min(answered, key=lambda s: ORDER.index(s) if s in ORDER else 0)
            return Standing(StateName.RESUMABLE, stage, Detail(
                f"decision {answered[stage].value} answered — its stage applies it"))
        if run.rounds.value >= MAX_ROUNDS:
            return Standing(StateName.STOPPED, None, Detail(f"{MAX_ROUNDS} rounds did not converge"))
        if Mark.PLAN_REFUSED in run.marks:
            # Repaired since: the story or its epic is not what the plan gate refused, so the plan gate asks again.
            if Mark.REPAIRED not in run.marks:
                return Standing(StateName.STOPPED, None, Detail(
                    "the plan gate refused the story — the backlog needs a fix"))
            return Standing(StateName.IN_PROGRESS, PLAN, Detail(
                "the story changed after the plan gate refused it — planned again"))
        judge = texts.get(JUDGE)
        verdict = judge.verdict if judge else NO_VERDICT
        conflict = (judge.asks if judge else None) or ()
        if verdict.value == "story-conflict" and conflict and all(i in resolved for i in conflict):
            applied_at = max((resolved[i] for i in conflict), key=lambda s: ORDER.index(s) if s in ORDER else 0)
            after = ORDER[min(ORDER.index(applied_at) + 1, len(ORDER) - 1)] if applied_at in ORDER else BUILD
            return Standing(StateName.IN_PROGRESS, after, Detail(f"the story conflict was answered and applied at "
                                                       f"{applied_at.value if applied_at else None} — the stages "
                                                       f"after it run again"))
        for stage, facts in texts.items():
            if facts.asks and all(i in resolved for i in facts.asks):
                continue
            if facts.asks is not None:
                return Standing(StateName.STOPPED, None, Detail(
                    f"{file_of(stage).value} ends in `## needs-human` without an open "
                    f"record"))
        if verdict.value == "story-conflict":
            return Standing(StateName.STOPPED, None, Detail("the judge found a story conflict"))
        if Mark.INTEGRATE_REFUSED in run.marks:
            report = run.integrate_report.value if run.integrate_report else ""
            if "gate:fail checkout" in report:
                return Standing(StateName.STOPPED, None, Detail(
                    "the main checkout could not take the story's commit — see "
                    ".gate-integrate.txt; then `factory.sh run --story "
                    + front.story.value + " --from integrate`"))
            if "gate:fail moved" in report:
                return Standing(StateName.IN_PROGRESS, INTEGRATE, Detail(
                    "the main line moved on — the story is merged with "
                    "it again"))
            return Standing(StateName.IN_PROGRESS, BUILD, Detail(
                "the integrate gate refused the story on the main line — the "
                "build stage runs again"))
        if run.refused:
            first = run.refused[0]
            # A refusal over an earlier pass's file — the document gate's `story-pass` — runs on from that stage:
            # running the refused stage again changes nothing it could fix.
            before = ORDER[:ORDER.index(first)] if first in ORDER else ()
            stale = [stage for stage in before if stage not in texts and stage in run.on_disk]
            if stale:
                return Standing(StateName.IN_PROGRESS, stale[0], Detail(
                    f"the {first.value} gate refused over an earlier "
                    f"pass's {file_of(stale[0]).value} — the story runs on from "
                    f"{stale[0].value}"))
            # The outcome event is code: the document stage cannot write it, the build can.
            if first == DOCUMENT and run.document_report and "gate:fail outcome" in run.document_report.value:
                return Standing(StateName.IN_PROGRESS, BUILD, Detail(
                    "the document gate found no outcome event in the code — "
                    "the build adds it"))
            return Standing(StateName.IN_PROGRESS, first, Detail(
                f"the {first.value} gate refused — the stage runs again"))
        adopt, integrating = front.kind == StoryKind.ADOPT, Mark.WORKTREE in run.marks
        if adopt and verdict.value == "pass":
            if integrating and Mark.ADOPT_PASSED in run.marks:
                return Standing(StateName.IN_PROGRESS, INTEGRATE, Detail(
                    "the adopt gate passed — its worktree is integrated "
                    "next"))
            return Standing(StateName.IN_PROGRESS, ADOPT, Detail(
                "the judge confirmed the tests — the adopt gate delivers it"))
        if DOCUMENT in texts:
            if integrating and Mark.DOCUMENT_PASSED in run.marks:
                return Standing(StateName.IN_PROGRESS, INTEGRATE, Detail(
                    "every gate passed — its worktree is integrated next"))
            if run.acceptance and run.acceptance.verdict == AcceptanceVerdict.ACCEPTED:
                accepted = run.acceptance.record.value if run.acceptance.record else None
                return Standing(StateName.RESUMABLE, DOCUMENT, Detail(
                    f"{accepted} accepted — the document gate delivers it"))
            return Standing(StateName.IN_PROGRESS, DOCUMENT, Detail(
                "document.md is written, its gate has not passed yet"))
        if not texts:
            return Standing(StateName.READY, PLAN, Detail(""))
        if verdict.value == "changes-requested":
            return Standing(StateName.IN_PROGRESS, StoryRoute.judged_back(front.kind, texts[JUDGE].text),
                            Detail("the judge requested changes"))
        missing = next(stage for stage in Pipeline.order(front.kind) if stage not in texts)
        return Standing(StateName.IN_PROGRESS, missing, Detail(f"{file_of(missing).value} not written yet"))


