"""The stories under the epics as files: each story file read for the backlog check, or why it cannot be."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from .....sharedkernel.adapter.outgoing.profile.profile_files import shown
from ....application.shared.backlog_entries import BacklogEntry
from ....domain.model.stage_story import Place
from ....domain.model.story import StoryId
from ....domain.model.story_state import Detail, StatusWord
from .criteria_files import criteria_of
from .stage_evidence_files import stage_story
from .story_layout import duplicate_ids, is_delivered, story_files, story_folder


class BacklogEntryFiles:
    """The story files under <epics>."""

    def __init__(self, epics: str) -> None:
        self._epics = epics

    def twice(self) -> typing.Mapping[StoryId, typing.Tuple[Place, ...]]:
        return {StoryId(sid): tuple(Place(shown(p)) for p in paths)
                for sid, paths in duplicate_ids(self._epics).items()}

    def entries(self) -> typing.Iterator[BacklogEntry]:
        for path in story_files(self._epics):
            folder = StoryId(os.path.basename(story_folder(path)))
            try:
                front, body = read_front_matter(path)
            except MarkdownError as error:
                yield BacklogEntry(folder, folder, Place(path), None, False, None, Detail(str(error)))
                continue
            label = StoryId(str(front.get("id") or folder.value).strip())
            status = StatusWord(str(front.get("status", "")).strip().lower())
            try:
                story = stage_story(label.value, path, front, body, criteria_of(path, body, front))
            except MarkdownError as error:
                yield BacklogEntry(label, folder, Place(path), status, is_delivered(front), None, Detail(str(error)))
                continue
            yield BacklogEntry(label, folder, Place(path), status, is_delivered(front), story, None)
