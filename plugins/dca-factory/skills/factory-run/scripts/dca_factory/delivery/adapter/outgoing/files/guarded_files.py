"""The guarded set as files: the profile's `guarded:` key beside the profile itself, the plan's `## Guarded changes`,
what the story changed of the project (its stages' records, still different from its base), the story diff's sections
of the announced paths, and the project's files under a glob — for the gate, the acceptance and the runner's wall."""

from __future__ import annotations

import glob
import os
import re
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, PROFILE_FILE
from ....domain.model.guarded import GuardedChange, GuardedPattern, GuardedSet
from ....domain.model.story_state import Detail
from ....domain.model.story_words import Place
from .run_marks import window_open
from .snapshots import NOT_OBSERVED, git_tree, tree_changes

#: A line of the plan's `## Guarded changes`: `- \`<path>\` — <reason>`.
GUARDED_LINE = re.compile(r"^\s*[-*]\s*`([^`]+)`\s*(?:[—–:-]+\s*(.*))?$")

#: Folders a walk for the files under a guarded glob never enters.
UNWALKED = {".git", ".gradle", ".idea", ".vs", "build", "bin", "obj", "target", "dist", "out", "node_modules",
            ".dca-factory", ".venv", "venv", "__pycache__"}


def plain(path: str) -> str:
    """A path as the records write it: `/` between segments, no leading `./`."""
    path = path.strip().strip("`").replace("\\", "/")
    return path[2:] if path.startswith("./") else path


def guarded_set(profile: typing.Mapping[str, typing.Any]) -> GuardedSet:
    """The profile file and the globs of its `guarded:`."""
    return GuardedSet.of(Place(PROFILE_FILE), Detail(str(profile.get("guarded") or "")))


def announced_changes(runs: str, story_id: str) -> typing.Optional[typing.Tuple[GuardedChange, ...]]:
    """The plan's `## Guarded changes`, path and reason per line — None where the plan or the section is missing."""
    path = os.path.join(runs, story_id, "plan.md")
    if not os.path.isfile(path):
        return None
    lines = section_of(read_text(path), "guarded changes")
    if lines is None:
        return None
    changes = []
    for line in lines:
        match = GUARDED_LINE.match(line)
        if match and not any(c in match.group(1) for c in "<>{}"):
            changes.append(GuardedChange(Place(plain(match.group(1))), Detail((match.group(2) or "").strip())))
    return tuple(changes)


def _rows(path: str) -> typing.Optional[typing.List[str]]:
    if not os.path.isfile(path):
        return None
    text = read_text(path)
    if text.startswith(NOT_OBSERVED):
        return None
    return [line.split("\t", 1)[1].strip() for line in text.splitlines() if "\t" in line]


def story_changed(cwd: str, runs: str, story_id: str, checkouts: typing.Any = None) -> typing.Optional[typing.List[str]]:
    """The paths a stage of the story changed that still differ from the story's base: in a stage record and in the
    story's record — a path a stage put back drops out, and one a pipeline update changed between stages was no
    stage's. While the shared builder's window is open, the tree against the base. None where nothing was recorded."""
    folder = evidence_dir(runs, story_id)
    base_file = os.path.join(folder, "base-tree")
    if window_open(runs, story_id, "builder") and os.path.isfile(base_file):
        base = read_text(base_file).strip()
        now = git_tree(cwd, checkouts) if base and base != "none" else None
        rows = tree_changes(cwd, base, now, runs) if now else None
        if rows is not None:
            return [path for _kind, path in rows]
    staged: typing.Optional[typing.Set[str]] = None
    for record in sorted(glob.glob(os.path.join(folder, "changed-*.txt"))):
        rows_of = _rows(record)
        if rows_of is not None:
            staged = (staged or set()) | set(rows_of)
    if staged is None:
        return None
    story = _rows(os.path.join(folder, "changed.txt"))
    return sorted(staged if story is None else staged & set(story))


def diff_sections(runs: str, story_id: str, paths: typing.Iterable[str]) -> typing.Dict[str, str]:
    """The story diff's section of each of <paths> — none for a path the diff does not hold."""
    path = os.path.join(evidence_dir(runs, story_id), "story.diff")
    if not os.path.isfile(path):
        return {}
    wanted = {plain(p) for p in paths}
    sections: typing.Dict[str, str] = {}
    current: typing.Optional[str] = None
    for line in read_text(path).splitlines():
        if line.startswith("diff --git "):
            named = line.split(" b/", 1)[-1].strip()
            current = named if named in wanted else None
            if current:
                sections[current] = ""
        if current:
            sections[current] += line + "\n"
    return sections


def present_files(cwd: str, patterns: typing.Iterable[GuardedPattern]) -> typing.Tuple[Place, ...]:
    """The project's files under <patterns>, relative to <cwd>."""
    patterns = list(patterns)
    if not patterns:
        return ()
    found: typing.List[Place] = []
    for root, dirs, names in os.walk(cwd):
        dirs[:] = sorted(d for d in dirs if d not in UNWALKED)
        rel = os.path.relpath(root, cwd).replace(os.sep, "/")
        for name in sorted(names):
            place = Place(name if rel == "." else f"{rel}/{name}")
            if any(p.covers(place) for p in patterns):
                found.append(place)
    return tuple(found)
