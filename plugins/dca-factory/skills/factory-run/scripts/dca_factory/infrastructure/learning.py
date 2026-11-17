"""Learning's use cases, wired to delivery's open host service and to learning's own issue folder."""

from __future__ import annotations

import typing

from ..learning.adapter.outgoing.delivery.delivery_lessons import DeliveryLessons
from ..learning.adapter.outgoing.delivery.delivery_signals import DeliverySignals
from ..learning.adapter.outgoing.files.issue_files import LessonIssueFiles
from ..learning.application.shared.lesson_records import LessonProposals
from ..learning.application.show_lessons import ShowLessonsUseCase
from ..learning.application.write_issue import WriteIssueUseCase
from ..learning.application.write_lessons import WriteLessonsUseCase
from ..learning.domain.model.words import Moment


def show_lessons(cwd: str, epics: typing.Optional[str] = None) -> ShowLessonsUseCase:
    return ShowLessonsUseCase(DeliverySignals(cwd, epics))


def write_lessons(cwd: str) -> WriteLessonsUseCase:
    return WriteLessonsUseCase(DeliverySignals(cwd), DeliveryLessons(cwd))


def write_issue(cwd: str) -> WriteIssueUseCase:
    return WriteIssueUseCase(LessonIssueFiles(cwd))


def propose_lessons(cwd: str) -> typing.Callable[[str], typing.List[typing.Tuple[str, str, str]]]:
    """What the backlog run calls when nothing more can run: each candidate nobody was asked yet becomes a lesson
    record — [(record id, kind, where)]. Delivery calls it by the moment it reads, knowing no lesson."""
    proposals = LessonProposals(DeliverySignals(cwd), DeliveryLessons(cwd))
    return lambda at: [(rid, kind.value, where) for rid, kind, where in proposals.propose(Moment(at))]
