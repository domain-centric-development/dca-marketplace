"""The tests table and the tests it names, as files: the table read, each test located in the project's sources, the
plan's levels, the hand-overs' own bytes."""

from __future__ import annotations

import os
import re
import typing

from .hand_over_patterns import CRITERION, MAPPING_ROW, SELECTOR
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ....domain.model.stage_story import (
    CommandKey, MappedTest, Place, ScenarioKey, Selector, TestLocation, TitleCheck, TitleFound)
from ....domain.model.story_state import Detail
from ..stack.commands import command_for
from ..stack.test_reports import display_name_of, unescape_literal

Mapping = typing.Dict[str, typing.List[str]]


def plan_text(runs: str, story_id: str) -> str:
    path = os.path.join(runs, story_id, "plan.md")
    return read_text(path) if os.path.isfile(path) else ""


def plan_levels(runs: str, story_id: str) -> typing.Set[str]:
    """The keys the plan gave `browser-only` — a `Then` only a browser can observe, with its reason."""
    return {m.group(1) for m in re.finditer(r"^\s*-\s+([a-z0-9][a-z0-9-]*)\b[^\n]*level:\s*browser-only",
                                            plan_text(runs, story_id), re.M)}


def unfinished_levels(runs: str, story_id: str) -> typing.List[str]:
    """The keys the skeleton's plan lines still give no level."""
    return [m.group(1) for m in re.finditer(r"^\s*-\s+([a-z0-9][a-z0-9-]*)\s+→\s+level:\s*$",
                                            plan_text(runs, story_id), re.M)]


def read_mapping(runs: str, story_id: str) -> typing.Tuple[str, Mapping]:
    """criterion key -> list of test selectors, from the gate:tests table."""
    path = os.path.join(runs, story_id, "tests.md")
    text = read_text(path)
    if "<!-- gate:tests -->" not in text:
        raise GateError(
            f"{path}: no `<!-- gate:tests -->` table — the test stage records one row "
            f"per acceptance criterion: | <criterion key> | <Class>#<method> |"
        )
    mapping: Mapping = {}
    for line in text.split("<!-- gate:tests -->", 1)[1].splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        row = MAPPING_ROW.match(stripped)
        if not row:
            continue
        key, selector = row.group(1), row.group(2).strip()
        if key in ("criterion", "---"):
            continue
        if not SELECTOR.match(selector):
            raise GateError(
                f"{path}: test selector {selector!r} is not `<Class>#<method>` "
                f"(fully qualified class, then the test method)"
            )
        mapping.setdefault(key, []).append(selector)
    return path, mapping


def in_package(paths: typing.List[str], cls: str) -> typing.List[str]:
    """The files that hold `cls` itself: where the selector names a package or namespace, a file of that
    simple name declaring another one is a different class — `a.WidgetTest` is not `b.WidgetTest`."""
    if "." not in cls:
        return paths
    wanted = cls.rsplit(".", 1)[0]
    declared: typing.Dict[str, typing.Optional[str]] = {}
    for path in paths:
        match = re.search(r"^\s*(?:package|namespace)\s+([\w.]+)", read_text(path) if os.path.isfile(path) else "", re.M)
        declared[path] = match.group(1) if match else None
    if not any(declared.values()):
        return paths                          # nothing declares a package: a module path, or a stack without one
    return [path for path in paths if declared[path] == wanted
            or (declared[path] is None and wanted.replace(".", "/") in path.replace(os.sep, "/"))]


def contains(path: str, needle: str) -> bool:
    """Whether a source file mentions the identifier. Unreadable (binary) files do not."""
    try:
        with open(path, encoding="utf-8") as handle:
            return needle in handle.read()
    except (UnicodeDecodeError, OSError):
        return False


