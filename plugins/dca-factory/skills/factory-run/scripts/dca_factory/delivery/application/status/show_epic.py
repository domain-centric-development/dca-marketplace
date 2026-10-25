"""Show one epic: its fields, its own text, its stories with their state, what is up with it, what comes next."""

from __future__ import annotations

import dataclasses
import re
import typing

from ....building_blocks import UseCase, UseCaseException
from ..shared.detail_facts import DetailFacts
from ..shared.front import front_text
from .show_status import ShowStatusInputPort, ShowStatusQuery
from .show_story import said_alike

Model = typing.Dict[str, typing.Any]

#: The front-matter fields an epic's head shows, by the heading of the section that may say the same: a section under
#: one of these headings whose text says nothing beyond its field is left out of the detail.
HEAD_FIELDS = {"intent": "intent", "goal": "goal", "outcome": "metric", "metric": "metric",
               "domain contact": "domain_contact", "domain": "domain_contact"}

#: The sentence the epic template writes under `## Outcome` — it says nothing beyond the outcome event the head shows.
OUTCOME_BOILERPLATE = ("The epic is measured by the outcome event `{metric}`: as long as it is not published in "
                       "production, the epic has not delivered, however much code exists.")


@dataclasses.dataclass(frozen=True)
class ShowEpicQuery:
    epic: str
    live: bool = False


class UnknownEpic(UseCaseException):
    """No epic by the id or folder asked for; `known` names the epics there are."""

    def __init__(self, epic: str, known: typing.List[str]) -> None:
        super().__init__(epic)
        self.epic, self.known = epic, known


class ShowEpicInputPort(UseCase[ShowEpicQuery, Model], typing.Protocol):
    """One epic as a person reads it."""


class ShowEpicUseCase:
    """One epic as a person reads it (WP-146): its fields, its own text, its stories with their state — newest
    first, as the backlog shows them — and what comes next."""

    def __init__(self, status: ShowStatusInputPort, detail: DetailFacts) -> None:
        self._status, self._detail = status, detail

    def execute(self, query: ShowEpicQuery) -> Model:
        overview = self._status.execute(ShowStatusQuery(query.live))
        wanted = query.epic.lower()
        folders = self._detail.epic_folders()
        epic = next((e for e in overview["epics"] if e["epic"].lower() in (wanted, folders.get(wanted, "").lower())),
                    None)
        if epic is None:
            raise UnknownEpic(query.epic, [e["epic"] for e in overview["epics"] if e["epic"]])
        text = self._detail.epic_text(epic["epic"])
        front, body = text["front"], text["body"]
        journey = next((j for j in overview["journeys"] if j["epic"] == epic["epic"]), None)
        return dict(epic=epic["epic"], title=epic.get("title", ""), path=epic.get("path", ""),
                    created=epic.get("created", ""), intent=epic.get("intent", ""), goal=epic.get("goal", ""),
                    metric=epic.get("metric", ""), domain_contact=epic.get("domain_contact", ""),
                    discovery=epic.get("discovery", ""), description=epic_description(body, front),
                    mark=epic_mark(epic), rows=epic["rows"],
                    **epic_sections(text["sections"], text["stories_at"], front),
                    **epic_situation(epic, overview),
                    delivered=epic["delivered"], total=epic["total"], tokens=epic["tokens"],
                    measured=epic["measured"], seconds=epic["seconds"], journey=journey, next=overview["next"])


def epic_mark(epic: typing.Mapping[str, typing.Any]) -> str:
    """The epic's own mark, from its stories: what needs you wins, then what stopped, what runs; ✓ when all
    are delivered."""
    marks = [r["mark"] for r in epic["rows"]]
    for wanted in ("look", "question", "stopped", "running"):
        if wanted in marks:
            return wanted
    return "done" if marks and all(m == "done" for m in marks) else "none"


def without_head(sections: typing.List[Model], front: Model) -> typing.Tuple[typing.List[Model], typing.List[int]]:
    """The sections the head does not already show: one whose heading names a field of HEAD_FIELDS and whose text is
    that field's value (or, for the outcome, the template's sentence about it) — compared after `said_alike` — is
    left out; a section with more to say stays. Returns the sections kept and the indexes of those left out."""
    kept, gone = [], []
    for index, one in enumerate(sections):
        key = HEAD_FIELDS.get(one["heading"].split("(")[0].strip().lower())
        value = front_text(front.get(key)).strip() if key else ""
        same = {said_alike(value)} | ({said_alike(OUTCOME_BOILERPLATE.format(metric=value))} if key == "metric" else set())
        if value and said_alike(one["text"]) in same:
            gone.append(index)
        else:
            kept.append(one)
    return kept, gone


def epic_sections(sections: typing.List[Model], at: typing.Optional[int], front: Model) -> Model:
    """An epic's sections for its detail without those its head already says (`without_head`), and its stories'
    place among the ones kept."""
    kept, gone = without_head(sections, front)
    return dict(sections=kept, stories_at=None if at is None else at - sum(1 for i in gone if i < at))


def epic_description(body: str, front: Model) -> str:
    """An epic's own text beside its fields: its body without the title, without `## Stories` (the stories come with
    their state) and without a section the front matter already says — `## Intent`, `## Goal`, `## Outcome` (its
    `metric:`). Comments left out."""
    said = {"stories"} | {name for name, key in (("intent", "intent"), ("goal", "goal"), ("outcome", "metric"))
                          if front_text(front.get(key))}
    kept, skip = [], False
    for line in body.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            skip = line[3:].strip().lower() in said
        if not skip:
            kept.append(line)
    text = re.sub(r"<!--.*?-->", "", "\n".join(kept), flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def epic_situation(epic: Model, overview: Model) -> Model:
    """What is up with an epic beyond the progress its head shows, in one line: what is set aside, what runs, what
    waits for a person — empty when nothing does. The detail is one page: head, sections, stories."""
    ids = {r["story"] for r in epic["rows"]}
    parts = []  # how much is delivered stands in the head (its progress) — the line says only what comes beside it
    set_aside = sum(1 for r in epic["rows"] if r["state"] == "superseded")
    parts += [f"{set_aside} superseded"] if set_aside else []
    parts += [f"{m['story']} running {m['stage']}" for m in overview["running"]
              if m["story"] in ids and not m["interrupted"]]
    waits = sum(1 for w in overview["waiting"] if w["story"] in ids and not w.get("draft"))
    drafts = sum(1 for w in overview["waiting"] if w["story"] in ids and w.get("draft"))
    parts += [f"{waits} wait{'s' if waits == 1 else ''} for you"] if waits else []
    parts += [f"{drafts} draft{'' if drafts == 1 else 's'}"] if drafts else []
    return dict(situation=" · ".join(parts))
