"""Git as the factory runs it: UTF-8 always, an answer on stdout alone where git succeeds, a blob exactly as git
holds it, a committer where the repository names none."""

from __future__ import annotations

import subprocess
import typing


def git(cwd: str, *args: str, env: typing.Optional[typing.Mapping[str, str]] = None) -> typing.Tuple[int, str]:
    try:
        # UTF-8, not the locale: on Windows a cp1252 reading turns an umlaut into another character (a
        # test that did not change looks changed) and raises on bytes like 0x81.
        completed = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env,
                                   encoding="utf-8", errors="replace")
    except OSError as error:
        return 1, str(error)
    # A success answers on stdout alone: git warns on stderr while it succeeds — on Windows "LF will be replaced by
    # CRLF" beside the hash of `hash-object` — and a warning read as the answer is a blob that does not exist.
    if completed.returncode == 0:
        return 0, completed.stdout.strip()
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def git_blob(cwd: str, spec: str) -> typing.Tuple[int, str]:
    """(code, text) of one object — `<blob hash>` or `<ref>:<path>` — exactly as git holds it. `git` strips its
    answer, which would take a first line's indentation with it; a file's content is read here, never there."""
    try:
        completed = subprocess.run(["git", "cat-file", "blob", spec], cwd=cwd, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace")
    except OSError as error:
        return 1, str(error)
    if completed.returncode == 0:
        return 0, completed.stdout
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def git_identity(cwd: str) -> typing.List[str]:
    """`-c user.name=… -c user.email=…` where the repository names no committer — a factory commit must not
    fail on a machine that never committed."""
    if git(cwd, "config", "user.email")[1].strip():
        return []
    return ["-c", "user.name=dca-factory", "-c", "user.email=dca-factory@localhost"]
