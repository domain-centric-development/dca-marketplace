"""A story's place and its fields as written: a story is a folder of its own under its epic,
`<epics>/<epic>/<story>/` with its `story.md`, its decision records and its findings inside; the epic is
`<epics>/<epic>/epic.md` beside its story folders. Its id, its kind, its dependencies, where it stands in its front
matter, and its digest — what is the person's, the state the gate writes left out."""

from __future__ import annotations

import hashlib
import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import (
    MarkdownError as GateError, read_front_matter, read_text, split_front)
from .....sharedkernel.adapter.outgoing.profile.profile_files import shown
from ....application.shared.front import CREATED_KEY
from ....domain.model.story import KindWord, StoryStatus
from ....domain.model.stage import SpecHome, StoryKind

#: The epic is `<epics>/<epic>/epic.md` beside its story folders — one shape for both, a folder and its file.
EPIC_FILE = "epic.md"


#: A story's decision records: `<story>/decisions/` beside its `story.md`.
DECISIONS_DIR = "decisions"


#: A story is a folder of its own under its epic, `<epics>/<epic>/<story>/`, with everything that belongs to it
#: inside: the story itself, its decision records and acceptances, the judge's findings that did not block.
#: The epic is `<epics>/<epic>/epic.md` beside its story folders — one shape for both, a folder and its file.
STORY_FILE = "story.md"


def story_files(epics: str) -> typing.List[str]:
    """Every story under the epics, sorted: `<epics>/<epic>/<story>/story.md`. A file beside the epics (a
    README) or beside the story folders (`epic.md`) is not a story; a story file of the older flat layout
    (`<epic>/<story>.md`) is not read — `layout_hint` names it and `factory.sh update` moves it."""
    found: typing.List[str] = []
    if not os.path.isdir(epics):
        return found
    for epic in sorted(os.listdir(epics)):
        folder = os.path.join(epics, epic)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name, STORY_FILE)
            if os.path.isfile(path):
                found.append(path)
    return found


def story_folder(story_path: str) -> str:
    """The story's own folder: where its decisions and findings live, and the name its id defaults to."""
    return os.path.dirname(story_path)


def epic_folder(story_path: str) -> str:
    """The folder of the epic a story lies in: the parent of the story's folder."""
    return os.path.dirname(story_folder(story_path))


def flat_stories(epics: str) -> typing.List[str]:
    """Story files of the older flat layout — `<epics>/<epic>/<story>.md` beside `epic.md` — which this gate
    no longer reads."""
    found: typing.List[str] = []
    if not os.path.isdir(epics):
        return found
    for epic in sorted(os.listdir(epics)):
        folder = os.path.join(epics, epic)
        if os.path.isdir(folder):
            found += [os.path.join(folder, name) for name in sorted(os.listdir(folder))
                      if name.endswith(".md") and name != EPIC_FILE and not name.endswith(".findings.md")
                      and os.path.isfile(os.path.join(folder, name))]
    return found


def story_id_of(path: str, front: typing.Optional[typing.Mapping[str, typing.Any]] = None) -> str:
    """A story's id: its front matter's `id:`, else its folder's name."""
    if front is None:
        try:
            front, _ = read_front_matter(path)
        except GateError:
            front = {}
    return str(front.get("id", "")).strip() or os.path.basename(story_folder(path))


def find_story(epics: str, story_id: str) -> str:
    """The one story file with this id. Two files with one id are refused, naming both: the schedule keys
    stories by id, the run folder and the decisions are named after it, so a second one would silently
    replace the first."""
    wanted, matches = story_id.lower(), typing.cast(typing.List[str], [])
    for path in story_files(epics):
        if os.path.basename(story_folder(path)).lower() == wanted or story_id_of(path).lower() == wanted:
            matches.append(path)
    if len(matches) > 1:
        raise GateError(f"story id {story_id!r} is not unique — {' and '.join(shown(m) for m in matches)}; "
                        f"an id names one story in the whole project, give one of them another")
    if matches:
        return matches[0]
    flat = [p for p in flat_stories(epics) if os.path.splitext(os.path.basename(p))[0].lower() == wanted]
    if flat:
        raise GateError(f"{shown(flat[0])} is in the older flat layout — a story is a folder now, "
                        f"{epics}/<epic>/<story>/{STORY_FILE}; `factory.sh update` moves it")
    raise GateError(
        f"no story {story_id!r} under {epics}/ — a story is a folder {epics}/<epic>/<story>/ with its "
        f"{STORY_FILE} (front matter, see the backlog contract)"
    )


