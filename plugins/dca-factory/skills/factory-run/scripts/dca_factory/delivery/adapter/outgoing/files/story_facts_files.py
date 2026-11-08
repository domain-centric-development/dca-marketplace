"""One story's facts as its files keep them: its front matter, the marks in its evidence folder, its journal, the
stage files and refusals of its run folder, its decision records."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from ..pipeline.stage_rows import order_for, stage_files, stage_order
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, factory_home
from ....domain.model.decision_record import RecordId
from ....domain.model.stage import StageName
from ....domain.model.story_state import (
    Acceptance, AcceptanceVerdict, Claimant, Detail, GateReport, HandOverFacts, HandOverText, Mark, Rounds, RunFacts, StoryMarks)
from ..claims.remote_claims import cached_claims, PUBLISHED
from ....domain.model.decision_record import DecisionRecord
from ....domain.model.story import Story
from .story_files import story_of
from ..git.worktrees import has_worktree
from .decision_record_files import acceptance_state, needs_human_ids, record_of, records_of
from .journal_files import journal_events
from .run_marks import (
    backlog_digest, current_stage_files, gate_passed_since, OWNED_CHANGED, pass_marks, STORY_DIGEST, judged_of, verdict_in)
from .story_layout import story_digest
from ....application.shared.story_facts import StoryFacts

Front = typing.Mapping[str, typing.Any]


class StoryFactsFiles(StoryFacts):
    """The facts of the story <story_id> with the front matter <front>, under the checkout <cwd> and the run folder
    <runs>."""

    def __init__(self, cwd: str, runs: str, story_id: str, front: Front, story_path: typing.Optional[str],
                 story: typing.Optional[Story] = None) -> None:
        self.cwd, self.runs, self.story_id, self.matter, self.story_path = cwd, runs, story_id, front, story_path
        self._story = story
        self.evidence, self.folder = evidence_dir(runs, story_id), os.path.join(runs, story_id)

    def story(self) -> Story:
        if self._story is not None:
            return self._story
        if self.story_path:
            return story_of(self.story_path, self.matter, read_front_matter(self.story_path)[1])
        return story_of(os.path.join(self.story_id, "story.md"), dict(self.matter, id=self.story_id), "", ())

    def story_marks(self) -> StoryMarks:
        marks = {mark for mark, name in ((Mark.OWNED_CHANGED, OWNED_CHANGED), (Mark.PUBLISHED, PUBLISHED))
                 if os.path.isfile(os.path.join(self.evidence, name))}
        foreign = cached_claims(self.runs).get(self.story_id)
        claimant = Claimant(f"{foreign['who']} ({foreign['host']}) since {foreign['since']}") \
            if foreign and not foreign["own"] else None
        return StoryMarks(frozenset(marks), claimant)

    def run(self, story: Story) -> RunFacts:
        texts = current_stage_files(self.runs, self.story_id, order_for(story.kind.value))
        hand_overs = {StageName(stage): self.hand_over(text) for stage, text in texts.items()}
        marks = self.marks(texts, pass_marks(self.runs, self.story_id))
        acceptance = self.acceptance() if self.story_path and "document" in texts else None
        return RunFacts(hand_overs, self.unreadable(), frozenset(marks), self.rounds(),
                        tuple(StageName(s) for s in stage_order() if self.present(f".gate-{s}.txt")),
                        frozenset(StageName(s) for s in stage_order() if self.present(stage_files()[s])),
                        self.report(".gate-integrate.txt"), self.report(".gate-document.txt"), acceptance)

    @staticmethod
    def hand_over(text: str) -> HandOverFacts:
        asks = needs_human_ids(text)
        return HandOverFacts(HandOverText(text), judged_of(verdict_in(text)),
                             tuple(RecordId(i) for i in asks) if asks is not None else None)

    def records(self, story: Story) -> typing.Sequence[DecisionRecord]:
        try:
            found = records_of(self.story_id, self.story_path)
        except GateError:
            return ()
        return [record_of(os.path.basename(path)[:-3], front, body, state, answer)
                for path, front, body, state, answer in found]

    def unreadable(self) -> typing.Optional[Detail]:
        try:
            records_of(self.story_id, self.story_path)
        except GateError as error:
            return Detail(str(error))
        return None

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
                and not passes.get(f"wrote:{stage_files()['build']}", 0) > passes.get("fail:integrate", 0):
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
