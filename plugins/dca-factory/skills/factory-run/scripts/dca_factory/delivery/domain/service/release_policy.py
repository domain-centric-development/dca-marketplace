"""Which drafts a release may approve without the backlog skill."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import DomainService
from ..model.decision_record import DecisionRecord
from ..model.story import Story, StoryStatus


class QuestionPass(enum.Enum):
    """Whether the question pass ran on the draft as it stands — on an older text it did not."""

    RAN_ON_IT = "ran on it"
    NOT_RAN = "not ran"


class ReleasePolicy(DomainService):
    """A draft whose question pass ran on it as it stands and none of whose records waits for a person is released by
    a press; any other one needs the backlog skill, which asks what the draft leaves open."""

    @staticmethod
    def releasable(story: Story, question_pass: QuestionPass, records: typing.Sequence[DecisionRecord]) -> bool:
        return story.status is StoryStatus.DRAFT and question_pass is QuestionPass.RAN_ON_IT \
            and not any(record.waits() for record in records)
