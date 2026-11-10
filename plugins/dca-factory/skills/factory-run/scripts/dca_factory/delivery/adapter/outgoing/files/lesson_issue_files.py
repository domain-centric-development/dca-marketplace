"""The issue texts as files: `.dca-factory/issues/<name>.md`, beside the runs — the factory's own folder, never
committed, never sent by the factory."""

from __future__ import annotations

import hashlib
import os
import typing

from .decision_record_files import decision_state, is_lesson, project_decision_files, record_of
from .....contract import CONTRACT, VERSION
from .....sharedkernel.adapter.outgoing.profile.profile_files import runs_top, shown
from ....application.shared.lesson_issues import AnsweredLesson, LessonIssues
from ....domain.model.decision_record import RecordId
from ....domain.model.lesson import LessonKind, LessonPlace, SignalKey
from ....domain.model.maintainer_issue import MaintainerIssue
from ....domain.model.story_words import Count, Detail

ISSUES = "issues"


class LessonIssueFiles(LessonIssues):
    """The lessons of the project <cwd>, and its issue folder."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def answered(self, record: RecordId) -> typing.Optional[AnsweredLesson]:
        for name, front, body, state, error, _path in project_decision_files(self._cwd):
            if error or not is_lesson(front) or str(front.get("id", name)).strip() != record.value:
                continue
            read = record_of(name, front, body, state, decision_state(body)[1])
            said = read.answer_sentence()
            if said is None:
                return None
            try:
                kind = LessonKind(str(front.get("lesson", "")).strip().lower())
                stories = Count(int(str(front.get("stories", "0")).strip() or 0))
            except ValueError:
                return None
            return AnsweredLesson(kind, SignalKey(str(front.get("key", ""))), stories, LessonPlace.named(said))
        return None

    def pipeline(self) -> Detail:
        return Detail(f"dca-factory {VERSION}, contract {CONTRACT}")

    def write(self, record: RecordId, issue: MaintainerIssue, text: Detail) -> str:
        name = f"{issue.target.place.value}-{issue.kind.value}-" \
            + hashlib.sha256(record.value.encode("utf-8")).hexdigest()[:10]
        folder = os.path.join(self._cwd, runs_top(), ISSUES)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name + ".md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.value)
        return shown(path)
