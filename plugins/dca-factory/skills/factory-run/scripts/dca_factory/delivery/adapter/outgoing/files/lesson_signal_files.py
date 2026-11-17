"""The signals a lesson is counted from, as the project's files hold them — the stories' decision records and
findings, their acceptances and assumptions — and the lesson records already written."""

from __future__ import annotations

import os
import re
import typing

from .decision_record_files import decision_files, decision_state, is_lesson, project_decision_files, record_of
from .findings_files import findings_path, findings_rows
from .status_facts import correction_code
from .story_layout import story_files, story_id_of
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .....sharedkernel.adapter.outgoing.profile.profile_files import place, read_profile, resolve_profile
from ....application.shared.front import is_acceptance
from ....application.shared.lesson_signals import LessonSignals
from ....domain.model.decision_record import DecisionState
from ....domain.model.finding_class import FindingClass
from ....domain.model.lesson import (BACK_AFTER, Decided, Evidence, LessonKind, LessonPlace, OPEN_AT_ONCE, Signal,
                                     SignalKey)
from .journal_files import journal_events
from ....domain.model.question_tag import QuestionTag
from ....domain.model.story import Assumption, StoryId
from ....domain.model.story_words import Count, Detail

#: A rule id as a finding names it: two or more upper-case words and a number — `DCA-HEX-014`, `STAGE-PLAN-9B`; a
#: story id (`US-3`) is not one.
RULE_ID = re.compile(r"\b[A-Z]{2,}(?:-[A-Z]{2,})+-\d+[A-Z]?\b")
#: The domain code a judge's finding opens with (`domain-term: …`).
DOMAIN_CODE = re.compile(r"^\s*`?(domain-(?:concept|boundary|invariant|term))`?\s*:", re.I)
#: The source an answered line ends with — `(US-1-01)`, `(product/domain.md)` —: the same answer from two records is
#: the same assumption.
CITATION = re.compile(r"\s*\([^()]*\)\s*$")
#: The first word in back ticks — the term a `domain-term` finding flags.
TERM = re.compile(r"`([^`]{1,40})`")

def finding_signals(story: StoryId, row: typing.Tuple[str, ...]) -> typing.List[Signal]:
    """A finding row's signals, finest first: the rule it names under its perspective; its class (WP-221) as
    `<perspective>/<target>/<type>/<qualifier>` within `<target>/<type>`; a row without a class its domain code; and for
    a `domain-term` finding the term it flags. A finding that names none of them is counted nowhere: what is the same
    could not be told without guessing."""
    n, perspective, defect = row[0], row[1], row[4]  # by place: the row grows columns at its end (`findings_rows`)
    outcome = row[9] if len(row) > 9 else ""
    evidence = Evidence(story, Detail(f"{story.value}#{n}" + (f" ({outcome})" if outcome else "")))
    rule = RULE_ID.search(defect)
    code = DOMAIN_CODE.match(defect)
    kind = FindingClass.written(Detail(row[10]), Detail(row[11]), Detail(row[12])) if len(row) > 12 else None
    found = []
    fine, coarse = kind.keys(Detail(perspective)) if kind is not None else (None, None)
    if fine is not None and coarse is not None:
        found.append(Signal(LessonKind.FINDING, SignalKey(coarse.value), evidence))
        found.append(Signal(LessonKind.FINDING, SignalKey(fine.value), evidence, SignalKey(coarse.value)))
    if rule or (code and kind is None):
        found.append(Signal(LessonKind.FINDING, SignalKey(f"{perspective}/{rule.group(0) if rule else code.group(1)}"),  # type: ignore[union-attr]
                            evidence, SignalKey(fine.value) if fine is not None else None))
    if code and code.group(1).lower() == "domain-term":
        term = TERM.search(defect[code.end():])
        if term:
            found.append(Signal(LessonKind.TERM, SignalKey(term.group(1)), evidence))
    return found


