"""The lesson records as files: `<product>/decisions/<id>.md`, a record of the project's own with `kind: lesson`."""

from __future__ import annotations

import os
import string
import typing

from .decision_record_files import LESSON_KIND, project_decisions_dir
from .....sharedkernel.adapter.outgoing.profile.profile_files import read_profile, resolve_profile, shown
from ....application.shared.lesson_records import LessonRecords
from ....domain.model.decision_record import RecordId
from ....domain.model.lesson import Candidate, LessonKind, LessonPlace, Owner
from ....domain.model.moment import Moment

#: What repeated, as the record's title says it.
TITLES = {
    LessonKind.QUESTION: "The same kind of question in {n} stories",
    LessonKind.FINDING: "The same finding in {n} stories",
    LessonKind.CORRECTION: "The same correction at acceptance in {n} stories",
    LessonKind.ASSUMPTION: "An assumption answered the same way in {n} stories",
    LessonKind.TERM: "A term flagged in {n} stories",
}

#: Why the recommended place, by kind — the factory's recommendation, never an answer.
WHY = {
    LessonKind.QUESTION: "a stage asks this kind of question again and again; said once in the description, the "
                         "next brief carries it and the stage stops asking.",
    LessonKind.FINDING: "the judge finds the same flaw story after story; a rule catches it at the gate instead.",
    LessonKind.CORRECTION: "people correct the same thing at acceptance; said in the description, the plan carries it.",
    LessonKind.ASSUMPTION: "the same assumption was answered the same way; said once, nobody needs to answer it again.",
    LessonKind.TERM: "the word was flagged in several stories; in the glossary, the gate looks for it in the code.",
}

#: Who writes a place, as the option names it: the skill to run with the lesson's evidence.
DEFAULT_SKILLS = {
    Owner.DESCRIBE: "`/dca-describe`",
    Owner.GLOSSARY: "`/ubiquitous-language`",
    Owner.METHOD: "the method's skills (`/dca-modelling`)",
    Owner.SETUP: "`/factory-setup`",
    Owner.BACKLOG: "`/factory-backlog`",
}


def option_text(place: LessonPlace, profile: typing.Mapping[str, str], record: RecordId) -> str:
    """One option: the place, what it means, and who writes it."""
    owner = place.owner
    if owner is Owner.NOBODY:
        return f"{place.value} — {place.says.value}"
    if owner is Owner.MAINTAINERS:
        return f"{place.value} — {place.says.value} (`factory.sh lessons --issue {record.value}`, sent by a person)"
    skill = DEFAULT_SKILLS[owner]
    if owner is Owner.GLOSSARY and profile.get("carrier.glossary"):
        skill = f"`/{profile['carrier.glossary']}`"
    return f"{place.value} — {place.says.value} (written by {skill})"


def lesson_text(record: RecordId, candidate: Candidate, asked: Moment, profile: typing.Mapping[str, str]) -> str:
    n = candidate.stories.value
    keys = string.ascii_lowercase
    lines = ["---", f"id: {record.value}", f"kind: {LESSON_KIND}", f"lesson: {candidate.kind.value}",
             f"key: {candidate.key.value}", f"stories: {n}", f"asked: {asked.value}", "---", "",
             f"# {TITLES[candidate.kind].format(n=n)} — {candidate.key.value}", "", "## Question",
             f"Counted, never guessed: this {candidate.kind.value} repeats in {n} stories. Where does its correction "
             "belong? The factory writes no rule and no knowledge itself — the skill that owns the place does, with "
             "the evidence below. No story waits for this answer.", "", "## Evidence"]
    lines += [f"- {e.story.value}: {e.source.value}" for e in candidate.evidence]
    lines += ["", "## Options"]
    lines += [f"- {keys[i]}: {option_text(place, profile, record)}" for i, place in enumerate(candidate.places)]
    lines += ["", "## Recommendation", f"a — {candidate.recommended.value}: {WHY[candidate.kind]}", ""]
    return "\n".join(lines)


class LessonRecordFiles(LessonRecords):
    """The lesson records of the project <cwd>."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def _path(self, record: RecordId) -> str:
        return os.path.join(self._cwd, project_decisions_dir(), record.value + ".md")

    def taken(self, record: RecordId) -> bool:
        return os.path.exists(self._path(record))

    def write(self, record: RecordId, candidate: Candidate, asked: Moment) -> str:
        path = self._path(record)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        profile = read_profile(resolve_profile(None, self._cwd))
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(lesson_text(record, candidate, asked, profile))
        return shown(path)
