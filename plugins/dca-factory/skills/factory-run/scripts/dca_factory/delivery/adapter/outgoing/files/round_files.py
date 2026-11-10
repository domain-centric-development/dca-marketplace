"""A story's rounds as files: the refusals and fresh restarts its journal keeps, the round record `rounds.md` beside
the round counter — written by the runner, a list, never a log —, the mark of a fresh restart and the hand-overs it
set aside."""

from __future__ import annotations

import contextlib
import os
import time
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from ....domain.model.refusal_history import FreshRestart, GateRefusal, RefusalHistory
from ....domain.model.stage import StageName
from ....domain.model.story_words import Selector
from ....domain.model.verdict import CheckName
from .journal_files import journal_events
from .run_marks import last_ended

#: The round record, beside the round counter in the story's evidence.
ROUNDS_RECORD = "rounds.md"
#: The mark a fresh restart leaves for the stage it restarts: the stage's name.
FRESH_MARK = ".fresh"
#: Where a fresh restart sets the earlier attempt's hand-over aside.
ATTEMPTS = "attempts"
#: How many changed files a round's line names at most.
CHANGED_SHOWN = 12


def _names(value: str) -> typing.List[str]:
    return [name for name in value.split(",") if name]


def refusal_history(runs: str, story_id: str) -> RefusalHistory:
    """The refused gates the runner ran (`by=runner`) and the fresh restarts, since the last `rounds-reset`."""
    entries: typing.List[typing.Union[GateRefusal, FreshRestart]] = []
    for event in journal_events(runs, story_id):
        fields = event["fields"]
        if event["kind"] == "rounds-reset":
            entries = []
        elif event["kind"] == "gate" and fields.get("exit") == "1" and fields.get("by") == "runner":
            entries.append(GateRefusal(StageName(event["name"]),
                                       frozenset(CheckName(c) for c in _names(fields.get("fail", ""))),
                                       frozenset(Selector(t) for t in _names(fields.get("tests", "")))))
        elif event["kind"] == "fresh":
            entries.append(FreshRestart(StageName(event["name"])))
    return RefusalHistory(tuple(entries))


def account(hand_over: str) -> str:
    """The one line a hand-over gives of itself: its first line of prose — no heading, table, list, field or fence."""
    if not os.path.isfile(hand_over):
        return ""
    for line in read_text(hand_over).splitlines():
        text = line.strip()
        if not text or text.startswith(("#", "|", "-", "*", "```", ">", "<!--")) or text.lower().startswith("brief:"):
            continue
        return text[:200]
    return ""


def changed_by(runs: str, story_id: str, stage: str) -> typing.List[str]:
    """The files the stage's window changed, from its changed-files record — the shared builder's where it ran last."""
    folder = evidence_dir(runs, story_id)
    name = "builder" if last_ended(runs, story_id, (stage, "builder")) == "builder" else stage
    record = os.path.join(folder, f"changed-{name}.txt")
    if not os.path.isfile(record):
        return []
    return [line.split("\t", 1)[1].strip() for line in read_text(record).splitlines() if "\t" in line]


def record_round(runs: str, story_id: str, stage: str, hand_over: str) -> None:
    """One line in the story's round record for the refusal its journal kept last: the stage, the failed checks, the
    failing tests, the files the stage changed and the one line its hand-over gives."""
    refusal = next((e for e in reversed(refusal_history(runs, story_id).entries) if isinstance(e, GateRefusal)), None)
    path = os.path.join(evidence_dir(runs, story_id), ROUNDS_RECORD)
    lines = read_text(path).splitlines() if os.path.isfile(path) else [
        f"# Rounds — {story_id}", "", "Written by the runner, one line a refused round: the stage, what failed, what "
        "the attempt changed, what its hand-over said.", ""]
    rounds = sum(1 for line in lines if line.startswith("- round "))
    checks = ", ".join(sorted(c.value for c in refusal.checks)) if refusal else "?"
    tests = ", ".join(sorted(t.value for t in refusal.tests)) if refusal and refusal.tests else "none named"
    changed = changed_by(runs, story_id, stage)
    shown = ", ".join(changed[:CHANGED_SHOWN]) + (" …" if len(changed) > CHANGED_SHOWN else "") if changed else "none"
    said = account(hand_over) or "—"
    lines.append(f"- round {rounds + 1} · {stage} · failed: {checks} · tests: {tests} · changed: {shown} · said: {said}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def mark_fresh(runs: str, story_id: str, stage: str, hand_over: str) -> None:
    """The next round at <stage> starts fresh: the mark, and the stage's earlier hand-over set aside under
    `attempts/`, so the stage reads the story, the plan, the gate's report and the round record instead."""
    folder = evidence_dir(runs, story_id)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, FRESH_MARK), "w", encoding="utf-8") as handle:
        handle.write(stage + "\n")
    if os.path.isfile(hand_over):
        aside = os.path.join(folder, ATTEMPTS)
        os.makedirs(aside, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        with contextlib.suppress(OSError):
            os.replace(hand_over, os.path.join(aside, f"{stamp}-{os.path.basename(hand_over)}"))


def fresh_stage(runs: str, story_id: str) -> typing.Optional[str]:
    """The stage a fresh restart waits to start — None where none does."""
    path = os.path.join(evidence_dir(runs, story_id), FRESH_MARK)
    return read_text(path).strip() or None if os.path.isfile(path) else None


def clear_fresh(runs: str, story_id: str) -> None:
    """The fresh restart started: its mark goes."""
    with contextlib.suppress(OSError):
        os.remove(os.path.join(evidence_dir(runs, story_id), FRESH_MARK))
