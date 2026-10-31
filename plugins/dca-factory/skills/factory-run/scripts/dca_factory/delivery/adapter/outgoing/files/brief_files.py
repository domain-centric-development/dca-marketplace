"""A stage's brief as the runner hands it over: files in the story's evidence folder — what every stage is told once,
each stage's own beside it with the digest its hand-over names (`brief: <digest>`), so the gate sees which brief the
stage worked from."""

from __future__ import annotations

import hashlib
import os
import re
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError, read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir

BRIEF = "brief"
EVERY_STAGE = "every-stage.md"
DIGEST = ".digest"
#: the line a hand-over names its brief by, its first
NAMED = re.compile(r"^brief:\s*`?([0-9a-f]+)`?\s*$", re.M)


def brief_dir(runs: str, story: str) -> str:
    return os.path.join(evidence_dir(runs, story), BRIEF)


def digest_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def write_file(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_brief(runs: str, story: str, stage: str, text: str) -> typing.Tuple[str, str]:
    """<text> as <stage>'s brief, ending with the line its hand-over repeats; the file and the digest."""
    digest = digest_of(text)
    path = os.path.join(brief_dir(runs, story), f"{stage}.md")
    write_file(path, f"{text.rstrip()}\n\n## Your hand-over names this brief\n\nThe first line of your hand-over, "
                     f"before its heading: `brief: {digest}` — the gate refuses a hand-over that names another brief or "
                     f"none.\n")
    write_file(os.path.join(brief_dir(runs, story), f"{stage}{DIGEST}"), f"{digest}\n")
    return path, digest


def write_every_stage(runs: str, story: str, text: str) -> str:
    path = os.path.join(brief_dir(runs, story), EVERY_STAGE)
    write_file(path, text.rstrip() + "\n")
    return path


def given_digest(runs: str, story: str, stage: str) -> typing.Optional[str]:
    """The digest of the brief the runner gave <stage> — None where it gave none (a stage run by hand)."""
    path = os.path.join(brief_dir(runs, story), f"{stage}{DIGEST}")
    try:
        return read_text(path).strip() or None if os.path.isfile(path) else None
    except GateError:
        return None


def named_digest(hand_over: str) -> typing.Optional[str]:
    """The digest the hand-over at <hand_over> names on a `brief:` line — the last, should it name several —, None
    where it names none."""
    if not os.path.isfile(hand_over):
        return None
    try:
        found = NAMED.findall(read_text(hand_over))
    except GateError:
        return None
    return found[-1] if found else None
