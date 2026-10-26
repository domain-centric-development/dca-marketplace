"""One story's facts as its files keep them: its front matter, the marks in its evidence folder, its journal, the
stage files and refusals of its run folder, its decision records."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from ..pipeline.stage_rows import order_for, STAGE_FILES, STAGE_ORDER
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, factory_home
from ....application.shared.front import is_acceptance
from ....domain.model.decision_record import DecisionState, RecordId, RecordKind
from ....domain.model.stage import StageName, StoryKind
from ....domain.model.story import StoryId
from ....domain.model.story_state import (
    Acceptance, AcceptanceVerdict, Claimant, Detail, GateReport, HandOverFacts, HandOverText, Mark, RecordFacts,
    Rounds, RunFacts, StatusWord, StoryFront, VerdictWord)
from ..claims.remote_claims import cached_claims, PUBLISHED
from ..git.worktrees import has_worktree
from .decision_record_files import acceptance_state, needs_human_ids, records_of, resume_stage
from .journal_files import journal_events
from .run_marks import (
    backlog_digest, current_stage_files, gate_passed_since, OWNED_CHANGED, pass_marks, STORY_DIGEST, verdict_in)
from .story_layout import delivered_by, is_delivered, story_digest, story_kind

Front = typing.Mapping[str, typing.Any]


class StoryFactsFiles:
    """The facts of the story <story_id> with the front matter <front>, under the checkout <cwd> and the run folder
    <runs>."""

    def __init__(self, cwd: str, runs: str, story_id: str, front: Front, story_path: typing.Optional[str]) -> None:
        self.cwd, self.runs, self.story_id, self.matter, self.story_path = cwd, runs, story_id, front, story_path
        self.evidence, self.folder = evidence_dir(runs, story_id), os.path.join(runs, story_id)

    def front(self) -> StoryFront:
        marks = {mark for mark, name in ((Mark.OWNED_CHANGED, OWNED_CHANGED), (Mark.PUBLISHED, PUBLISHED))
                 if os.path.isfile(os.path.join(self.evidence, name))}
        foreign = cached_claims(self.runs).get(self.story_id)
        claimant = Claimant(f"{foreign['who']} ({foreign['host']}) since {foreign['since']}") \
            if foreign and not foreign["own"] else None
        return StoryFront(StoryId(self.story_id), StatusWord(str(self.matter.get("status", "")).strip().lower()),
                          StoryKind(story_kind(self.matter)),
                          Detail(delivered_by(self.matter)) if is_delivered(self.matter) else None,
                          frozenset(marks), claimant)

    def run(self, front: StoryFront) -> RunFacts:
        texts = current_stage_files(self.runs, self.story_id, order_for(front.kind.value))
        hand_overs = {StageName(stage): self.hand_over(text) for stage, text in texts.items()}
        records, unreadable = self.records()
        marks = self.marks(texts, pass_marks(self.runs, self.story_id))
        acceptance = self.acceptance() if self.story_path and "document" in texts else None
        return RunFacts(hand_overs, records, unreadable, frozenset(marks), self.rounds(),
                        tuple(StageName(s) for s in STAGE_ORDER if self.present(f".gate-{s}.txt")),
                        frozenset(StageName(s) for s in STAGE_ORDER if self.present(STAGE_FILES[s])),
                        self.report(".gate-integrate.txt"), self.report(".gate-document.txt"), acceptance)

    @staticmethod
    def hand_over(text: str) -> HandOverFacts:
        asks = needs_human_ids(text)
        return HandOverFacts(HandOverText(text), VerdictWord(verdict_in(text)),
                             tuple(RecordId(i) for i in asks) if asks is not None else None)

    def records(self) -> typing.Tuple[typing.Tuple[RecordFacts, ...], typing.Optional[Detail]]:
        try:
            found = records_of(self.story_id, self.story_path)
        except GateError as error:
            return (), Detail(str(error))
        facts = []
        for _path, front, _body, state, answer in found:
            resumes = resume_stage(front, answer)
            facts.append(RecordFacts(RecordId(str(front["id"]).strip()), DecisionState(state),
                                     StageName(resumes) if resumes else None,
                                     RecordKind.ACCEPTANCE if is_acceptance(front) else RecordKind.QUESTION))
        return tuple(facts), None

    def marks(self, texts: typing.Mapping[str, str], passes: typing.Mapping[str, int]) -> typing.Set[Mark]:
        marks = set()
        planned = os.path.join(self.evidence, STORY_DIGEST)
        if self.story_path and os.path.isfile(planned) and self.present("plan.md") \
                and read_text(planned).strip() != story_digest(self.story_path):
            marks.add(Mark.CHANGED_SINCE_PLAN)
        if self.present(".gate-plan.txt"):
            marks.add(Mark.PLAN_REFUSED)
            refused = next((e["fields"].get("backlog") for e in reversed(journal_events(self.runs, self.story_id))
                            if e["kind"] == "gate" and e["name"] == "plan" and e["fields"].get("exit") != "0"), None)
            if refused and refused != backlog_digest(self.story_path):
                marks.add(Mark.REPAIRED)
        if self.present(".gate-integrate.txt") \
                and not passes.get(f"wrote:{STAGE_FILES['build']}", 0) > passes.get("fail:integrate", 0):
            marks.add(Mark.INTEGRATE_REFUSED)
        if has_worktree(self.story_id, factory_home() or self.cwd):
            marks.add(Mark.WORKTREE)
            if gate_passed_since(self.runs, self.story_id, "adopt", "judge"):
                marks.add(Mark.ADOPT_PASSED)
            if gate_passed_since(self.runs, self.story_id, "document", "document"):
                marks.add(Mark.DOCUMENT_PASSED)
        return marks

    def rounds(self) -> Rounds:
        path = os.path.join(self.evidence, ".rounds")
        text = (read_text(path).strip() or "0") if os.path.isfile(path) else "0"
        return Rounds(int(text) if text.isdigit() else 0)

    def acceptance(self) -> typing.Optional[Acceptance]:
        try:
            verdict, rid = acceptance_state(self.cwd, self.story_id, self.story_path)
        except (GateError, OSError):
            return None
        return Acceptance(AcceptanceVerdict(verdict), RecordId(rid) if rid else None)

    def present(self, name: str) -> bool:
        return os.path.isfile(os.path.join(self.folder, name))

    def report(self, name: str) -> typing.Optional[GateReport]:
        return GateReport(read_text(os.path.join(self.folder, name))) if self.present(name) else None
