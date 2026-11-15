"""The judge's rows with their origin, from files: `judge.md`'s `## Confirmed defects` and the story's diff
(`<evidence>/<story>/story.diff`) — a row's place is introduced where the diff adds or changes that line of that file,
pre-existing where the file or the line is not in it, unresolved where the row names no line."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from .findings_files import confirmed_defects
from ....domain.model.judge_rows import JudgeRow, Origin, RoundPlace
from .diff_lines import added_lines, added_texts, changed_since, origin_of, place_of
from ....domain.model.story_state import Detail

#: The diff the previous verdict was given on, kept when that verdict sent the story back.
PREVIOUS_DIFF = ".judge-previous.diff"
PREVIOUS_VERDICT = ".judge-previous.md"


def judge_rows_of(judge_text: str, diff: typing.Optional[str], previous_text: typing.Optional[str] = None,
                  previous_diff: typing.Optional[str] = None) -> typing.Tuple[JudgeRow, ...]:
    """The judge's confirmed defects with their origin, and — from the second round on, where the previous verdict and
    its diff are kept — each row's place against that round: named before, on a line changed since, or untouched.
    Without a diff every origin is unresolved."""
    usable = diff is not None and not diff.startswith("# no diff")
    added = added_lines(diff) if usable and diff is not None else None
    now = added_texts(diff) if usable and diff is not None else {}
    second = previous_text is not None and previous_diff is not None and usable
    before = added_texts(previous_diff) if second and previous_diff is not None else {}
    named = {place_of(row[1]) for row in confirmed_defects(previous_text)} if second and previous_text else set()

    def since(where: str) -> RoundPlace:
        if not second:
            return RoundPlace.FIRST
        if place_of(where) in named:
            return RoundPlace.REPEATED
        return RoundPlace.CHANGED_SINCE if changed_since(where, now, before) else RoundPlace.UNTOUCHED
    return tuple(JudgeRow(Detail(perspective), Detail(where), Detail(severity),
                          origin_of(where, added) if added is not None else Origin.UNRESOLVED, since(where))
                 for perspective, where, severity, _defect, _fix, _plain in confirmed_defects(judge_text))


def judge_rows(runs: str, story_id: str) -> typing.Tuple[JudgeRow, ...]:
    """The rows of the story's judge.md, weighed against its diff and the round before."""
    judge = os.path.join(runs, story_id, "judge.md")
    if not os.path.isfile(judge):
        return ()
    def text(path: str) -> typing.Optional[str]:
        return read_text(path) if os.path.isfile(path) else None
    return judge_rows_of(read_text(judge), text(os.path.join(evidence_dir(runs, story_id), "story.diff")),
                         text(os.path.join(runs, story_id, PREVIOUS_VERDICT)),
                         text(os.path.join(runs, story_id, PREVIOUS_DIFF)))


def keep_judged_diff(runs: str, story_id: str) -> None:
    """Keep the diff a verdict that sent the story back was given on, for the next round to weigh against."""
    diff = os.path.join(evidence_dir(runs, story_id), "story.diff")
    if os.path.isfile(diff):
        with open(os.path.join(runs, story_id, PREVIOUS_DIFF), "w", encoding="utf-8") as handle:
            handle.write(read_text(diff))
