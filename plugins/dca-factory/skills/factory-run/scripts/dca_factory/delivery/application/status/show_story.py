"""Show one story: its words, its criteria, its stages and passes with their figures, its decisions, what is up."""

from __future__ import annotations

import dataclasses
import datetime
import re
import typing

from ....building_blocks import UseCase, UseCaseException
from ...domain.model.usage import USAGE_FIELDS
from ..requests.pending import mark_pending
from ..requests.pending_requests import PendingRequestsQuery, PendingRequestsUseCase
from ..shared.detail_facts import DetailFacts
from ..shared.front import accepted, created_of, front_text, is_acceptance
from ..shared.status_facts import StatusFacts
from .actions import make_action, offered
from .show_status import ShowStatusInputPort, ShowStatusQuery
from .texts import figures, parse_time, stamp_text, took_text
from ...domain.model.decision_record import ANSWERED_WORDS

Model = typing.Dict[str, typing.Any]

#: The processes beside the stages: what each is for in a story's detail.
WINDOW_WORK = {"backlog": "writing the story", "decisions": "answering its questions"}

#: The longest a situation line quotes a reason before it cuts it.
SITUATION_REASON = 90


@dataclasses.dataclass(frozen=True)
class ShowStoryQuery:
    story: str
    live: bool = False


class UnknownStory(UseCaseException):
    """No story by the id asked for in the backlog."""


class ShowStoryInputPort(UseCase[ShowStoryQuery, Model], typing.Protocol):
    """One story as a person reads it."""


