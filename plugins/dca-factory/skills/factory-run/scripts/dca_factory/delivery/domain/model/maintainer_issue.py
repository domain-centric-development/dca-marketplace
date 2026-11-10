"""What is the factory's goes up: a lesson a person answered `factory`, `rule-library` or `knowledge-catalog` becomes an
issue text for the maintainers — anonymised, in general words, sent by a person, never by the factory."""

from __future__ import annotations

import re
import typing

from ....building_blocks import Value
from .lesson import LessonKind, LessonPlace, SignalKey
from .question_tag import QuestionTag
from .story_words import Count, Detail

#: The perspectives a review stage knows by default — a perspective of the project's own is not named.
GENERAL_PERSPECTIVES = ("ddd", "hexagonal", "clean-code", "plan", "security", "frontend", "test")
#: The method's and the factory's own rule ids — a project's own rule id is not named.
GENERAL_RULE = re.compile(r"^(?:dca|gate|stage|run)(?:-[a-z0-9]+)+$")
#: The codes the factory itself writes: a judge's domain code, a correction's reason code.
GENERAL_CODES = ("domain-concept", "domain-boundary", "domain-invariant", "domain-term", "structural", "behavioural",
                 "assumption")

TARGET_TITLES = {
    LessonPlace.FACTORY: "The delivery pipeline",
    LessonPlace.RULE_LIBRARY: "The rule suite",
    LessonPlace.KNOWLEDGE_CATALOG: "The knowledge catalog",
}

WHAT = {
    LessonKind.QUESTION: "A stage asked the same kind of question in {n} stories of one project.",
    LessonKind.FINDING: "The judge confirmed the same kind of finding in {n} stories of one project.",
    LessonKind.CORRECTION: "A person corrected the same kind of thing at acceptance in {n} stories of one project.",
    LessonKind.ASSUMPTION: "The same assumption was answered the same way in {n} stories of one project.",
    LessonKind.TERM: "A word of the project's language was flagged in {n} stories of one project.",
}

PROPOSED = {
    LessonPlace.FACTORY: "A stage rule, a gate check or a change to the page that settles this before a stage asks "
                         "or a person corrects it — or the reason it cannot be the pipeline's.",
    LessonPlace.RULE_LIBRARY: "A rule of the suite that catches this shape in the code, with the cases it must and "
                              "must not select — or the reason no rule can check it.",
    LessonPlace.KNOWLEDGE_CATALOG: "A node of the catalog (a pitfall, a decision or a recipe) that says what the "
                                   "stages should have known — or the node that already says it and was not read.",
}


class IssueTarget(Value):
    """Who receives the issue: the place a person answered, one of the three that go up."""

    place: LessonPlace

    def __post_init__(self) -> None:
        if not self.place.goes_up:
            raise ValueError(f"{self.place.value} is the project's place, not the maintainers'")


class MaintainerIssue(Value):
    """An issue text for the people who maintain the factory, the rule suite or the knowledge. It names no project, no
    story, no path and no word of the project's language: only the kind of signal, how many stories showed it, the
    words the factory itself keeps (a question's tag, a default perspective, a rule id of the method or the factory, a
    domain or reason code), the pipeline's version and what is proposed."""

    target: IssueTarget
    kind: LessonKind
    key: SignalKey
    stories: Count
    #: the pipeline that saw it: `dca-factory <version>, contract <n>`
    pipeline: Detail

    def shape(self) -> typing.Tuple[Detail, ...]:
        """The parts of the key that are the factory's own words — never the project's."""
        parts = self.key.value.split("/")
        said: typing.List[Detail] = []
        if self.kind is LessonKind.QUESTION:
            tag = QuestionTag.written(Detail(parts[-1]))
            if tag is not None:
                said.append(Detail(f"question tag: `{tag.value}`"))
        elif self.kind is LessonKind.FINDING and len(parts) == 2:
            perspective, what = parts
            said.append(Detail(f"perspective: `{perspective}`" if perspective in GENERAL_PERSPECTIVES
                               else "perspective: one of the project's own"))
            if GENERAL_RULE.match(what):
                said.append(Detail(f"rule: `{what.upper()}`"))
            elif what in GENERAL_CODES:
                said.append(Detail(f"code: `{what}`"))
        elif self.kind is LessonKind.CORRECTION and self.key.value in GENERAL_CODES:
            said.append(Detail(f"reason code: `{self.key.value}`"))
        return tuple(said)

    def text(self) -> Detail:
        lines = [f"# {TARGET_TITLES[self.target.place]}: the same {self.kind.value} in {self.stories.value} stories",
                 "", f"target: {self.target.place.value}", f"signal: {self.kind.value}",
                 f"stories: {self.stories.value}", f"pipeline: {self.pipeline.value}", "", "## What happened",
                 WHAT[self.kind].format(n=self.stories.value)
                 + f" A person who answers the project's lessons decided the correction belongs to "
                   f"{TARGET_TITLES[self.target.place].lower()}, not to the project.", "", "## Shape"]
        lines += [f"- {part.value}" for part in self.shape()] or ["- nothing beyond the kind of signal and its count"]
        lines += ["", "## Proposed", PROPOSED[self.target.place], "", "## About this text",
                  "Written by the delivery pipeline from a lesson a person answered, and sent by that person. It names "
                  "no project, no story, no file and no word of the project's language — only what the pipeline "
                  "itself counts. Ask the sender for an example; they decide what to share.", ""]
        return Detail("\n".join(lines))
