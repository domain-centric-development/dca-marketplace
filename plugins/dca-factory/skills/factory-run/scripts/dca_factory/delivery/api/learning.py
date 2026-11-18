"""What learning may ask delivery, in delivery's published terms, as plain data: each story's findings with their class,
its answered assumptions, its gate refusals; the decision records — a stage's tag, an acceptance's correction code —;
the lesson records; and the one write: a lesson record filed in the decision inbox. Delivery knows no lesson's meaning:
it files the text learning hands it and keeps the answer."""

from __future__ import annotations

import os
import re
import typing

from ...contract import CONTRACT, VERSION
from ...sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from ...sharedkernel.adapter.outgoing.markdown.sections import section_of
from ...sharedkernel.adapter.outgoing.profile.profile_files import place, shown
from ..adapter.outgoing.files.decision_record_files import (
    decision_files, decision_state, is_lesson, project_decision_files, project_decisions_dir, record_of)
from ..adapter.outgoing.files.findings_files import findings_path, findings_rows, row_class
from ..adapter.outgoing.files.journal_files import journal_events
from ..adapter.outgoing.files.status_facts import correction_code
from ..adapter.outgoing.files.story_layout import story_files, story_id_of
from ..application.shared.front import is_acceptance
from ..domain.model.decision_record import DecisionState
from ..domain.model.question_tag import QuestionTag
from ..domain.model.story import Assumption
from ..domain.model.story_words import Detail

Published = typing.Dict[str, typing.Any]

#: A lesson record's kind in the decision inbox (`kind: lesson`).
LESSON_KIND = "lesson"


def stories(cwd: str, epics: typing.Optional[str] = None) -> typing.List[Published]:
    """Every story that reads: {id, context, answered, findings, refusals}. `answered` the text of each answered
    assumption after `answered:`, a wrapped line read whole, the factory's own process marks and the answers to a
    question about the pipeline (`tag: pipeline`, the record the line cites) left out; `findings` each row of its findings.md —
    {n, perspective, defect, outcome, target, type, qualifier}, the class only where all three are of delivery's lists;
    `refusals` each check a gate refused it on, from its journal — {stage, check}."""
    folder = epics or os.path.join(cwd, place("epics"))
    about_pipeline: typing.Dict[str, typing.Set[str]] = {}
    for record in records(cwd, epics):
        if record["tag"] == QuestionTag.PIPELINE.value:
            about_pipeline.setdefault(record["story"], set()).add(record["id"])
    runs = place("runs")
    runs = runs if os.path.isabs(runs) else os.path.join(cwd, runs)
    found = []
    for path in story_files(folder):
        try:
            front, body = read_front_matter(path)
        except MarkdownError:
            continue
        story = story_id_of(path, front)
        answered = []
        for item in assumption_items(section_of(body, "assumptions") or []):
            text = item.lstrip("-*").strip()
            if not text or Assumption(item).marks_process or not text.lower().startswith("answered:"):
                continue
            said = text[len("answered:"):].strip()
            if not cites(said, about_pipeline.get(story, set())):
                answered.append(said)
        rows = []
        for row in findings_rows(findings_path(path)):
            kind = row_class(row)
            rows.append(dict(n=row[0], perspective=row[1], defect=row[4], outcome=row[9],
                             target=kind.target.value if kind else "", type=kind.type.value if kind else "",
                             qualifier=kind.qualifier.value if kind else ""))
        refusals = []
        for event in journal_events(runs, story):
            fields = event.get("fields", {})
            if event.get("kind") == "gate" and fields.get("exit") == "1":
                refusals += [dict(stage=event.get("name", ""), check=c.strip())
                             for c in str(fields.get("fail", "")).split(",") if c.strip()]
        found.append(dict(id=story, context=str(front.get("context", "")).strip() or "-", answered=answered,
                          findings=rows, refusals=refusals))
    return found


def cites(said: str, records_: typing.Set[str]) -> bool:
    """Whether an answered line names one of <records_> in the parenthesis it ends with — the gate writes
    `(<record id>)`."""
    match = re.search(r"\(([^()]*)\)\s*\.?\s*$", said)
    return bool(match) and any(re.search(rf"(?<![\w-]){re.escape(r)}(?![\w-])", match.group(1)) for r in records_)


def assumption_items(lines: typing.Sequence[str]) -> typing.List[str]:
    """The items of an `## Assumptions` section, each one line: an item opens with `-` or `*` and runs on through
    the indented lines below it."""
    items: typing.List[str] = []
    for line in lines:
        said = line.strip()
        if not said:
            continue
        if said[0] in "-*" or not items:
            items.append(said)
        else:
            items[-1] += " " + said
    return items


def records(cwd: str, epics: typing.Optional[str] = None) -> typing.List[Published]:
    """Every decision record of a story, a request's left out: {id, story, acceptance, tag, correction} — `tag` the
    stage's question tag where it is one of delivery's list, `correction` an answered acceptance's reason code."""
    found = []
    for name, front, body, state, error, _path in decision_files(cwd, epics):
        story = str(front.get("story", "")).strip() if not error else ""
        if not story or str(front.get("request", "")).strip():
            continue
        acceptance = is_acceptance(front)
        code = correction_code(decision_state(body)[1].get("answer")) \
            if acceptance and DecisionState(state).answered else None
        tag = QuestionTag.written(Detail(str(front.get("tag", "") or ""))) if not acceptance else None
        found.append(dict(id=str(front.get("id", name)).strip(), story=story, acceptance=acceptance,
                          tag=tag.value if tag else "", correction=code if code and code != "uncoded" else ""))
    return found


def lessons(cwd: str) -> typing.List[Published]:
    """Every lesson record of the project: {id, lesson, key, stories, answer} — `answer` the answer's first line where
    a person answered it, else None; `lesson`, `key` and `stories` as its front matter says them."""
    found = []
    for name, front, body, state, error, _path in project_decision_files(cwd):
        if error or not is_lesson(front):
            continue
        said = record_of(name, front, body, state, decision_state(body)[1]).answer_sentence()
        found.append(dict(id=str(front.get("id", name)).strip(), lesson=str(front.get("lesson", "")).strip().lower(),
                          key=str(front.get("key", "")), stories=str(front.get("stories", "0")).strip(),
                          answer=said.value if said is not None else None))
    return found


def lesson_taken(cwd: str, record: str) -> bool:
    """Whether a decision record of the project's own by this id exists."""
    return os.path.exists(os.path.join(cwd, project_decisions_dir(), record + ".md"))


def withdraw_lesson(cwd: str, record: str) -> None:
    """Remove a lesson record of the project's own that nobody answered; an answered one stays, as history."""
    for name, front, body, state, error, path in project_decision_files(cwd):
        if error or not is_lesson(front) or str(front.get("id", name)).strip() != record:
            continue
        if record_of(name, front, body, state, decision_state(body)[1]).answer_sentence() is None:
            os.remove(path)


def ask_lesson(cwd: str, record: str, text: str) -> str:
    """File a lesson record in the decision inbox, as the project's own record `<id>.md`, never over one; where, as a
    person reads it."""
    path = os.path.join(cwd, project_decisions_dir(), record + ".md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        handle.write(text)
    return shown(path)


def pipeline() -> str:
    """The pipeline that saw it: `dca-factory <version>, contract <n>`."""
    return f"dca-factory {VERSION}, contract {CONTRACT}"
