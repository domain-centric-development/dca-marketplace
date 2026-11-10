"""Write the issue text a lesson answered `factory`, `rule-library` or `knowledge-catalog` sends up — anonymised; a
person sends it, nothing leaves the machine by itself."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.decision_record import RecordId
from ...domain.model.maintainer_issue import IssueTarget, MaintainerIssue
from ..shared.lesson_issues import LessonIssues
from ..shared.outcomes import NeedsSkill


@dataclasses.dataclass(frozen=True)
class WriteIssueCommand:
    record: RecordId


@dataclasses.dataclass(frozen=True)
class IssueWritten:
    """Where the text lies, and the text itself."""

    path: str
    text: str


WriteIssueResult = typing.Union[IssueWritten, NeedsSkill]


class WriteIssueInputPort(UseCase[WriteIssueCommand, WriteIssueResult], typing.Protocol):
    """The issue text of one answered lesson whose place goes up."""


class WriteIssueUseCase(WriteIssueInputPort):
    """A lesson answered with a place of the maintainers' becomes an issue text under the factory's own folder, named
    by no word of the project; any other lesson, or one not answered, writes nothing and says why."""

    def __init__(self, issues: LessonIssues) -> None:
        self._issues = issues

    def execute(self, command: WriteIssueCommand) -> WriteIssueResult:
        lesson = self._issues.answered(command.record)
        if lesson is None:
            return NeedsSkill(f"{command.record.value} is no answered lesson — answer it first (/factory-decisions)")
        if lesson.place is None or not lesson.place.goes_up:
            return NeedsSkill(f"{command.record.value} was placed in the project "
                              f"({lesson.place.value if lesson.place else 'no place'}) — only `factory`, "
                              "`rule-library` and `knowledge-catalog` go up to the maintainers")
        issue = MaintainerIssue(IssueTarget(lesson.place), lesson.kind, lesson.key, lesson.stories,
                                self._issues.pipeline())
        text = issue.text()
        return IssueWritten(self._issues.write(command.record, issue, text), text.value)
