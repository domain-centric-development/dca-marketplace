"""A break of the production code, as files: the patch a test's break is kept in, a scratch copy of the project to
apply it to, and the tests an adoption wrote itself."""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import tempfile
import typing
from .....sharedkernel.adapter.outgoing.profile.profile_files import runs_top
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ..files.design_files import BREAK_IGNORE


def copy_for_break(cwd: str, copy: str) -> None:
    """The project as a scratch copy for a break: in git the files git sees — tracked, and new ones it does not
    ignore — so a package that happens to be called `build` comes along; outside git, everything but
    the build outputs and the run folder at the project's top level."""
    listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=cwd,
                            capture_output=True)
    if listed.returncode != 0:
        top = os.path.abspath(cwd)
        ignored = BREAK_IGNORE + (runs_top(),)
        shutil.copytree(cwd, copy, symlinks=True,
                        ignore=lambda folder, names: [n for n in names if n in ignored
                                                      and (os.path.abspath(folder) == top or n in (".git", "node_modules"))])
        return
    # A story's worktree links the pipeline, the runs and the epics to the checkout's own folders; the index
    # still lists the files below such a link. The copy takes the link and nothing below it — a file copied
    # through the link would be copied onto itself.
    linked = set()
    for name in sorted({n for n in listed.stdout.decode("utf-8", "replace").split("\0") if n}):
        source, target = os.path.join(cwd, name), os.path.join(copy, name)
        parts = name.split("/")
        if any("/".join(parts[:i]) in linked for i in range(1, len(parts))):
            continue
        if not os.path.lexists(source):
            continue                          # deleted in the tree, still in the index
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if os.path.islink(source):
            os.symlink(os.readlink(source), target)
            linked.add(name)
        elif os.path.isfile(source):
            shutil.copy2(source, target)


def break_path(runs: str, story_id: str, selector: str) -> str:
    return os.path.join(runs, story_id, "breaks", selector.replace("#", "--").replace("/", "_") + ".patch")


def characterization_tests(runs: str, story_id: str) -> typing.List[str]:
    """The selectors under `## Characterization` in tests.md — the tests the adoption wrote itself."""
    text = read_text(os.path.join(runs, story_id, "tests.md")) if os.path.isfile(os.path.join(runs, story_id, "tests.md")) else ""
    section = text.split("## Characterization", 1)[1].split("\n## ", 1)[0] if "## Characterization" in text else ""
    return [m.group(1) for m in re.finditer(r"^\s*-\s+`?([\w.$]+#[\w$]+)`?", section, re.M)]


def qualify_selector(selector: str, by_selector: typing.Mapping[str, str], cwd: str) -> str:
    """A test named by its simple class (`WidgetTest#shows`) as the table names it, or with the package its file
    declares: the report the gate reads names the class in full."""
    cls, _, method = selector.partition("#")
    if "." in cls:
        return selector
    for known in by_selector:
        known_cls, _, known_method = known.partition("#")
        if known_method == method and known_cls.rsplit(".", 1)[-1] == cls:
            return known
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in BREAK_IGNORE]
        for name in files:
            if os.path.splitext(name)[0] == cls:
                package = re.search(r"^\s*(?:package|namespace)\s+([\w.]+)", read_text(os.path.join(root, name)), re.M)
                if package:
                    return f"{package.group(1)}.{cls}#{method}"
    return selector


def break_patch(runs: str, story_id: str, selector: str) -> typing.Optional[str]:
    """The break a selector has — under its full name or its simple class —, or None."""
    patch = break_path(runs, story_id, selector)
    if not os.path.isfile(patch):
        short = selector.split("#")[0].rsplit(".", 1)[-1] + "#" + selector.split("#", 1)[-1]
        patch = break_path(runs, story_id, short) if os.path.isfile(break_path(runs, story_id, short)) else patch
    return patch if os.path.isfile(patch) else None


def apply_break(copy: str, scratch: str, patch: str, reverse: bool = False) -> typing.Tuple[int, str]:
    """`git apply` of a break on the scratch copy (`-R` to take it back): (exit code, what git said). An editor on
    Windows writes the patch with CRLF, which git reads as part of each line — retried with LF."""
    args = ["git", "apply", "--whitespace=nowarn"] + (["-R"] if reverse else [])
    applied = subprocess.run(args + [os.path.abspath(patch)], cwd=copy, capture_output=True, text=True)
    with open(patch, "rb") as handle:
        raw = handle.read()
    if applied.returncode != 0 and b"\r\n" in raw:
        unix = os.path.join(scratch, "break.patch")
        with open(unix, "wb") as handle:
            handle.write(re.sub(rb"\r+\n", b"\n", raw))
        applied = subprocess.run(args + [unix], cwd=copy, capture_output=True, text=True)
    return applied.returncode, (applied.stderr or applied.stdout).strip()


@contextlib.contextmanager
def break_copy(cwd: str) -> typing.Iterator[typing.Tuple[str, str]]:
    """One scratch copy of the project for every break of a gate run (WP-148): the first break compiles it, the ones
    after it build on that. Removed afterwards; the tree is never touched."""
    scratch = tempfile.mkdtemp(prefix="dca-break-")
    try:
        copy = os.path.join(scratch, "tree")
        copy_for_break(cwd, copy)
        yield copy, scratch
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
