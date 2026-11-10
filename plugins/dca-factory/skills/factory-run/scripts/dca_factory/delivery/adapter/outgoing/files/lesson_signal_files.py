"""The signals a lesson is counted from, as the project's files hold them — the stories' decision records and
findings, their acceptances and assumptions — and the lesson records already written."""

from __future__ import annotations

import os
import re
import typing

from .decision_record_files import decision_files, decision_state, project_decision_files, record_of
from .findings_files import findings_path, findings_rows
from .status_facts import correction_code
from .story_layout import story_files, story_id_of
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .....sharedkernel.adapter.outgoing.profile.profile_files import place
from ....application.shared.front import is_acceptance
from ....application.shared.lesson_signals import LessonSignals
from ....domain.model.decision_record import DecisionState
from ....domain.model.lesson import Decided, Evidence, LessonKind, LessonPlace, Signal, SignalKey
from ....domain.model.question_tag import QuestionTag
from ....domain.model.story import StoryId
from ....domain.model.story_words import Count, Detail

#: A rule id as a finding names it: two or more upper-case words and a number — `DCA-HEX-014`, `STAGE-PLAN-9B`; a
#: story id (`US-3`) is not one.
RULE_ID = re.compile(r"\b[A-Z]{2,}(?:-[A-Z]{2,})+-\d+[A-Z]?\b")
#: The domain code a judge's finding opens with (`domain-term: …`).
DOMAIN_CODE = re.compile(r"^\s*`?(domain-(?:concept|boundary|invariant|term))`?\s*:", re.I)
#: The first word in back ticks — the term a `domain-term` finding flags.
TERM = re.compile(r"`([^`]{1,40})`")

#: A lesson record's own front matter: `kind: lesson`, the candidate's `lesson:` kind and `key:`, `stories:` counted
#: when it was asked.
LESSON_KIND = "lesson"


def finding_signals(story: StoryId, row: typing.Tuple[str, ...]) -> typing.List[Signal]:
    """A finding row's signals: the finding under its perspective and the rule it names — else its domain code —,
    and for a `domain-term` finding the term it flags. A finding that names neither is counted nowhere: what is the
    same could not be told without guessing."""
    n, perspective, _where, _severity, defect, _fix, _status, _plain = row
    evidence = Evidence(story, Detail(f"{story.value}#{n}"))
    rule = RULE_ID.search(defect)
    code = DOMAIN_CODE.match(defect)
    found = []
    if rule or code:
        found.append(Signal(LessonKind.FINDING, SignalKey(f"{perspective}/{rule.group(0) if rule else code.group(1)}"),  # type: ignore[union-attr]
                            evidence))
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
        if text.lower().startswith("answered:"):
            said = text[len("answered:"):].strip().rstrip(".")
            if said:
                found.append(Signal(LessonKind.ASSUMPTION, SignalKey(said),
                                    Evidence(story, Detail(f"{story.value} assumptions"))))
    return found


def lesson_front(front: typing.Mapping[str, typing.Any]) -> bool:
    return str(front.get("kind", "")).strip().lower() == LESSON_KIND


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

    def decided(self) -> typing.Sequence[Decided]:
        found = []
        for name, front, body, state, error, _path in project_decision_files(self._cwd):
            if error or not lesson_front(front):
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
