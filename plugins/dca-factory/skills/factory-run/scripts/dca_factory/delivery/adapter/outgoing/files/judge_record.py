"""Every verdict in the story's journal, and what became of the findings before it (WP-209).

A verdict is a `signal judge` group: its written word and the word its rows weigh it to (`verdict=`, `weighed=`), one
`finding` line a confirmed defect — severity, place, origin, place against the round before, whether it blocks, a hash
of its line's text in the diff, its class as the `Defect` cell begins — and one `outcome` line for every blocking
finding of the verdict before: repeated, fixed, dropped or overruled, computed by the domain. A verdict that sends the
story back is a line of the round record too."""

from __future__ import annotations

import hashlib
import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, place
from .decision_record_files import decisions_store, read_decisions
from .round_questions import cited_places
from .round_files import ROUNDS_RECORD
from .story_layout import find_story
from .diff_lines import added_texts, place_of
from .findings_files import append_findings, confirmed_classes, confirmed_defects, findings_path, findings_rows
from .journal_files import journal_events
from .judge_rows_files import judge_rows
from .run_marks import judged_of, verdict_in
from .signals import DOMAIN_CODE, SignalItem, journal_signal, latest_signal
from ....domain.model.judge_rows import Closure, NextSeen, outcome_of, weighed

#: How much of a defect's text a journal line keeps.
DEFECT_KEPT = 160


def place_key(where: str) -> str:
    """A place by its path and line — the same place however a row writes it."""
    found = place_of(where)
    return f"{found[0]}:{found[1]}" if found else where.strip("` ")


def line_hash(where: str, texts: typing.Mapping[str, typing.Mapping[int, str]]) -> str:
    """A short hash of the row's line as the diff carries it — empty where the diff does not carry that line."""
    found = place_of(where)
    if not found:
        return ""
    path, number = found
    for diffed, lines in texts.items():
        if diffed == path or diffed.endswith("/" + path) or path.endswith("/" + diffed):
            text = lines.get(number)
            return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8] if text is not None else ""
    return ""


def plain(text: str) -> str:
    """A cell's text for a journal field: one line, no tab, kept short."""
    return " ".join(text.replace("\t", " ").split())[:DEFECT_KEPT]


def record_verdict(runs: str, story_id: str, answered_places: typing.AbstractSet[str] = frozenset()) -> None:
    """Journal the story's verdict as it stands, once per judge.md: its rows with their origin and round place, and the
    outcome of every blocking finding of the verdict before. `answered_places` are the places a person's answered
    question cites — a finding there is overruled."""
    judge = os.path.join(runs, story_id, "judge.md")
    if not os.path.isfile(judge):
        return
    text = read_text(judge)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    events = journal_events(runs, story_id)
    previous = latest_signal(events, "judge", "finding")
    if previous and previous[0].get("sha") == sha:
        return
    diff_path = os.path.join(evidence_dir(runs, story_id), "story.diff")
    texts = added_texts(read_text(diff_path)) if os.path.isfile(diff_path) else {}
    rows = judge_rows(runs, story_id)
    cells = confirmed_defects(text)
    written = judged_of(verdict_in(text))
    items: typing.List[SignalItem] = []
    for row, (perspective, where, severity, defect, _fix, _plain), (target, kind, qualifier) in zip(
            rows, cells, confirmed_classes(text)):
        code = DOMAIN_CODE.match(defect or "")
        items.append(("finding", perspective.lower(), dict(
            severity=severity.lower(), file=where, code=code.group(1).lower() if code else "",
            origin=row.origin.value, since=row.since.value, blocks="yes" if row.blocks() else "no",
            line=line_hash(where, texts), defect=plain(defect), target=target, type=kind, qualifier=qualifier)))
    now = {place_key(row.where.value) for row in rows}
    for perspective, fields in previous[1] if previous else []:
        if fields.get("blocks") != "yes":
            continue
        key = place_key(fields.get("file", ""))
        seen = NextSeen.RAISED_AGAIN if key in now else (
            NextSeen.GONE_LINE_CHANGED if line_hash(fields.get("file", ""), texts) != fields.get("line", "")
            else NextSeen.GONE_LINE_SAME)
        closure = Closure.ANSWERED if key in answered_places else Closure.OPEN
        items.append(("outcome", perspective, dict(
            severity=fields.get("severity", ""), file=fields.get("file", ""), origin=fields.get("origin", ""),
            outcome=outcome_of(seen, closure).value, defect=fields.get("defect", ""),
            target=fields.get("target", ""), type=fields.get("type", ""), qualifier=fields.get("qualifier", ""))))
    journal_signal(runs, story_id, "judge", items, sha=sha, findings=len(rows), verdict=written.value,
                   weighed=weighed(written, rows).value)