class ShowStoryUseCase:
    """A story's detail over the status: the row the status shows of it, and what its file, its journal and its
    records say beyond that — the passes, why a stage ran more than once, the decisions, what is up with it."""

    def __init__(self, status: ShowStatusInputPort, facts: StatusFacts, detail: DetailFacts,
                 pending: PendingRequestsUseCase) -> None:
        self._status, self._facts, self._detail, self._pending = status, facts, detail, pending

    def execute(self, query: ShowStoryQuery) -> Model:
        story_id, live = query.story, query.live
        overview = self._status.execute(ShowStatusQuery(live))
        row = next((r for r in overview["rows"] if r["story"] == story_id), None)
        if row is None:
            raise UnknownStory(story_id)
        facts, now = self._facts, self._facts.now()
        data = facts.schedule()["stories"][story_id]
        told = facts.story_facts(story_id, data.get("front"))
        records = facts.story_records(story_id, data.get("path"))
        front, body = data.get("front") or {}, data.get("body") or ""
        text = self._detail.story_text(data.get("path") or "", body, front)
        accepted_by = next((str(f["id"]).strip() for _p, f, _b, st, a in reversed(records)
                            if is_acceptance(f) and st in ANSWERED_WORDS and accepted(a)), None)
        passes = []
        for i, p in enumerate(told["passes"]):
            before = told["passes"][i - 1]["end"] if i else None
            passes.append(dict(p, label=pass_label(i, p, records),
                               waited=(p["start"] - before).total_seconds() if before and p["start"] else 0))
        stages = told["stages"]
        shared = facts.shared_windows()
        # why a stage ran more than once per pass: the questions it asked, else a repeat (a gate refused it)
        questions: typing.Dict[str, typing.List[str]] = {}
        for _p, record, _b, _st, _a in records:
            if not is_acceptance(record):
                questions.setdefault(str(record.get("stage", "")).strip(), []).append(str(record["id"]).strip())
        for stage, entry in stages.items():
            if stage in WINDOW_WORK:
                entry["why"] = WINDOW_WORK[stage] + (f" · {entry['runs']} sessions" if entry["runs"] > 1 else "")
                continue
            extra = entry["runs"] - sum(1 for p in told["passes"] if stage in p["stages"])
            # a shared window carries several stages: a question any of those stages asked is its
            covered = shared.get(stage, (stage,))
            asked = [rid for name in covered for rid in questions.get(name, [])][:max(extra, 0)]
            repeats = max(extra, 0) - len(asked)
            why = [f"{len(asked)} question" + ("s" if len(asked) > 1 else "") + f" ({', '.join(asked)})"] if asked else []
            if repeats:
                why.append(f"{repeats} repeat" + ("s" if repeats > 1 else "") + " (a gate refused)")
            entry["why"] = " · ".join(why)
        decisions = []
        for _p, record, said, state, answer in records:
            question = (said.strip().splitlines() or ["(no title)"])[0].lstrip("# ").strip()
            given = str(answer.get("answer", "")).strip() if state in ANSWERED_WORDS else ""
            line = (f"{given}" if is_acceptance(record) and given else
                    f"{given} — {question}" if given else f"open — {question}")
            decisions.append(dict(id=str(record["id"]).strip(), state=state,
                                  kind="acceptance" if is_acceptance(record) else "question", text=line))
        journal = self._detail.story_journal(story_id, stages, stages)
        for window in journal["parts"]:
            stages[window]["parts"] = journal["parts"][window]
            stages[window]["parts_incomplete"] = journal["incomplete"][window]
        for moving in overview["running"]:
            if moving["story"] == story_id and not moving["interrupted"]:
                window_running(stages.get(moving["stage"]), moving, shared,
                               lambda: self._detail.stream_now(story_id, moving["stage"]), now, live)
        # the calls a stage was denied: each a turn spent on another way
        for stage, entry in stages.items():
            entry["denials"] = journal["denied"][stage]
            entry["denied"] = len(entry["denials"])
            if entry["denied"]:
                entry["why"] = " · ".join(w for w in (entry.get("why", ""), f"{entry['denied']} denied") if w)
        models = sorted({m for e in stages.values() for m in e["models"]})
        not_applied = sorted({r for e in stages.values() if e["not_applied"] for r in e["requested"]})
        for entry in stages.values():
            entry.update(figures(entry))
        # a delivered story is corrected in the person's words: the correction goes back into it
        actions = row["actions"] + (mark_pending(offered(make_action(
            facts.names_story, text="What should be different?",
            skill=f"/factory-decisions {story_id}: answer correction:", label="correct")),
            self._pending.execute(PendingRequestsQuery()).requests) if row["done"] else [])
        return dict(row=row, story=story_id, title=data.get("title", ""), epic=data.get("epic", ""),
                    path=facts.shown(data["path"]) if data.get("path") else "", kind=text["kind"],
                    created=created_of(front), intent=front_text(front.get("intent")),
                    description=text["description"], scenarios=text["scenarios"],
                    superseded=data.get("state") == "superseded",
                    sections=text["sections"], criteria_at=text["criteria_at"],
                    **story_situation(row, data, overview, text["sections"], now),
                    context=str(front.get("context", "")).strip(), criteria=text["criteria"],
                    accepted_by=accepted_by, passes=passes, stages=stages, decisions=decisions, models=models,
                    not_applied=not_applied, signals=facts.story_signals(story_id, records, body),
                    priced=told["priced"] > 0, waiting=[w for w in overview["waiting"] if w["story"] == story_id],
                    next=overview["next"], actions=actions)


def pass_label(index: int, pass_: Model, records: typing.List[typing.Tuple[typing.Any, ...]]) -> str:
    """First delivery, then what started each later pass: a human's correction, or a re-plan."""
    if index == 0:
        return "first delivery"
    corrections = [str(f["id"]).strip() for _p, f, _b, st, a in records
                   if is_acceptance(f) and st in ANSWERED_WORDS and not accepted(a)
                   and parse_time(str(a.get("at", ""))) and parse_time(str(a.get("at", ""))) <= pass_["start"]]
    return "correction" if corrections else "again from plan"


