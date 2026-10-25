"""The tests table and the tests it names, as files: the table read, each test located in the project's sources, the
plan's levels, the hand-overs' own bytes."""

from __future__ import annotations

import os
import re
import typing

from .....contract import GateError, MAPPING_ROW, SELECTOR
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ....domain.model.stage_story import Place, ScenarioKey, Selector, TestLocation
from ....domain.model.story_state import Detail

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
