"""The decision records, beside their stories and the project's own."""

from __future__ import annotations

import typing

from ....building_blocks import Repository, UseCaseException
from ...domain.model.decision_record import DecisionRecord, RecordId
from ...domain.model.story import StoryId


class RecordNotFound(UseCaseException):
    """No decision record by this id, or one that cannot be read — the message says which."""


class DecisionRecordRepository(Repository[DecisionRecord, RecordId], typing.Protocol):
    """The decision records: beside each story, and the project's own without a story."""

    def get(self, record_id: RecordId) -> DecisionRecord:
        """The record with this id; RecordNotFound otherwise."""
        ...

    def open_acceptance_of(self, story: StoryId) -> typing.Optional[DecisionRecord]:
        """The story's newest acceptance that is open or a draft, or None."""
        ...

    def open_records_of(self, story: StoryId) -> typing.Sequence[DecisionRecord]:
        """Every record of the story that is open or a draft."""
        ...