def assumption_signals(story: StoryId, body: str) -> typing.List[Signal]:
    """The story's answered assumptions — `- answered: <the assumption and its answer>` —, each its own key."""
    found = []
    for line in section_of(body, "assumptions") or []:
        text = line.strip().lstrip("-*").strip()
        if text and Assumption(line.strip()).marks_process:
            continue
        if text.lower().startswith("answered:"):
            said = CITATION.sub("", text[len("answered:"):].strip().rstrip(".")).strip().rstrip(".")
            if said:
                found.append(Signal(LessonKind.ASSUMPTION, SignalKey(said),
                                    Evidence(story, Detail(f"{story.value} assumptions"))))
    return found


def refusal_signals(story: StoryId, events: typing.Sequence[typing.Mapping[str, typing.Any]]) -> typing.List[Signal]:
    """The checks a gate refused the story on, from its journal (`gate … exit=1 fail=<checks>`), each once — a line
    that names no check counts nowhere."""
    found: typing.Dict[str, Signal] = {}
    for event in events:
        fields = event.get("fields", {})
        if event.get("kind") != "gate" or fields.get("exit") != "1":
            continue
        for check in (c for c in str(fields.get("fail", "")).split(",") if c.strip()):
            found.setdefault(check.strip(), Signal(LessonKind.REFUSAL, SignalKey(check.strip()), Evidence(
                story, Detail(f"{story.value} journal: {event.get('name', '')} gate refused {check.strip()}"))))
    return list(found.values())


class LessonSignalFiles(LessonSignals):
    """The signals of the project <cwd>, its stories under <epics>."""

    def __init__(self, cwd: str, epics: typing.Optional[str] = None) -> None:
        self._cwd = cwd
        self._epics = epics or os.path.join(cwd, place("epics"))

    def signals(self) -> typing.Sequence[Signal]:
        found: typing.List[Signal] = []
        contexts: typing.Dict[str, str] = {}
        for path in story_files(self._epics):
            try:
                front, body = read_front_matter(path)
            except MarkdownError:
                continue
            story = StoryId(story_id_of(path, front))
            contexts[story.value] = str(front.get("context", "")).strip() or "-"
            found += assumption_signals(story, body)
            for row in findings_rows(findings_path(path)):
                found += finding_signals(story, row)
        runs = place("runs")
        runs = runs if os.path.isabs(runs) else os.path.join(self._cwd, runs)
        for story_id in sorted(contexts):
            found += refusal_signals(StoryId(story_id), journal_events(runs, story_id))
        for name, front, body, state, error, _path in decision_files(self._cwd, self._epics):
            story_word = str(front.get("story", "")).strip() if not error else ""
            if not story_word or str(front.get("request", "")).strip():
                continue
            story, rid = StoryId(story_word), Detail(str(front.get("id", name)).strip())
            if is_acceptance(front):
                code = correction_code(decision_state(body)[1].get("answer")) if DecisionState(state).answered else None
                if code and code != "uncoded":
                    found.append(Signal(LessonKind.CORRECTION, SignalKey(code), Evidence(story, rid)))
                continue
            tag = QuestionTag.written(Detail(str(front.get("tag", "") or "")))
            if tag is not None:
                found.append(Signal(LessonKind.QUESTION,
                                    SignalKey(f"{contexts.get(story_word, '-')}/{tag.value}"), Evidence(story, rid)))
        return found

    def back_after(self) -> Count:
        return self._count("lessons.backAfter", BACK_AFTER)

    def open_at_once(self) -> Count:
        return self._count("lessons.open", OPEN_AT_ONCE)

    def _count(self, key: str, default: Count) -> Count:
        said = str(read_profile(resolve_profile(None, self._cwd)).get(key) or "").strip()
        return Count(int(said)) if said.isdigit() else default

    def decided(self) -> typing.Sequence[Decided]:
        found = []
        for name, front, body, state, error, _path in project_decision_files(self._cwd):
            if error or not is_lesson(front):
                continue
            try:
                kind = LessonKind(str(front.get("lesson", "")).strip().lower())
                stories = Count(int(str(front.get("stories", "0")).strip() or 0))
            except ValueError:
                continue
            record = record_of(name, front, body, state, decision_state(body)[1])
            said = record.answer_sentence()
            found.append(Decided(kind, SignalKey(str(front.get("key", ""))),
                                 LessonPlace.named(said) if said is not None else None, stories))
        return found