def module_files(by_path: typing.Mapping[str, typing.List[str]], cls: str, method: str) -> typing.List[str]:
    """The files a dotted class part names as a module path, longest prefix first.

    `a.b.C` is tried as the file `a/b/C.*`, then `a/b.*` holding `C`, then `a.*` holding `b` and
    `C` — each as a path suffix of some source file, never as a bare basename. The remaining
    segments and the method must all appear in the file, so a module that has the function but not
    the class it is claimed to sit in is not a match either.
    """
    segments = cls.split(".")
    for cut in range(len(segments), 0, -1):
        prefix, rest = "/".join(segments[:cut]), segments[cut:]
        hits = [path for stem, paths in by_path.items()
                if stem == prefix or stem.endswith("/" + prefix)
                for path in paths]
        found = [path for path in hits
                 if all(contains(path, name) for name in rest) and contains(path, method)]
        if found:
            return found
    return []


def locate_tests(cwd: str, mapping: typing.Mapping[str, typing.Sequence[str]]
                 ) -> typing.Tuple[typing.Dict[str, str], typing.Tuple[TestLocation, ...]]:
    """Each mapped test looked for in the project's sources: {selector: file} for the ones found, and where each
    was looked for.

    Two shapes resolve a selector's class part to a file, and both are strict about it:

    * **a file named after the class** — `com.example.WidgetTest#shows` lives in `WidgetTest.java`
      wherever that file is. JUnit, xUnit, NUnit, MSTest, Kotlin: one class per file.
    * **a file named by the module path** — `tests.test_widgets#test_shows` lives in
      `tests/test_widgets.py`, and `tests.test_widgets.TestWidgets#test_shows` in the same file.
      The class part is read as a dotted path; the longest prefix that *is* a file (by path, not by
      basename) is the module, and every remaining segment must be declared in it. pytest, and any
      stack whose tests are functions in a module.

    A basename that happens to match elsewhere never counts for the second shape: `com.example`
    would have to exist as `com/example.<ext>`, which is what keeps a Java class in a file not
    named after it *not found*.
    """
    sources: typing.Dict[str, typing.List[str]] = {}
    by_path: typing.Dict[str, typing.List[str]] = {}
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in ("build", "out", "bin", "obj", "target", "node_modules", ".git")]
        for name in files:
            full = os.path.join(root, name)
            sources.setdefault(os.path.splitext(name)[0], []).append(full)
            stem = os.path.splitext(os.path.relpath(full, cwd))[0].replace(os.sep, "/")
            by_path.setdefault(stem, []).append(full)
    located: typing.Dict[str, str] = {}
    looked = []
    for key, selectors in sorted(mapping.items()):
        for selector in selectors:
            match = SELECTOR.match(selector)
            assert match is not None, selector
            cls, method = match.groups()
            candidates = in_package(sources.get(cls.rsplit(".", 1)[-1], []), cls)
            found = [path for path in candidates if contains(path, method)]
            shape = "a file named after the class"
            if not found and not candidates:
                found = module_files(by_path, cls, method)
                shape = "the module path"
            if found:
                # with `/` on every platform: the changed-files records and the hand-overs name paths that way
                located[selector] = os.path.relpath(found[0], cwd).replace(os.sep, "/")
            looked.append(TestLocation(
                ScenarioKey(key), Selector(selector), Place(located[selector]) if found else None,
                Place(os.path.relpath(candidates[0], cwd)) if candidates and not found else None, Detail(shape)))
    return located, tuple(looked)


#: Sections the pipeline writes into a hand-over; their bytes are not the stage's and do not count against
#: its measure — a skeleton's `## Paths` alone ran to 1.5 kB in the bench.
PIPELINE_SECTIONS = {"document.md": ("## Paths",)}


def stage_bytes(path: str, name: str) -> int:
    """The bytes of a hand-over that the stage wrote: the file without the sections the pipeline put there."""
    text = read_text(path)
    for heading in PIPELINE_SECTIONS.get(name, ()):
        start = text.find("\n" + heading)
        if start < 0:
            continue
        end = text.find("\n## ", start + 1)
        text = text[:start] + (text[end:] if end >= 0 else "")
    return len(text.encode("utf-8"))


