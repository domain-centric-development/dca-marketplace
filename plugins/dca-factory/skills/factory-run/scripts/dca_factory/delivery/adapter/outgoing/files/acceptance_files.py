"""A story's acceptance records as files, as a correction asks them."""

from __future__ import annotations

import typing

from .criteria_files import criteria_of
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from ....application.shared.front import accepted
from ....domain.model.decision_record import RecordId
from ....domain.model.story import StoryId
from .decision_record_files import acceptance_records, latest_verdict, Records
from ....domain.model.story_state import AcceptanceVerdict
from .run_marks import accepted_criteria
from .story_layout import find_story


class AcceptanceFiles:
    """The acceptance records beside the stories under <epics>, in the project <cwd>."""

    def __init__(self, cwd: str, epics: str) -> None:
        self._cwd = cwd
        self._epics = epics

    def _records(self, story: StoryId) -> typing.Tuple[str, Records]:
        path = find_story(self._epics, story.value)
        return path, acceptance_records(self._cwd, story.value, path)

    def correction_of(self, story: StoryId) -> typing.Optional[RecordId]:
        _path, records = self._records(story)
        # Whatever the story says since: the correction is what the person answered last.
        if not records or latest_verdict(records) is not AcceptanceVerdict.CORRECTION:
            return None
        return RecordId(records[-1][0])

    def cited(self, story: StoryId, record: RecordId) -> bool:
        return record.value in read_text(find_story(self._epics, story.value))

    def changed_since_accepted(self, story: StoryId) -> typing.Sequence[str]:
        # After an acceptance, the criteria as accepted are the record's list: a correction that changes one of
        # them is a new wish.
        path, records = self._records(story)
        earlier = [record for record in records[:-1] if accepted(record[3])]
        if not earlier:
            return ()
        before = dict(accepted_criteria(earlier[-1][4]))
        now = dict(criteria_of(path, read_front_matter(path)[1]))
        return sorted(key for key, value in before.items() if now.get(key) != value)
