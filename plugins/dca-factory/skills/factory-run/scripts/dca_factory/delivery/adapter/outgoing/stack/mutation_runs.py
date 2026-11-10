"""How strong a story's tests are: the profile's `mutation:` run over the production files the story changed, after its
judge — `{classes}` the changed classes by their qualified names (a JVM source set's path below `java/` or `kotlin/`),
`{files}` the changed files —, and the score its output states. A measure to read, never a gate."""

from __future__ import annotations

import os
import re
import subprocess
import typing

#: Where a JVM class's qualified name starts in its path.
JVM_ROOTS = re.compile(r"(?:^|/)(?:java|kotlin|scala|groovy)/(.+)\.(?:java|kt|scala|groovy)$")

#: How the mutation tools state their score: PIT's `Killed 18 (82%)`, Stryker's `mutation score is 72.73 %`, and a
#: report's `Mutation score: 80%`.
SCORE = (re.compile(r"Killed\s+\d+\s+\((\d+(?:\.\d+)?)%\)"),
         re.compile(r"mutation score(?: is|:)?\s*(\d+(?:\.\d+)?)\s*%", re.I))


def classes_of(files: typing.Sequence[str]) -> typing.List[str]:
    """The JVM classes among <files>, by their qualified names."""
    found = []
    for path in files:
        match = JVM_ROOTS.search(path.replace(os.sep, "/"))
        if match:
            found.append(match.group(1).replace("/", "."))
    return found


def score_of(output: str) -> typing.Optional[str]:
    """The last score the output states, as written (`82`, `72.73`); None where it states none."""
    found: typing.Optional[str] = None
    for pattern in SCORE:
        for match in pattern.finditer(output):
            found = match.group(1)
    return found


def mutation_command(command: str, files: typing.Sequence[str]) -> str:
    """The profile's command with the story's classes and files put in."""
    return command.replace("{classes}", ",".join(classes_of(files))).replace("{files}", ",".join(files))


def run_mutation(command: str, cwd: str, timeout: typing.Optional[int]) -> typing.Tuple[int, str]:
    """The command through a shell, its exit and its output — a timeout is exit 124 and what it printed so far."""
    try:
        done = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout or None)
        return done.returncode, done.stdout + done.stderr
    except subprocess.TimeoutExpired as expired:
        out = expired.stdout or ""
        return 124, out if isinstance(out, str) else out.decode("utf-8", "replace")
