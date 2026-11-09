"""What the working tree looked like at one edge of a stage window (WP-202) — the one observation both the snapshot's
readers (the observer, a stage's own changes) and the record's (the story's change against its base) read.

Taken once when a window starts and once when it ends: the files that differ from HEAD with the digest of their
bytes, which of them git tracks, HEAD itself, and — where a reader needs it — the tree object of everything as it is.
A stage's changes are the difference of its two edges."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .project_path import ProjectPath


class Digest(Value):
    """A file's content as an observation saw it: the sha256 of its bytes, `deleted`, or `-` where nothing hashed it."""

    value: str


#: A file that HEAD has and the working tree no longer does.
DELETED = Digest("deleted")
#: A file observed without its content (no hashing on that machine): names only.
UNHASHED = Digest("-")
#: A path an observation does not list, as HEAD has it.
AS_HEAD = Digest("head")


class Tracking(enum.Enum):
    """Whether git tracks a path: a path an observation does not list is as HEAD has it — there when tracked."""

    TRACKED = "tracked"
    UNTRACKED = "untracked"


class Hashing(enum.Enum):
    """Whether the observation carries content digests, or names only."""

    HASHED = "hashed"
    NAMES_ONLY = "names only"


class ObjectName(Value):
    """A git object's name — a tree's or a commit's."""

    value: str


class TreeChange(enum.Enum):
    """What a window did to a path, as the changed-files records write it."""

    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"


class ObservedFile(Value):
    """One path that differs from HEAD at the edge: its digest, and whether git tracks it."""

    place: ProjectPath
    digest: Digest
    tracking: Tracking


class ChangedFile(Value):
    """One row of a window's changes."""

    change: TreeChange
    place: ProjectPath


class TreeObservation(Value):
    """The working tree at one edge of a window."""

    files: typing.Tuple[ObservedFile, ...]
    head: typing.Optional[ObjectName]
    tree: typing.Optional[ObjectName]
    hashing: Hashing

    def digests(self) -> typing.Dict[ProjectPath, Digest]:
        """{path: digest} — the snapshot's view."""
        return {f.place: f.digest for f in self.files}

    def head_moved_from(self, earlier: TreeObservation) -> bool:
        return self.head != earlier.head

    def changes_since(self, earlier: TreeObservation,
                      between_heads: typing.Mapping[ProjectPath, TreeChange] = {}) -> typing.Tuple[ChangedFile, ...]:
        """The paths whose content differs between `earlier` and this observation. A path one of them does not list is
        as its HEAD has it: there when git tracks it, absent otherwise. `between_heads` names the paths HEAD itself
        changed between the two edges (a window that committed), each as a change of its own."""
        tracked = {f.place for f in earlier.files + self.files if f.tracking is Tracking.TRACKED}
        was_map, now_map = earlier.digests(), self.digests()

        def state(digests: typing.Mapping[ProjectPath, Digest], path: ProjectPath) -> typing.Optional[Digest]:
            return digests.get(path, AS_HEAD if path in tracked else None)

        def exists(value: typing.Optional[Digest]) -> bool:
            return value not in (None, DELETED)
        rows = []
        for path in sorted(set(was_map) | set(now_map) | set(between_heads), key=lambda place: place.value):
            was, now = state(was_map, path), state(now_map, path)
            if path in between_heads and path not in was_map and path not in now_map:
                rows.append(ChangedFile(between_heads[path], path))
                continue
            if was == now or not (exists(was) or exists(now)):
                continue
            change = TreeChange.REMOVED if not exists(now) else TreeChange.ADDED if not exists(was) else TreeChange.MODIFIED
            rows.append(ChangedFile(change, path))
        return tuple(rows)
