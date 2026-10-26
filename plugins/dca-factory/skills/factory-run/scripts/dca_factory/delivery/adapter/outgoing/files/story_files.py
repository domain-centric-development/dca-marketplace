"""The stories as files: `<epics>/<epic>/<story>/story.md`, the state in the front matter."""

from __future__ import annotations

import contextlib
import os
import typing

from .story_layout import (
    delivered_by, delivered_on, epic_folder, find_story, story_files, story_folder, story_id_of, story_ids)
from .....sharedkernel.adapter.outgoing.profile.profile_files import place
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .owned_files import write_story_fields
from ....application.shared.requests import ID_WORD
from ....application.shared.story_repository import StoryNotFound
from ....domain.model.epic import EpicId
from ....domain.model.story import (
    Assumption, DeliveredBy, DeliveredOn, Delivery, KindWord, Story, StoryId, StoryStatus)
from .epic_files import epic_dir
from .request_files import write_atomic

ASSUMPTIONS = "assumptions"


def status_of(value: typing.Any) -> StoryStatus:
    text = str(value or "").strip().lower()
    return next((s for s in StoryStatus if s.value == text and s is not StoryStatus.OTHER), StoryStatus.OTHER)


def add_assumption(path: str, line: str) -> None:
    """One line at the end of the story's `## Assumptions` — the section added where the story has none."""
    lines = read_text(path).splitlines()
    head = next((i for i, l in enumerate(lines) if l.strip().lower().startswith("## assumptions")), None)
    if head is None:
        lines += ["", "## Assumptions", "", line]
    else:
        end = next((i for i in range(head + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        while end > head + 1 and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, line)
    write_atomic(path, "\n".join(lines) + "\n")


def names_story(word: str) -> bool:
    """Whether one word is the id of a story under the epics, as the profile places them."""
    if not ID_WORD.match(word):
        return False
    wanted = word.lower()
    with contextlib.suppress(MarkdownError, OSError):
        return any(os.path.basename(story_folder(path)).lower() == wanted or story_id_of(path).lower() == wanted
                   for path in story_files(place("epics")))
    return False


class StoryFiles:
    """The story repository as files, under the project the process works in — or under the epics folder given."""

    def __init__(self, cwd: str, epics: typing.Optional[str] = None) -> None:
        self._epics = epics or os.path.join(cwd, place("epics"))

    def path_of(self, story_id: StoryId) -> str:
        """The story's file; StoryNotFound with the reason where no single story has the id."""
        try:
            return str(find_story(self._epics, story_id.value))
        except MarkdownError as error:
            raise StoryNotFound(f"no story {story_id.value} under {place('epics')}/ — {error}") from None

    def get(self, story_id: StoryId) -> Story:
        return self.read(self.path_of(story_id))

    def find_by_id(self, aggregate_id: StoryId) -> typing.Optional[Story]:
        try:
            return self.get(aggregate_id)
        except StoryNotFound:
            return None

    def stories_of(self, epic: EpicId) -> typing.Sequence[Story]:
        folder = epic_dir(self._epics, epic.value)
        return [self.read(path) for path in story_files(self._epics)
                if folder and os.path.dirname(os.path.dirname(path)) == folder]

    def save(self, aggregate: Story) -> Story:
        return self.write(self.path_of(aggregate.id), aggregate)

    @staticmethod
    def write(path: str, aggregate: Story) -> Story:
        """The story's state written into its file at `path` — a story in a worktree as well as in the checkout."""
        front, body = read_front_matter(path)
        state = dict(status=aggregate.status.value,
                     delivered=aggregate.delivery.on.value or None if aggregate.delivery else None,
                     delivered_by=aggregate.delivery.by.value or None if aggregate.delivery else None)
        written_state = dict(status=status_of(front.get("status")).value, delivered=delivered_on(front) or None,
                             delivered_by=delivered_by(front) or None)
        changed = {key: value for key, value in state.items() if value != written_state[key]}
        if changed:
            write_story_fields(path, **changed)
        written = {line.strip() for line in section_of(body, ASSUMPTIONS) or []}
        for assumption in aggregate.assumptions:
            if assumption.value.strip() not in written:
                add_assumption(path, assumption.value)
        return aggregate

    def delete_by_id(self, aggregate_id: StoryId) -> None:
        os.remove(self.path_of(aggregate_id))

    def ids(self) -> typing.Sequence[StoryId]:
        return [StoryId(story_id) for story_id in story_ids(self._epics)] if os.path.isdir(self._epics) else []

    def names_story(self, word: str) -> bool:
        return names_story(word)

    @staticmethod
    def read(path: str) -> Story:
        front, body = read_front_matter(path)
        assumptions = [Assumption(line.rstrip()) for line in section_of(body, ASSUMPTIONS) or [] if line.strip()]
        on, by = delivered_on(front), delivered_by(front)
        delivery = Delivery(DeliveredOn(on), DeliveredBy(by)) if on or by else None
        return Story(StoryId(story_id_of(path, front)), EpicId(os.path.basename(epic_folder(path))),
                     status_of(front.get("status")), assumptions, delivery, KindWord(str(front.get("kind") or "")))
