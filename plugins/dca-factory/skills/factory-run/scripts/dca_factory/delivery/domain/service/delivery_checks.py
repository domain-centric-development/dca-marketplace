"""What the document gate delivers a story on: every stage of this pass ran in order and the judge passed it, the
outcome event exists, what the document stage wrote can be checked and resolves, every proposed term is accounted
for, the review reports are reports — and no stage changed the installed pipeline."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService, Value
from ..gateway.stage_evidence import StageEvidence
from ..model.stage import Pipeline, StageName, StoryKind
from ..model.stage_story import ContractNumber, PlannedDigest, Presence, StageStory
from ..model.verdict import CheckName, Findings, Said

STORY_PASS = CheckName("story-pass")
OUTCOME = CheckName("outcome")
DOCUMENTED = CheckName("documented")
GLOSSARY = CheckName("glossary")
REVIEWS = CheckName("reviews")
PIPELINE = CheckName("pipeline")

#: The contract that holds a delivered story to its outcome event.
OUTCOME_CONTRACT = ContractNumber(14)
JUDGE = StageName("judge")


class StoryPassChecked(Value):
    """The findings, and whether the judge passed the story — a signal the gate's run records."""

    findings: Findings
    judge_passed: Presence


class DeliveryChecks(DomainService):
    """The document gate's checks."""

    @staticmethod
    def story_pass(story: StageStory, evidence: StageEvidence) -> StoryPassChecked:
        """Every stage of this pass wrote its file after the one before it, the judge passed it, and the story is the
        one that was planned. A document written for an earlier pass, or over a judge who asked for changes,
        delivers nothing."""
        facts = evidence.story_pass(story)
        if facts.gaps:
            gaps = ", ".join(f"{g.hand_over.value} ("
                             f"{'written for an earlier pass' if g.earlier is Presence.PRESENT else 'missing'})"
                             for g in facts.gaps)
            return StoryPassChecked((STORY_PASS.fail(Said(
                f"{gaps} — the document gate delivers a story whose stages all ran, in order, in this pass; the story "
                f"runs on from the first of them")),), Presence.ABSENT)
        verdict = facts.verdict.value
        if verdict != "pass":
            judge = Pipeline.hand_over(JUDGE)
            return StoryPassChecked((STORY_PASS.fail(Said(
                f"{judge.value if judge else 'judge.md'} says `verdict: {verdict or 'none'}` — only a judge's `pass` "
                f"lets a story be delivered")),), Presence.ABSENT)
        if facts.planned is PlannedDigest.MISSING:
            found = STORY_PASS.skip(Said("no .story-digest from the plan gate — whether the story changed since it "
                                         "was planned is not checked"))
        elif facts.planned is PlannedDigest.CHANGED:
            found = STORY_PASS.fail(Said(
                f"{story.place.value} changed after it was planned — a criterion no stage planned, tested or built "
                f"cannot be delivered; the story runs again from plan"))
        else:
            found = STORY_PASS.ok(Said("every stage of this pass ran in order, the judge passed it, and the story is "
                                       "the one that was planned"))
        return StoryPassChecked((found,), Presence.PRESENT)

    @staticmethod
    def outcome_raised(story: StageStory, contract: ContractNumber, evidence: StageEvidence) -> Findings:
        """Delivered means the outcome event exists: every event of `publishes:` is a type the production code
        declares, and a production file the story changed — the aggregate that raises it or the use case that
        publishes it — refers to it beyond the declaration."""
        if story.kind is not StoryKind.STORY or contract.value < OUTCOME_CONTRACT.value or not story.publishes:
            return ()
        facts = evidence.outcome(story)
        scope = "the story changed" if facts.changed is not None else \
            "the project has (no record of what the story changed)"
        problems, found = [], []
        for outcome in facts.events:
            event = outcome.event.value
            if not outcome.declared:
                problems.append(f"no type `{event}` in the production code — the story says it publishes it")
                continue
            declared = outcome.declared[0].value
            raisers = [p.value for p in outcome.raising if facts.changed is None or p in facts.changed]
            if not raisers and outcome.raising:
                problems.append(f"`{event}` is declared in {declared} and raised in {outcome.raising[0].value}, but by "
                                f"nothing the story changed — `publishes:` belongs on the story that introduces the "
                                f"event; this story drops the line")
                continue
            if not raisers:
                problems.append(f"`{event}` is declared in {declared}, but nothing {scope} refers to it — the "
                                f"aggregate raises it or the use case publishes it")
                continue
            found.append(f"{event} (declared in {declared}, raised in {raisers[0]})")
        if problems:
            return (OUTCOME.fail(Said("; ".join(problems))),)
        return (OUTCOME.ok(Said("the outcome event exists: " + "; ".join(found))),)

    @staticmethod
    def documented(story: StageStory, evidence: StageEvidence) -> Findings:
        """The document stage may only write statements that can be checked: a file it says it updated exists, and
        every row names how it was checked. A documented path that does not resolve outlives the story."""
        facts = evidence.document(story.story)
        where = facts.place.value
        if facts.unreadable is not None:
            return (DOCUMENTED.fail(Said(facts.unreadable.value)),)
        if facts.asks is Presence.PRESENT:
            return (DOCUMENTED.fail(Said(f"{where}: the stage stopped with a needs-human section — read it and "
                                         f"decide")),)
        found = []
        if facts.missing:
            found.append(DOCUMENTED.fail(Said(
                f"{where}: names things that do not exist: {', '.join(sorted({m.value for m in facts.missing}))} — a "
                f"documented path that does not resolve sends the next reader nowhere. Write every path as it "
                f"resolves from the project root, not as a package- or namespace-relative shorthand.")))
        if facts.unsourced:
            found.append(DOCUMENTED.fail(Said(f"{where}: unsourced claims: "
                                              f"{', '.join(u.value for u in facts.unsourced)} — every row says how "
                                              f"it was checked")))
        if not found:
            found.append(DOCUMENTED.ok(Said(f"{facts.files.value} document(s) updated, every claim resolves")))
        return tuple(found)

    @staticmethod
    def proposals_landed(story: StageStory, evidence: StageEvidence) -> Findings:
        """Every term the plan proposed is either in a glossary now or named as still open under `## Not
        documented`. A proposal that quietly disappears is how a model's private vocabulary enters a code base."""
        facts = evidence.proposals(story.story)
        if facts is None:
            return ()
        if facts.glossary is Presence.ABSENT:
            return (GLOSSARY.skip(Said(f"{facts.proposed.value} term(s) proposed in the plan, but the project keeps "
                                       f"no glossary")),)
        if facts.missing:
            return (GLOSSARY.fail(Said(
                f"proposed but neither in a glossary nor named as open under `## Not documented`: "
                f"{', '.join(m.value for m in facts.missing)} — a term the code uses and no glossary defines is "
                f"private vocabulary (a term is found by the word before the parenthesis or the word inside it, case "
                f"aside)")),)
        return (GLOSSARY.ok(Said(f"{facts.proposed.value} proposed term(s) accounted for")),)

    @staticmethod
    def reviews(story: StageStory, evidence: StageEvidence) -> Findings:
        """One review file per perspective in the review skills' report format. A missing file is a note — the
        judge then ran that pass itself and says so —, a file that is no report is refused: the judge would converge
        from nothing while the report claims a perspective."""
        facts = evidence.reviews(story.story)
        if facts.malformed:
            return (REVIEWS.fail(Said(
                f"reviews/{', reviews/'.join(m.value for m in facts.malformed)}.md carries no must-fix, should-fix or "
                f"nit section and says of no finding that there is none — not a review report")),)
        found = []
        if facts.missing:
            found.append(REVIEWS.note(Said(
                f"no review file for {', '.join(m.value for m in facts.missing)} (reviews/<perspective>.md) — the judge "
                f"ran that pass itself, and `## Perspectives covered` says so")))
        if facts.read:
            found.append(REVIEWS.ok(Said(f"{len(facts.read)} review file(s) for the judge to converge from: "
                                         f"{', '.join(r.value for r in facts.read)}")))
        return tuple(found)

    @staticmethod
    def pipeline_untouched(story: StageStory, evidence: StageEvidence) -> Findings:
        """No stage of the story changed the installed pipeline: a change made by any stage is refused at the next
        gate, whichever stage made it. Silent without a record."""
        facts = evidence.pipeline(story.story)
        if facts.touched is None:
            return ()
        folder = facts.folder.value
        if facts.touched:
            touched = [p.value for p in facts.touched]
            return (PIPELINE.fail(Said(
                f"a stage changed the installed pipeline: {', '.join(touched[:6])}{' …' if len(touched) > 6 else ''} "
                f"— a stage reads {folder} and never writes it; put it back (`factory.sh update`, or git) and the "
                f"stage runs again")),)
        return (PIPELINE.ok(Said(f"no stage of {story.story.value} changed {folder}")),)
