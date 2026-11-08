"""The stories as files: `<epics>/<epic>/<story>/story.md`, the state in the front matter."""

from __future__ import annotations

import contextlib
import os
import re
import typing

from .plan_adoption_files import split_off
from .story_layout import STORY_FILE
from .story_layout import (
    deliverer_of, named_kind, delivered_by, delivered_on, epic_folder, find_story, story_files, story_folder, story_id_of, story_ids)
from .....sharedkernel.adapter.outgoing.profile.profile_files import place, release_required, shown
from ....domain.model.stage_story import Place
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError, MarkdownError, read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .owned_files import write_story_fields
from ....application.shared.requests import ID_WORD
from ....application.shared.story_repository import StoryNotFound
from ....domain.model.epic import EpicId
from ....domain.model.story import (
    Assumption, DeliveredOn, Delivery, Releasing, Story, StoryId, StoryStatus)
from .criteria_files import criteria_of
from .epic_files import epic_dir
from .stage_evidence_files import story_content
from .request_files import write_atomic
from ....application.shared.story_repository import StoryRepository

ASSUMPTIONS = "assumptions"


def status_of(value: typing.Any) -> StoryStatus:
    text = str(value or "").strip().lower()
    return next((s for s in StoryStatus if s.value == text and s is not StoryStatus.OTHER), StoryStatus.OTHER)


def add_assumption(path: str, line: str) -> None:
    """One line at the end of the story's `## Assumptions` — the section added where the story has none."""
    with open(path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    while lines and not lines[-1]:
        lines.pop()
    head = next((i for i, l in enumerate(lines) if l.strip().lower().startswith("## assumptions")), None)
    if head is None:
        lines += ["", "## Assumptions", "", line]
    else:
        end = next((i for i in range(head + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        while end > head + 1 and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, line)
    write_atomic(path, newline.join(lines) + newline)


def cut_scenarios(path: str, keys: typing.Collection[str]) -> None:
    """The story at <path> without the scenarios <keys> — a rule left without one goes with them —, its line endings
    kept."""
    with open(path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    rest, _moved = split_off(text.split(newline), keys)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(newline.join(rest))


def names_story(word: str) -> bool:
    """Whether one word is the id of a story under the epics, as the profile places them."""
    if not ID_WORD.match(word):
        return False
    wanted = word.lower()
    with contextlib.suppress(MarkdownError, OSError):
        return any(os.path.basename(story_folder(path)).lower() == wanted or story_id_of(path).lower() == wanted
                   for path in story_files(place("epics")))
    return False


class StoryFiles(StoryRepository):
    """The story repository as files, under the project the process works in — or under the epics folder given."""

    def __init__(self, cwd: str, epics: typing.Optional[str] = None) -> None:
        self._epics = epics or os.path.join(cwd, place("epics"))

    def path_of(self, story_id: StoryId) -> str:
        """The story's file; StoryNotFound with the reason where no single story has the id."""
        try:
            return str(find_story(self._epics, story_id.value))
        except MarkdownError as error:
            raise StoryNotFound(f"no story {story_id.value} under {place('epics')}/ — {error}") from None

    def place_of(self, story_id: StoryId) -> Place:
        return Place(shown(self.path_of(story_id)))

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
        if aggregate.split_from is not None and self.find_by_id(aggregate.id) is None:
            return self._add_split(aggregate, aggregate.split_from)
        path = self.path_of(aggregate.id)
        if aggregate.split_off_scenarios:
            cut_scenarios(path, {k.value for k in aggregate.split_off_scenarios})
        return self.write(path, aggregate)

    def _add_split(self, aggregate: Story, source: StoryId) -> Story:
        """A story split off another one: its file beside the source's, its scenarios as the source still says them,
        its rules with them."""
        source_path = self.path_of(source)
        front, _body = read_front_matter(source_path)
        with open(source_path, encoding="utf-8", newline="") as handle:
            text = handle.read()
        newline = "\r\n" if "\r\n" in text else "\n"
        _rest, moved = split_off(text.split(newline), {k.value for k in aggregate.content.criteria})
        title = str(front.get("title") or source.value).strip()
        fields = [f"id: {aggregate.id.value}"] + [f"{k}: {front[k]}" for k in ("epic", "context", "feature")
                                                   if front.get(k)] + [
            f"status: {aggregate.status.value}", f"created: {aggregate.created.value if aggregate.created else ''}",
            f"title: {title} — what holds today"]
        body = ["---", *fields, "---", "", f"# {title} — what holds today", "", "## Story", "",
                f"Split from story `{source.value}` by its plan: these scenarios hold on today's code, and no "
                "delivered story carries them.", "", "## Acceptance criteria", "", *moved, "",
                "## Assumptions", "", *[a.value for a in aggregate.assumptions], ""]
        folder = os.path.join(os.path.dirname(os.path.dirname(source_path)), aggregate.id.value)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, STORY_FILE), "w", encoding="utf-8", newline="") as handle:
            handle.write(newline.join(re.sub(r"\s*\(happy path\)\s*$", "", line) for line in body))
        return aggregate

    @staticmethod
    def write(path: str, aggregate: Story) -> Story:
        """The story's state written into its file at `path` — a story in a worktree as well as in the checkout."""
        front, body = read_front_matter(path)
        state = dict(status=aggregate.status.value,
                     delivered=aggregate.delivery.on.value or None if aggregate.delivery else None,
                     delivered_by=aggregate.delivery.by.line().value or None if aggregate.delivery else None)
        # the written claim read the way the aggregate reads it: a word the factory does not know stays as written
        written_state = dict(status=status_of(front.get("status")).value, delivered=delivered_on(front) or None,
                             delivered_by=deliverer_of(front).line().value or None)
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
        return story_of(path, front, body)


def story_of(path: str, front: typing.Mapping[str, typing.Any], body: str,
             criteria: typing.Optional[typing.Sequence[typing.Tuple[str, str]]] = None) -> Story:
    """The story at <path>, read off its front matter and body; <criteria> where a caller read them already."""
    assumptions = [Assumption(line.rstrip()) for line in section_of(body, ASSUMPTIONS) or [] if line.strip()]
    on, by = delivered_on(front), delivered_by(front)
    delivery = Delivery(DeliveredOn(on), deliverer_of(front)) if on or by else None
    said = criteria
    if said is None:
        # the story's life — release, delivery, a take-back — does not rest on how its criteria are written; the gate
        # reads them itself and refuses a malformed one there
        try:
            said = criteria_of(path, body, front)
        except GateError:
            said = ()
    return Story.restore(StoryId(story_id_of(path, front)), EpicId(os.path.basename(epic_folder(path))),
                 status_of(front.get("status")), assumptions, delivery, named_kind(front),
                 content=story_content(front, body, said),
                 releasing=Releasing.REQUIRED if release_required() else Releasing.OPTIONAL)
