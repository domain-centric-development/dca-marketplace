"""The issue texts as files: `.dca-factory/issues/<name>.md`, beside the runs — the factory's own folder, never
committed, never sent by the factory. The lesson they come from is read through delivery's api."""

from __future__ import annotations

import hashlib
import os
import typing

from .....delivery.api import learning as delivery
from .....sharedkernel.adapter.outgoing.profile.profile_files import runs_top, shown
from ....application.shared.lesson_issues import AnsweredLesson, LessonIssues
from ....domain.model.lesson import LessonKind, LessonPlace, SignalKey
from ....domain.model.maintainer_issue import MaintainerIssue
from ....domain.model.words import Count, Detail, RecordId

ISSUES = "issues"


class LessonIssueFiles(LessonIssues):
    """The lessons of the project <cwd>, and its issue folder."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def answered(self, record: RecordId) -> typing.Optional[AnsweredLesson]:
        for lesson in delivery.lessons(self._cwd):
            if lesson["id"] != record.value:
                continue
            if lesson["answer"] is None:
                return None
            try:
                kind = LessonKind(lesson["lesson"])
                stories = Count(int(lesson["stories"] or 0))
            except ValueError:
                return None
            return AnsweredLesson(kind, SignalKey(lesson["key"]), stories, LessonPlace.named(Detail(lesson["answer"])))
        return None

    def pipeline(self) -> Detail:
        return Detail(delivery.pipeline())

    def write(self, record: RecordId, issue: MaintainerIssue, text: Detail) -> str:
        name = f"{issue.target.place.value}-{issue.kind.value}-" \
            + hashlib.sha256(record.value.encode("utf-8")).hexdigest()[:10]
        folder = os.path.join(self._cwd, runs_top(), ISSUES)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name + ".md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.value)
        return shown(path)
