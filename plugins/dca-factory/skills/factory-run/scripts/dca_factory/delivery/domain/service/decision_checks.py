"""Every question a story raised is recorded, and every answer it got has been applied."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService, Value
from ..gateway.stage_evidence import StageEvidence
from ..model.decision_record import DecisionState, RecordKind
from ..model.stage import Pipeline, StageName, StoryKind
from ..model.stage_story import DecisionFacts, Place, StageStory
from ..model.story_state import Detail
from ..model.verdict import CheckName, Finding, Said

DECISIONS = CheckName("decisions")
INTEGRATE = StageName("integrate")


class Applying(Value):
    """An answer its stage applied: the record is stamped applied, and the answer becomes an `answered:` line of the
    story — effects the gate's run carries out before the finding is said."""

    record: DecisionFacts
    stage: StageName


class DecisionsChecked(Value):
    """What the check found, in order: findings, and the answers to apply where they stand."""

    items: typing.Tuple[typing.Union[Finding, Applying], ...]


def answered(record: DecisionFacts) -> Detail:
    """The answer and who gave it, as a finding quotes them."""
    return Detail(f"{record.answer.value!r} by {record.by.value}")


class DecisionChecks(DomainService):
    """Runs on every stage: an open question blocks the story wherever it stands, and a stage file that escalates
    without a record has asked nobody. `gating` is the stage this gate is for: the plan gate runs *before* its
    stage, so there an answered plan question is the stage's input, not yet something it failed to apply."""

    @staticmethod
    def check(story: StageStory, gating: StageName, evidence: StageEvidence) -> DecisionsChecked:
        facts = evidence.decisions(story)
        if facts.unreadable is not None:
            return DecisionsChecked((DECISIONS.fail(Said(facts.unreadable.value)),))
        known = {record.record for record in facts.records}
        items: typing.List[typing.Union[Finding, Applying]] = []
        # 1. a stage that stopped must have written a record for its question
        for hand_over in facts.hand_overs:
            if hand_over.asks is None:
                continue
            if not hand_over.asks:
                items.append(DECISIONS.fail(Said(
                    f"{hand_over.place.value}: `## needs-human` names no `decision: <id>` — the question has to be a "
                    f"record under {facts.store.value}/ so an answer has a place to land; without one, nobody was "
                    f"asked.")))
            for wanted in hand_over.asks:
                if wanted not in known:
                    items.append(DECISIONS.fail(Said(
                        f"{hand_over.place.value}: `## needs-human` names decision {wanted.value!r}, but "
                        f"{evidence.record_place(story, wanted).value} does not exist or names another story.")))
        failed_asking = bool(items)
        # 2. every record: open blocks, a draft is still open, answered must be applied by its stage. An acceptance
        # record is the document gate's own question; that gate reads it.
        texts = {hand_over.stage: hand_over for hand_over in facts.hand_overs}
        order = Pipeline.order(StoryKind.STORY)
        for record in facts.records:
            if record.kind is RecordKind.ACCEPTANCE:
                continue
            rid, stage, where = record.record.value, record.stage, record.place.value
            named = stage.value if stage else ""
            if record.state is DecisionState.OPEN:
                items.append(DECISIONS.fail(Said(
                    f"{rid} is open — {record.question.value!r} (asked by stage {named or '?'}). Answer it in {where} "
                    f"under `## Answer` with `answer:`, `by:` and `at:`; the story waits until then.")))
            elif record.state is DecisionState.DRAFT:
                missing = ", ".join(f"`{f.value}:`" for f in record.missing)
                items.append(DECISIONS.fail(Said(
                    f"{rid} has an `## Answer` that is not confirmed — {missing} missing in {where}. A draft unblocks "
                    f"nothing; the person deciding signs it with a name and a time.")))
            elif record.state is DecisionState.ANSWERED and stage == INTEGRATE:
                # The integrate step has no stage file of its own to cite an answer in, and its agent runs only on a
                # conflict: the step applies the answer when it runs — its gate stamps it; every gate before it waits.
                if gating == INTEGRATE:
                    items.append(Applying(record, INTEGRATE))
                else:
                    items.append(DECISIONS.note(Said(f"{rid} is answered ({answered(record).value}) — the integrate step "
                                                     f"applies it; its gate stamps it.")))
            elif record.state is DecisionState.ANSWERED:
                written_by = texts.get(stage) if stage else None
                text = written_by.text.value if written_by else None
                still_asking = written_by is not None and record.record in (written_by.asks or ())
                unapplied = text is None or still_asking or rid not in text
                # Before the plan stage runs, an answer it has to apply is its input — also one a judge's story
                # conflict routed here, which the plan written before the conflict cannot cite yet.
                if gating.value == "plan" and named == "plan" and unapplied:
                    items.append(DECISIONS.note(Said(
                        f"{rid} is answered ({answered(record).value}) — the plan stage runs next and applies it; the gate "
                        f"after it checks that it did.")))
                # A stage before the one that applies the answer ran first — the test stage recording a red proof a
                # merge left stale: the answer waits for its own stage, whose gate checks that it was applied.
                elif gating in order and stage in order and order.index(gating) < order.index(stage) and unapplied:
                    items.append(DECISIONS.note(Said(
                        f"{rid} is answered ({answered(record).value}) — stage {named} comes after {gating.value} and "
                        f"applies it; its gate checks that it did.")))
                elif text is None or still_asking:
                    items.append(DECISIONS.fail(Said(
                        f"{rid} is answered ({answered(record).value}), but stage {named or '?'} has not run with it yet — "
                        f"re-run that stage (`--from {named}`); it applies the answer and cites `decision: {rid}`.")))
                elif rid not in text:
                    where_cited = written_by.place.value if written_by else "?"
                    items.append(DECISIONS.fail(Said(
                        f"{rid} is answered and stage {named} ran again, but {where_cited} does not cite {rid} — say "
                        f"where the answer landed, so the record can be stamped applied.")))
                elif stage is not None:
                    items.append(Applying(record, stage))
            else:
                items.append(DECISIONS.ok(Said(f"{rid} applied ({answered(record).value})")))
        if not facts.records and not failed_asking:
            items.append(DECISIONS.note(Said("no decision record for this story")))
        return DecisionsChecked(tuple(items))

    @staticmethod
    def applied(applying: Applying, written: typing.Optional[Place]) -> Finding:
        """The finding once the record is stamped — `written` the story where the answer became an `answered:` line."""
        record = applying.record
        by = "the integrate step" if applying.stage == INTEGRATE else f"stage {applying.stage.value}"
        return DECISIONS.ok(Said(
            f"{record.record.value} applied by {by} ({answered(record).value}) — stamped in {record.place.value}"
            + (f", the answer an `answered:` line in {written.value}" if written else "")))
