"""The pictures a story's end-user tests took (WP-184), on disk: listed from the story's run folder (`shots/`) and
copied there from the tests' picture folder after a test run. Which pictures count, how they are named and how many
a story shows is the domain's (`shot`); here only folders are read and files copied."""

from __future__ import annotations

import os
import shutil
import time
import typing

from ....domain.model.handed_file import ByteSize, FileBytes, FileName
from ....domain.model.moment import Moment
from ....domain.model.project_path import ProjectPath
from ....domain.model.shot import SHOTS, FoundShot, Instant, Shot, TakenFile, kept, shot_name, shown
from ....domain.model.suite_run import CommandKey


def head_of(path: str) -> bytes:
    with open(path, "rb") as file:
        return file.read(64)


def shots_of(cwd: str, runs: str, story: str) -> typing.List[Shot]:
    """A story's pictures as the domain shows them — read from `<runs>/<story>/shots/`, no link followed."""
    folder = os.path.join(runs, story, SHOTS)
    base = folder if os.path.isabs(folder) else os.path.join(cwd, folder)
    if not os.path.isdir(base) or os.path.islink(base):
        return []
    found = []
    for name in os.listdir(base):
        path = os.path.join(base, name)
        if os.path.islink(path) or not os.path.isfile(path):
            continue
        written = os.path.getmtime(path)
        at = Moment(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(written)))
        shot = Shot.of(ProjectPath(os.path.relpath(path, cwd).replace(os.sep, "/")), FileName(name), at)
        found.append(FoundShot(shot, Instant(written), FileBytes(head_of(path))))
    return shown(found)


def collect_shots(cwd: str, folder: str, story_folder: str, key: str, since: Instant) -> typing.List[str]:
    """The pictures a test command made in the profile's `screenshots:` folder, copied into the story's run folder —
    the domain decides which (`kept`) and under which name (`shot_name`). Answers the names copied."""
    source = folder if os.path.isabs(folder) else os.path.join(cwd, folder)
    if not folder or not os.path.isdir(source) or os.path.islink(source):
        return []
    files = []
    for root, dirs, names in os.walk(source):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for name in names:
            path = os.path.join(root, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            files.append(TakenFile(ProjectPath(os.path.relpath(path, source).replace(os.sep, "/")), FileName(name),
                                   FileBytes(head_of(path)), ByteSize(os.path.getsize(path)), Instant(os.path.getmtime(path))))
    target, copied = os.path.join(story_folder, SHOTS), []
    for taken in kept(files, since):
        kept_as = shot_name(CommandKey(key), taken.relative)
        os.makedirs(target, exist_ok=True)
        shutil.copy2(os.path.join(source, taken.relative.value), os.path.join(target, kept_as.value))
        copied.append(kept_as.value)
    return copied
