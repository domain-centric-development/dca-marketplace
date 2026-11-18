"""The signals a lesson is counted from, as delivery publishes them — the stories' findings with their class, their
answered assumptions and gate refusals, the decision records' tags and acceptances' corrections — and the lessons
already asked."""

from __future__ import annotations

import re
import typing

from .....delivery.api import learning as delivery
from .....sharedkernel.adapter.outgoing.profile.profile_files import read_profile, resolve_profile
from ....application.shared.lesson_signals import LessonSignals
from ....domain.model.lesson import (BACK_AFTER, Decided, Evidence, LessonKind, LessonPlace, OPEN_AT_ONCE, Signal,
                                     SignalKey)
from ....domain.model.words import Count, Detail, StoryId

#: A rule id as a finding names it: two or more upper-case words and a number — `DCA-HEX-014`, `STAGE-PLAN-9B`; a
#: story id (`US-3`) is not one.
RULE_ID = re.compile(r"\b[A-Z]{2,}(?:-[A-Z]{2,})+-\d+[A-Z]?\b")
#: The domain code a judge's finding opens with (`domain-term: …`).
DOMAIN_CODE = re.compile(r"^\s*`?(domain-(?:concept|boundary|invariant|term))`?\s*:", re.I)
#: The source an answered line ends with — `(US-1-01)`, `(product/domain.md)`, `(the person, WP-170 decision 4)`:
#: the same answer from two records is the same assumption, and the same source in two stories one answer.
CITATION = re.compile(r"\s*\(([^()]*)\)\s*$")
#: The option a person chose, where the answer opens with it (`a — …`): the same words after another key are the
#: same answer.
OPTION_KEY = re.compile(r"^[a-z]\s+[—-]+\s+")
#: The file of the project description a question's tag points to — where its answer would be said once.
TAG_FILES = {
    "scope": "overview.md", "behaviour": "overview.md", "page-layout": "overview.md",
    "domain-term": "domain.md", "domain-boundary": "domain.md",
    "failure": "tech.md", "test-level": "tech.md", "test-data": "tech.md", "persistence": "tech.md",
    "integration": "tech.md", "dependency": "tech.md",
}
#: The first word in back ticks — the term a `domain-term` finding flags.
TERM = re.compile(r"`([^`]{1,40})`")

Published = typing.Mapping[str, typing.Any]


def finding_signals(story: StoryId, row: Published) -> typing.List[Signal]:
    """A finding's signals, finest first: its class as `<target>/<type>`, within it
    `<perspective>/<target>/<type>/<qualifier>`, within that the rule it names under its perspective; a row without a
    class its rule alone; and for a `domain-term` finding the term it flags. A domain code alone is no key — it
    throws different words together. A finding that names none of them is counted nowhere: what is the same could
    not be told without guessing."""
    perspective, defect, outcome = row["perspective"], row["defect"], row.get("outcome", "")
    evidence = Evidence(story, Detail(f"{story.value}#{row['n']}" + (f" ({outcome})" if outcome else "")))
    rule = RULE_ID.search(defect)
    code = DOMAIN_CODE.match(defect)
    found = []
    fine = coarse = None
    if row.get("target") and row.get("type") and row.get("qualifier"):
        coarse = f"{row['target']}/{row['type']}"
        fine = f"{perspective}/{row['target']}/{row['type']}/{row['qualifier']}"
        found.append(Signal(LessonKind.FINDING, SignalKey(coarse), evidence))
        found.append(Signal(LessonKind.FINDING, SignalKey(fine), evidence, SignalKey(coarse)))
    if rule:
        found.append(Signal(LessonKind.FINDING, SignalKey(f"{perspective}/{rule.group(0)}"),
                            evidence, SignalKey(fine) if fine is not None else None))
    if code and code.group(1).lower() == "domain-term":
        term = TERM.search(defect[code.end():])
        if term:
            found.append(Signal(LessonKind.TERM, SignalKey(term.group(1)), evidence))
    return found


def assumption_signals(story: StoryId, answered: typing.Sequence[str],
                       tags: typing.Optional[typing.Mapping[str, str]] = None) -> typing.List[Signal]:
    """The story's answered assumptions, each its own key — the source it ends with aside, as its evidence: the same
    source in several stories is one answer. A line without one is its story's own. Where the source is a record of
    a known tag (<tags>: record id → tag), the file of the description that tag points to."""
    found = []
    for text in answered:
        line = text.strip().rstrip(".")
        cited = CITATION.search(line)
        said = OPTION_KEY.sub("", CITATION.sub("", line).strip().rstrip("."))
        if not said:
            continue
        source = cited.group(1).strip() if cited else ""
        file = TAG_FILES.get((tags or {}).get(source, ""))
        found.append(Signal(LessonKind.ASSUMPTION, SignalKey(said),
                            Evidence(story, Detail(f"answered in {source}" if source else f"{story.value} assumptions")),
                            said=Detail(said), file=Detail(file) if file else None))
    return found


#: The check a gate refuses on while a question waits for a person — the question itself, counted as its own kind.
ASKING_CHECKS = frozenset({"decisions"})


def refusal_signals(story: StoryId, refusals: typing.Sequence[Published]) -> typing.List[Signal]:
    """The checks a gate refused the story on, each once; the check that stops for a question left out."""
    found: typing.Dict[str, Signal] = {}
    for refusal in refusals:
        check = refusal["check"]
        if check in ASKING_CHECKS:
            continue
        found.setdefault(check, Signal(LessonKind.REFUSAL, SignalKey(check), Evidence(
            story, Detail(f"{story.value} journal: {refusal['stage']} gate refused {check}"))))
    return list(found.values())


class DeliverySignals(LessonSignals):
    """The signals of the project <cwd>, its stories under <epics>, through delivery's api."""

    def __init__(self, cwd: str, epics: typing.Optional[str] = None) -> None:
        self._cwd = cwd
        self._epics = epics

    def signals(self) -> typing.Sequence[Signal]:
        found: typing.List[Signal] = []
        contexts: typing.Dict[str, str] = {}
        stories = delivery.stories(self._cwd, self._epics)
        records = delivery.records(self._cwd, self._epics)
        tags = {record["id"]: record["tag"] for record in records if record["tag"]}
        for story in stories:
            sid = StoryId(story["id"])
            contexts[sid.value] = story["context"]
            found += assumption_signals(sid, story["answered"], tags)
            for row in story["findings"]:
                found += finding_signals(sid, row)
        for story in sorted(stories, key=lambda s: s["id"]):
            found += refusal_signals(StoryId(story["id"]), story["refusals"])
        for record in records:
            story, rid = StoryId(record["story"]), Detail(record["id"])
            if record["acceptance"]:
                if record["correction"]:
                    found.append(Signal(LessonKind.CORRECTION, SignalKey(record["correction"]), Evidence(story, rid)))
                continue
            if record["tag"]:
                found.append(Signal(LessonKind.QUESTION,
                                    SignalKey(f"{contexts.get(story.value, '-')}/{record['tag']}"), Evidence(story, rid)))
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
        for lesson in delivery.lessons(self._cwd):
            try:
                kind = LessonKind(lesson["lesson"])
                stories = Count(int(lesson["stories"] or 0))
            except ValueError:
                continue
            said = lesson["answer"]
            found.append(Decided(kind, SignalKey(lesson["key"]),
                                 LessonPlace.named(Detail(said)) if said is not None else None, stories,
                                 Detail(lesson["id"])))
        return found