def judge_round_line(runs: str, story_id: str) -> str:
    """The round record's line for a verdict that sent the story back: the blocking rows, each with its place and
    the class its `Defect` cell begins with."""
    blocking = [(row, cells) for row, cells in zip(judge_rows(runs, story_id),
                                                   confirmed_defects(read_text(os.path.join(runs, story_id, "judge.md"))))
                if row.blocks()]
    shown = "; ".join(f"{cells[0]} {cells[1].strip('`')} ({cells[2]}) — {plain(cells[3])[:60]}" for _row, cells in blocking)
    return f"judge · blocking: {shown or 'none named'}"


def answered_places(story_id: str) -> typing.FrozenSet[str]:
    """The places the story's answered questions cite, by path and line — a finding there a person closed."""
    try:
        store = decisions_store(find_story(place("epics"), story_id))
        records = read_decisions(store, story_id)
    except Exception:  # noqa: BLE001 — a story or a record the gate cannot read cites nothing here
        return frozenset()
    found = set()
    for _path, _front, body, state, _answer in records:
        if state in ("answered", "applied"):
            for cited in cited_places(body):
                found.add(cited)
    return frozenset(found)


def record_judge_round(runs: str, story_id: str) -> None:
    """One line in the story's round record for a verdict that sent the story back."""
    path = os.path.join(evidence_dir(runs, story_id), ROUNDS_RECORD)
    lines = read_text(path).splitlines() if os.path.isfile(path) else [
        f"# Rounds — {story_id}", "", "Written by the runner, one line a refused round: the stage, what failed, what "
        "the attempt changed, what its hand-over said.", ""]
    rounds = sum(1 for line in lines if line.startswith("- round "))
    lines.append(f"- round {rounds + 1} · {judge_round_line(runs, story_id)}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def record_outcomes(story_path: str, story_id: str, front: typing.Mapping[str, typing.Any], runs: str) -> int:
    """At delivery, every blocking finding an earlier verdict raised goes into the story's findings beside the last
    verdict's rows, with what became of it — the journal's `outcome` lines, the last one of a place deciding. Returns
    how many rows it added."""
    record_verdict(runs, story_id, answered_places(story_id))
    last: typing.Dict[str, typing.Tuple[str, typing.Dict[str, typing.Any]]] = {}
    for event in journal_events(runs, story_id):
        if event["kind"] == "outcome":
            last[place_key(event["fields"].get("file", ""))] = (event["name"], event["fields"])
    have = {place_key(row[2]) for row in findings_rows(findings_path(story_path))}
    added = [(perspective, fields.get("file", ""), fields.get("severity", ""), fields.get("defect", ""), "", "",
              fields.get("origin", ""), fields.get("outcome", ""), fields.get("target", ""), fields.get("type", ""),
              fields.get("qualifier", ""))
             for key, (perspective, fields) in sorted(last.items())
             if key not in have and fields.get("outcome") != "repeated"]
    append_findings(story_path, story_id, front, added)
    return len(added)