def window_running(entry: typing.Optional[Model], moving: Model, shared: typing.Collection[str],
                   parts_now: typing.Callable[[], typing.List[Model]], now: datetime.datetime, live: bool) -> None:
    """A shared window whose process still runs has no usage line yet — the tool reports it at its end. Its row
    shows what its newest stream says so far (`parts_now`, read only for such a row): the tokens of its parts, and
    with `live` the time since it began; the cost stays the tool's and comes with the end."""
    if not entry or moving["stage"] not in shared or entry["measured"] >= entry["runs"]:
        return
    parts = parts_now()
    for field in USAGE_FIELDS:
        entry[field] = entry.get(field, 0) + sum(p[field] for p in parts)
    entry["tokens"] += sum(p[field] for p in parts for field in USAGE_FIELDS)
    if live and moving.get("since"):
        entry["seconds"] += max((now - moving["since"]).total_seconds(), 0)
    entry["running"] = True


def said_alike(text: str) -> str:
    """A text as compared with another: whitespace collapsed, a trailing period off."""
    return " ".join(text.split()).rstrip(".").strip()


def first_sentence(text: str, limit: int = SITUATION_REASON) -> str:
    """The first sentence of a section's text, list marks and line breaks out, cut at `limit` with an ellipsis."""
    words = " ".join(line.strip().lstrip("-*").strip() for line in text.splitlines() if line.strip())
    sentence = re.split(r"(?<=[.!?;])\s", words, maxsplit=1)[0].rstrip(".;")
    return sentence if len(sentence) <= limit else sentence[:limit - 1].rstrip(" ,;—") + "…"


def story_situation(row: Model, story: Model, overview: Model, sections: typing.List[Model],
                    now: datetime.datetime) -> Model:
    """What is up with a story, in one line the factory decides — and which of its two views a detail opens with:
    `pipeline` while it runs or waits for a person, `story` before it starts and once it is done or set aside. A line
    that would only repeat the state the head shows is empty."""
    found = situation_of_story(row, story, overview, sections, now)
    if said_alike(found["situation"]) == said_alike(str(row.get("state", ""))):
        found["situation"] = ""
    return found


def situation_of_story(row: Model, story: Model, overview: Model, sections: typing.List[Model],
                       now: datetime.datetime) -> Model:
    state = story.get("state", "")
    moving = next((m for m in overview["running"] if m["story"] == row["story"] and not m["interrupted"]), None)
    if moving:
        line = f"running {moving['stage']}" + (f" · {moving['part']}" if moving.get("part") else "")
        line += f" · round {moving['round']}" if (moving.get("round") or 1) > 1 else ""
        if moving.get("since"):
            line += " · " + took_text((now - moving["since"]).total_seconds())
        return dict(situation=line, view="pipeline")
    if state == "superseded":
        reason = next((s["text"] for s in sections if s["kind"] == "superseded"), "")
        return dict(situation="superseded" + (f" — {first_sentence(reason)}" if reason else ""), view="story")
    if row["done"]:
        return dict(situation=f"delivered {stamp_text(row['delivered'])[:10]}" if row["delivered"] else "delivered",
                    view="story")
    detail = str(story.get("detail", "")).strip()
    if state == "blocked":
        return dict(situation="blocked" + (f" — {first_sentence(detail)}" if detail else ""), view="story")
    if row["mark"] in ("look", "question", "stopped"):
        line = row["state"] + (f" — {first_sentence(detail)}" if row["mark"] == "stopped" and detail else "")
        return dict(situation=line, view="story" if state == "unreleased" else "pipeline")
    started = row["passes"] > 0 or state in ("in-progress", "resumable")
    line = row["state"] + ("" if started else " — not started")
    queue = overview.get("queue", {}).get("ready", [])
    if row["story"] in queue:
        place = queue.index(row["story"])
        line += " · next in line" if place == 0 else f" · {place + 1}. in line"
    return dict(situation=line, view="pipeline" if started else "story")