def duplicate_ids(epics: str) -> typing.Dict[str, typing.List[str]]:
    """{id: [paths]} for every id more than one story carries."""
    by_id: typing.Dict[str, typing.List[str]] = {}
    for path in story_files(epics):
        by_id.setdefault(story_id_of(path).lower(), []).append(path)
    return {sid: paths for sid, paths in by_id.items() if len(paths) > 1}


def is_delivered(front: typing.Mapping[str, typing.Any]) -> bool:
    """Delivered is one state, written into the story: `status: delivered` — by the gate that delivered it, or by
    a person who delivered it by hand (`delivered_by: hand:<who>`). Built or adopted makes no difference once
    delivered (one end state)."""
    return str(front.get("status", "")).strip().lower() == StoryStatus.DELIVERED.value


def delivered_on(front: typing.Mapping[str, typing.Any]) -> str:
    value = front.get("delivered", "")
    return value.strip() if isinstance(value, str) else ""


def delivered_by(front: typing.Mapping[str, typing.Any]) -> str:
    """Who claims the delivery: `gate`, `hand:<who>`, or "" for a story delivered before the line existed."""
    value = front.get("delivered_by", "")
    return value.strip() if isinstance(value, str) else ""


#: The lines of a story's front matter the gate and a hand delivery write; a story's digest leaves them out, so
#: a delivery does not read as "the story changed after it was planned".
STATE_KEYS = ("status", "delivered", "delivered_by")


#: When a story or an epic was written: `created:` in its front matter, a UTC time (`2026-10-18T09:12:00Z`; a date
#: alone reads as well). The backlog skill writes it with the item, `update` fills it once from git for an item
#: without it (the commit that added the file). The views order the backlog by it, newest first; an item without it
#: comes last. It says nothing about what the story asks for, so the story's digest leaves it out too.


#: The front-matter lines a story's digest leaves out: its state and when it was written.
DIGEST_LEFT_OUT = STATE_KEYS + (CREATED_KEY,)


def story_digest(path: str) -> str:
    """The story as planned: SHA-256 over the file with LF line endings and the state lines (`STATE_KEYS`) and its
    `created:` line left out — the front matter read by lines (`split_front`), an indented line never a key."""
    text = read_text(path).replace("\r\n", "\n")
    split = split_front(text)
    if split is not None:
        front_lines, body = split
        kept = [line for line in front_lines
                if line.startswith((" ", "\t", "-")) or line.split(":", 1)[0].strip().lower() not in DIGEST_LEFT_OUT]
        text = "---\n" + "".join(line + "\n" for line in kept) + "---" + body
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def legacy_story_digest(path: str) -> str:
    """`story_digest` as contract 17 had it — split on the first `---` anywhere. Read by the migration alone, to
    take a planned story's mark anew with today's function."""
    text = read_text(path)
    parts = text.split("---", 2)
    if len(parts) >= 3:
        kept = [line for line in parts[1].splitlines()
                if line.split(":", 1)[0].strip().lower() not in ("status", "delivered") or line.startswith((" ", "\t", "-"))]
        text = "---" + "\n".join(kept) + "\n---" + parts[2]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def story_kind(front: typing.Mapping[str, typing.Any]) -> str:
    """`story` (the default), `journey` — a guard over an epic's delivered stories, run as plan, test,
    judge and document, green at its test gate —, `task` — a change no actor sees, run as plan, build, tidy, judge
    and document on the existing suite — or `adopt`: a story with `status: adopted` describes behaviour the project
    already has; plan, test and judge map it to green tests, the adopt gate delivers it."""
    status = str(front.get("status", "")).strip().lower()
    known = next((s for s in StoryStatus if s.value == status), StoryStatus.OTHER)
    return KindWord(str(front.get("kind") or "")).kind(known).value


def journeys_hold(front: typing.Mapping[str, typing.Any]) -> bool:
    """Whether the story's criteria hold among the project's journeys rather than in its context (`SpecHome`)."""
    return SpecHome.of(StoryKind(story_kind(front))) is SpecHome.JOURNEYS


def depends_on(front: typing.Mapping[str, typing.Any]) -> typing.List[str]:
    """`depends_on: []`, `depends_on: [A, B]` or a `- A` list, as a list of ids."""
    value = front.get("depends_on") or []
    if isinstance(value, str):
        value = [part for part in value.strip().strip("[]").split(",")]
    return [str(part).strip().strip("'\"") for part in value if str(part).strip().strip("'\"")]


def file_digest(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def story_ids(epics: str) -> typing.List[str]:
    """Every story id under the epics, in the order of the files — front matter first, else the file name."""
    return [story_id_of(path) for path in story_files(epics)]