TITLE_LINE = re.compile(r"^Title:\s*(\S.*?)\s*$")


def scenario_titles(body: str) -> typing.Dict[str, str]:
    """{key: title} for every criterion: the `Title:` line under a scenario's heading, else the key in words
    (`shows-empty-state` → "Shows empty state"). An end-user test carries it verbatim as its display name, so two
    implementations of one story name the test alike and a report names the scenario it proves."""
    section = body.split("## Acceptance criteria", 1)[-1].split("\n## ", 1)[0] if "## Acceptance criteria" in body else ""
    titles: typing.Dict[str, str] = {}
    current: typing.Optional[str] = None
    for line in section.splitlines():
        stripped = line.strip()
        heading = re.match(r"^####\s+([a-z0-9][a-z0-9-]*)", stripped)
        criterion = CRITERION.match(stripped)
        if heading:
            current = heading.group(1)
            titles[current] = current.replace("-", " ").capitalize()
        elif criterion:
            current = None
            titles[criterion.group(1)] = criterion.group(1).replace("-", " ").capitalize()
        elif current and "{{" not in stripped:   # a template placeholder names nothing
            title = TITLE_LINE.match(stripped)
            if title:
                titles[current] = title.group(1)
    return titles


def carries_title(path: str, method: str, title: str) -> bool:
    """The test is reported under the title: its display name where the declaration gives one, else a string
    literal that is the title — never the words somewhere in a comment or another test."""
    display = display_name_of(path, method)
    if display is not None:
        return display == title
    text = read_text(path) if os.path.isfile(path) else ""
    return any(unescape_literal(m.group(2)) == title
               for m in re.finditer(r"""(["'`])((?:\\.|(?!\1).)*)\1""", text))


def mapped_tests(cwd: str, profile: typing.Mapping[str, typing.Any], body: str,
                 mapping: typing.Mapping[str, typing.Sequence[str]],
                 located: typing.Mapping[str, str]) -> typing.Tuple[MappedTest, ...]:
    """The tests table's rows as the test-design checks read them: each test's file, the command that runs it, and an
    end-user test's title check."""
    titles = scenario_titles(body)
    rows = []
    for key, selectors in mapping.items():
        for selector in selectors:
            path = located.get(selector)
            command = command_for(profile, path)[0] if path else None
            title = None
            if path and command in ("e2eTest", "test.journey") and key in titles:
                carries = carries_title(os.path.join(cwd, path), selector.split("#", 1)[-1], titles[key])
                title = TitleCheck(Detail(titles[key]), TitleFound.TITLED if carries else TitleFound.UNTITLED)
            rows.append(MappedTest(ScenarioKey(key), Selector(selector), Place(path) if path else None,
                                   CommandKey(command) if command else None, title))
    return tuple(rows)


class StageTestFiles:
    """The tests table of a story under the run folder <runs>, its tests in the project <cwd>, as the profile runs
    them."""

    def __init__(self, cwd: str, runs: str, profile: typing.Mapping[str, typing.Any]) -> None:
        self._cwd = cwd
        self._runs = runs
        self._profile = profile

    def table(self, story: str) -> typing.Tuple[typing.Optional[str], Mapping, typing.Optional[str]]:
        """(the table's file, the mapping, why it cannot be read)."""
        try:
            path, mapping = read_mapping(self._runs, story)
        except GateError as error:
            return None, {}, str(error)
        return path, mapping, None

    def locate(self, mapping: typing.Mapping[str, typing.Sequence[str]]
               ) -> typing.Tuple[typing.Dict[str, str], typing.Tuple[TestLocation, ...]]:
        return locate_tests(self._cwd, mapping)

    def mapped(self, body: str, mapping: typing.Mapping[str, typing.Sequence[str]],
               located: typing.Mapping[str, str]) -> typing.Tuple[MappedTest, ...]:
        return mapped_tests(self._cwd, self._profile, body, mapping, located)
