"""What a run reads from a project's files the way the gate does: a story's verdict, a stage file's needs-human
section, the decision records still open beside a story."""

from __future__ import annotations

import os
import re
import typing
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.profile.profile_files import place, shown
from .decision_record_files import decisions_store, needs_human_ids, record_path
from .story_layout import find_story
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .run_marks import verdict_in


def verdict_of_story(runs: str, story_id: str) -> str:
    path = os.path.join(runs, story_id, "judge.md")
    return verdict_in(read_text(path)) if os.path.isfile(path) else ""


def needs_human_lines(path: str, story_id: typing.Optional[str] = None) -> typing.Optional[typing.List[str]]:
    """`<id>\\t<stage>\\t<record path>` for every decision the file's needs-human section names; None when it
    asks nobody. The record lives beside the story, so the story's id says where to look."""
    ids = needs_human_ids(read_text(path)) if os.path.isfile(path) else None
    if ids is None:
        return None
    lines: typing.List[str] = []
    for decision_id in ids:
        record, stage = "", ""
        try:
            record = record_path(story_id, decision_id) if story_id else ""
        except GateError:
            record = ""
        if record and os.path.isfile(record):
            try:
                stage = str(read_front_matter(record)[0].get("stage", "") or "")
            except GateError:
                stage = ""
        lines.append(f"{decision_id}\t{stage or '-'}\t{shown(record) if record else '-'}")
    return lines


def open_decision_files(cwd: str, story_id: str) -> typing.List[str]:
    """The records beside the story that carry no `## Answer` yet — the cheap check a run makes
    before a stage; the gate does the fine reading (a draft without a name is still open)."""
    try:
        store = decisions_store(find_story(place("epics"), story_id))
    except GateError:
        return []
    if not os.path.isdir(store):
        return []
    found: typing.List[str] = []
    for name in sorted(os.listdir(store)):
        if not name.endswith(".md"):
            continue
        text = read_text(os.path.join(store, name))
        if not re.search(r"^## Answer", text, re.M):
            found.append(shown(os.path.join(store, name)))
    return found
