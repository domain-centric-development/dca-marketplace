"""A picture of what a story built (WP-184): taken by its end-user tests, collected by the runner after a test run,
shown on the story's place — which pictures count, what they are called and how many are shown."""

from __future__ import annotations

import enum
import re
import typing

from ....building_blocks import Value
from .handed_file import MAX_BYTES, ByteSize, FileBytes, FileName, kind_of
from .moment import Moment
from .project_path import ProjectPath
from .stage_story import CommandKey

#: At most this many pictures a story's place shows — the newest.
SHOWN = 24
#: A picture taken a little before its run's own start still counts: a test runner may stamp a file as it opens it.
SLACK = 5.0
#: The folder beneath a story's run folder its pictures are kept in.
SHOTS = "shots"
#: A test run the step reuses instead of running it again was run within this many seconds before the step began.
REUSED_WITHIN = 3600.0


class RunOrigin(enum.Enum):
    """Whether a step ran its test command itself or reused a run made before it."""

    RAN = "ran"
    REUSED = "reused"


class Instant(Value):
    """A point in time as a clock gives it, in seconds — when a file was written, when a run started."""

    value: float


class ShotTaker(Value):
    """What took a picture: a stage, or the test command whose run made it (`e2e`, `journey`)."""

    value: str

    @staticmethod
    def of(key: CommandKey) -> "ShotTaker":
        word = key.value[len("test."):] if key.value.startswith("test.") else "e2e" if key.value == "e2eTest" else key.value
        return ShotTaker(re.sub(r"[^a-z0-9]+", "-", word.lower()).strip("-") or "test")


def shot_name(key: CommandKey, relative: ProjectPath) -> FileName:
    """The name a picture is kept under in the story's folder: what took it, then its place in the tests' folder."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", relative.value.replace("\\", "/").replace("/", "-")).strip(".-")
    return FileName(f"{ShotTaker.of(key).value}-{stem}")


def taken_since(started: Instant, origin: RunOrigin) -> Instant:
    """From when a picture counts as taken by the run a step read: its own start, or for a reused run the window
    before the step in which that run was made."""
    return Instant(started.value - REUSED_WITHIN) if origin is RunOrigin.REUSED else started


def taken_by_the_run(name: FileName, head: bytes, size: ByteSize, written: Instant, since: Instant) -> bool:
    """Whether a file in the tests' picture folder is a picture this run took: a picture by its content, at most
    `MAX_BYTES`, not older than the run."""
    kind = kind_of(head, name)
    return written.value >= since.value - SLACK and size.value <= MAX_BYTES and bool(kind and kind.picture)


class TakenFile(Value):
    """A file in the tests' picture folder: where it lies beneath it, its name, its first bytes, its size, when it was
    written."""

    relative: ProjectPath
    name: FileName
    head: FileBytes
    size: ByteSize
    written: Instant


def kept(files: typing.Iterable[TakenFile], since: Instant) -> typing.List[TakenFile]:
    """The pictures of a run brought to the story's place: those it took, newest first, at most `SHOWN`."""
    taken = [f for f in files if taken_by_the_run(f.name, f.head.value, f.size, f.written, since)]
    return sorted(taken, key=lambda f: -f.written.value)[:SHOWN]


class Shot(Value):
    """One picture on the story's place: where it is in the project, its name, what took it (its name up to the
    first `-`) and when."""

    path: ProjectPath
    name: FileName
    taker: ShotTaker
    at: Moment

    @staticmethod
    def of(path: ProjectPath, name: FileName, at: Moment) -> "Shot":
        return Shot(path, name, ShotTaker(name.value.split("-", 1)[0] if "-" in name.value else ""), at)


class FoundShot(Value):
    """What a story's picture folder holds of one file: its shot, when it was written, its first bytes."""

    shot: Shot
    written: Instant
    head: FileBytes


def shown(found: typing.Iterable[FoundShot]) -> typing.List[Shot]:
    """The pictures a story shows: pictures only, newest first, at most `SHOWN`."""
    def picture(f: FoundShot) -> bool:
        kind = kind_of(f.head.value, f.shot.name)
        return bool(kind and kind.picture)
    return [f.shot for f in sorted(filter(picture, found), key=lambda f: -f.written.value)[:SHOWN]]
