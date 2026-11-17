"""The findings files read for their classes (WP-223): the rows without one, and what a `classify-findings` request
may change in them — the three empty class cells, each from the lists or `—`, and the front matter's `classes:` line."""

from __future__ import annotations

import os
import re
import subprocess
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import findings_dir, place
from ....application.shared.finding_classes import ClassFill, UnclassedFindings
from ....domain.model.finding_class import FindingClass
from ....domain.model.story_words import Count, Detail
from .findings_files import FINDINGS_FILE, findings_cells, findings_path, findings_rows, row_class, widen_findings
from .story_layout import story_files

#: What a classifier writes where no value of a list fits.
NONE_FITS = "—"
#: The front matter line a classified file carries.
MARK = re.compile(r"^classes:\s")


def findings_files(cwd: str) -> typing.List[str]:
    """Every findings file of the project: the stories' and the project's own."""
    epics = place("epics")
    epics = epics if os.path.isabs(epics) else os.path.join(cwd, epics)
    found = [findings_path(path) for path in story_files(epics)]
    project = findings_dir()
    project = project if os.path.isabs(project) else os.path.join(cwd, project)
    if os.path.isdir(project):
        found += [os.path.join(project, name) for name in sorted(os.listdir(project)) if name.endswith(".md")]
    return [path for path in found if os.path.isfile(path)]


def classed(row: typing.Sequence[str]) -> bool:
    """A findings row (as `findings_rows` reads it) with a listed class."""
    return row_class(row) is not None


def none_fits(word: str) -> bool:
    """A class cell that says no value of its list fits."""
    return word.strip() == NONE_FITS


def class_problems(before: str, after: str) -> typing.List[str]:
    """What <after> changes beyond filling the class cells of rows <before> had none in, from the lists or `—`, and
    the `classes:` line of its front matter."""
    problems: typing.List[str] = []
    old_lines, new_lines = widen_findings(before).splitlines(), after.splitlines()   # an older row in today's shape
    old_rows = [cells for cells in (findings_cells(line) for line in old_lines) if cells is not None]
    new_rows = [cells for cells in (findings_cells(line) for line in new_lines) if cells is not None]
    if len(old_rows) != len(new_rows):
        return [f"{len(old_rows)} rows before, {len(new_rows)} after — no row is added or removed"]
    for old, new in zip(old_rows, new_rows):
        wide_old = old
        if len(new) != 13 or len(wide_old) != 13:
            problems.append(f"row {old[0]}: a findings row of today's shape has 13 cells")
            continue
        if new[:10] != wide_old[:10]:
            problems.append(f"row {old[0]}: a cell other than the class changed")
            continue
        if any(wide_old[10:13]) and new[10:13] != wide_old[10:13]:
            problems.append(f"row {old[0]}: its class was there and changed")
            continue
        words = new[10:13]
        if not (FindingClass.written(Detail(words[0]), Detail(words[1]), Detail(words[2])) is not None
                or all(none_fits(w) for w in words)):
            problems.append(f"row {old[0]}: {' · '.join(words)} — each from its list, or `—` in all three where none fits")
    rest = lambda lines: [line for line in lines if findings_cells(line) is None and not MARK.match(line)
                          and not set(line.strip()) <= set("|-: ") and not line.startswith("| # |")]
    if rest(old_lines) != rest(new_lines):
        problems.append("a line other than a row's class cells and the `classes:` mark changed")
    return problems


class FindingClassFiles(UnclassedFindings, ClassFill):
    """The findings files of the project <cwd>."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def count(self) -> Count:
        return Count(sum(1 for path in findings_files(self._cwd) for row in findings_rows(path) if not classed(row)))

    def _head(self, path: str) -> typing.Optional[str]:
        relative = os.path.relpath(os.path.join(self._cwd, path), self._cwd)
        done = subprocess.run(["git", "show", f"HEAD:./{relative}"], cwd=self._cwd, capture_output=True)
        return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None

    def refused(self, paths: typing.Sequence[str]) -> typing.Optional[Detail]:
        for path in paths:
            if os.path.basename(path) != FINDINGS_FILE and os.path.dirname(os.path.join(self._cwd, path)) != \
                    os.path.join(self._cwd, findings_dir()):
                return Detail(f"{path}: a classify-findings request writes findings files alone")
            before = self._head(path)
            if before is None:
                return Detail(f"{path}: no findings file of the last commit — a request classifies, it adds none")
            problems = class_problems(before, read_text(os.path.join(self._cwd, path)))
            if problems:
                return Detail(f"{path}: {'; '.join(problems[:3])}")
        return None

    def restore(self, paths: typing.Sequence[str]) -> None:
        for path in paths:
            subprocess.run(["git", "checkout", "HEAD", "--", path], cwd=self._cwd, capture_output=True)
