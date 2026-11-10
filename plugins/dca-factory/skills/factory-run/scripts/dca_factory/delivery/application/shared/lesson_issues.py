"""The lessons that go up: an answered lesson as the issue text reads it, and where the text is kept."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import OutputPort
from ...domain.model.decision_record import RecordId
from ...domain.model.lesson import LessonKind, LessonPlace, SignalKey
from ...domain.model.maintainer_issue import MaintainerIssue
from ...domain.model.story_words import Count, Detail


@dataclasses.dataclass(frozen=True)
class AnsweredLesson:
    """A lesson record as the issue reads it: its kind, key and stories, and the place its answer named."""

    kind: LessonKind
    key: SignalKey
    stories: Count
    place: typing.Optional[LessonPlace]


class LessonIssues(OutputPort, typing.Protocol):
    """The lesson records and the factory's own folder for issue texts."""

    def answered(self, record: RecordId) -> typing.Optional[AnsweredLesson]:
        """The lesson by this id with its answer; None where there is none, or it is not answered."""
        ...

    def pipeline(self) -> Detail:
        """The pipeline that saw it: `dca-factory <version>, contract <n>`."""
        ...

    def write(self, record: RecordId, issue: MaintainerIssue, text: Detail) -> str:
        """Keep the text as `<factory folder>/issues/<target>-<signal>-<digest of the record's id>.md` — a name with
        no word of the project; where, as a person reads it."""
        ...
