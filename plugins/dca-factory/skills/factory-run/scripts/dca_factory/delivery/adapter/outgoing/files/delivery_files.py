"""What a delivery rests on, as files: the production code and the events it declares, the paths a document names, the
plan's proposed terms and the glossaries, the review perspectives, the installed pipeline."""

from __future__ import annotations

import os
import re
import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import runs_top


def glossary_files(cwd: str, profile: typing.Mapping[str, typing.Any]) -> typing.List[str]:
    named = profile.get("glossary")
    if named:
        matches = [
            os.path.join(root, f)
            for root, _dirs, files in os.walk(cwd)
            for f in files
            if os.path.join(root, f).endswith(named)
        ]
        if matches:
            return matches
    found: typing.List[str] = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in ("build", "out", "bin", "obj", "target", "node_modules", ".git")]
        found += [os.path.join(root, f) for f in files if f.lower() == "glossary.md"]
    return found


def proposal_words(term: str) -> typing.Set[str]:
    """The words the gate looks for in a glossary for one proposed term: the term as written, the domain
    word before a parenthesis and the code word inside it — `Titel (title)` is found by `titel` or by
    `title`. Case does not count."""
    term = term.strip().strip("`*").lower()
    words = {term}
    match = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", term)
    if match:
        words |= {match.group(1).strip(), match.group(2).strip()}
    return {w for w in words if w}


def plan_proposals(plan: str) -> typing.List[str]:
    """The terms a plan proposes under `## Glossary proposals`: the part before the colon of each list item."""
    proposals: typing.List[str] = []
    collecting = False
    for line in plan.splitlines():
        if line.strip().lower().startswith("## glossary proposals"):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if collecting and line.strip().startswith("-") and ":" in line:
            proposals.append(line.strip()[1:].split(":", 1)[0].strip().strip("`*"))
    return proposals


#: A source file of the project's code: the gate reads no profile key for where the code lives, so it reads every
#: file with a code extension outside the build's and the tools' folders and outside the tests.
CODE_FILE = re.compile(r"\.(java|kt|scala|groovy|cs|fs|py|ts|tsx|js|jsx|mjs|go|rb|php|rs|swift)$")


#: A test folder by name — `test`, `tests`, `test-utils`, `Foo.Tests`, and the camel-cased source set a build tool
#: names (`integrationTest`, `functionalTests`): a capital T after a lowercase letter, so `latest` and `contest` are not.
TEST_DIR = re.compile(r"(?i:^(tests?|specs?|__tests__)$|^tests?[-_.]|[-_.]tests?$)|[a-z]Tests?$")


#: A line that names a type without using it: an import, a using, a package or namespace line.
IMPORT_LINE = re.compile(r"^\s*(?:import|using|package|namespace|from\s+\S+\s+import)\b.*$", re.M)


def production_files(cwd: str) -> typing.List[str]:
    found: typing.List[str] = []
    skipped = SKIP_DIRS | {runs_top()}
    for root, dirs, files in os.walk(cwd):
        dirs[:] = sorted(d for d in dirs if d not in skipped and not d.startswith(".") and not TEST_DIR.search(d))
        for name in sorted(files):
            if CODE_FILE.search(name) and not TEST_FILE.search(name):
                found.append(os.path.relpath(os.path.join(root, name), cwd).replace(os.sep, "/"))
    return found


#: A review report carries its findings under these ranks (the review skills' own format).
REVIEW_RANKS = ("must-fix", "should-fix", "nit")


#: A markdown table row, split into its cells. The first cell names the thing, the **last**
#: names how it was checked — the tables differ in width, so counting from the left is wrong.
PATHLIKE = re.compile(r"`([\w./-]+\.[A-Za-z0-9]{1,6}(?::L?\d+(?:[-–:]\d+)?|#[\w.-]+)?)`")


TEST_FILE = re.compile(
    r"(^test_.*\.py$|_test\.(py|go|rb|exs?)$|Tests?\.(java|kt|cs|scala|groovy)$|IT\.(java|kt)$"
    r"|Spec\.(scala|groovy|kt)$|\.(test|spec)\.(js|jsx|ts|tsx|mjs)$|_spec\.rb$)")


SKIP_DIRS = {".git", "build", "target", "bin", "obj", "node_modules", "dist", ".gradle",
             ".agents", ".claude", ".codex", ".opencode", "__pycache__", ".venv", "venv"}


# The runner snapshots the working tree before and after every stage (path and sha256 of every file
# git reports as differing from HEAD, untracked ones included, and `deleted` for a tracked file that is
# gone). What a stage changed follows from two snapshots and the list of tracked files,
# deterministically. What the whole story changed follows from two git trees: the one recorded at the
# story's first stage, written without committing anything, and the working tree now — so a project
# without a commit, where `git diff` has nothing to compare against, still gets its diff, and a stage
# run again does not move the story's starting point. Both are written as files the next stage reads
# first, instead of reconstructing them. Paths are relative to the project, which may be a directory
# inside a larger repository.
#: The installed pipeline: every stage reads it, `factory.sh setup` and `update` alone change it. A stage's change
#: there is not hidden as the pipeline's own — it is refused (`pipeline`), because it is the gate judging itself.
PIPELINE_DIR = ".agents/factory/"
