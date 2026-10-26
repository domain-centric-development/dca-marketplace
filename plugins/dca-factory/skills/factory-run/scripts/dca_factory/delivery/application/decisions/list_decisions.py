"""List the decisions: the inbox, what waits for a person first."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..requests.pending import mark_pending
from ..shared.decision_inbox import DecisionInbox, Facts
from ..shared.requests import PENDING, RequestStore
from ..shared.story_repository import StoryRepository
from ..status.actions import Action, make_action, NamesStory, offered
from ..status.texts import parse_time
from ...domain.model.decision_record import ANSWERED_WORDS, WAITING_WORDS

Model = typing.Dict[str, typing.Any]

#: The order of the inbox: what needs a person first.
RANKS = {"open": 0, "draft": 1, "answered": 2, "applied": 3}


@dataclasses.dataclass(frozen=True)
class ListDecisionsQuery:
    """`story`: one story's records alone."""

    story: typing.Optional[str] = None


class ListDecisionsInputPort(UseCase[ListDecisionsQuery, Model], typing.Protocol):
    """The decision inbox."""


class ListDecisionsUseCase:
    """Every record, what waits for a person first — open, drafts, answered, applied — read from the files alone,
    each open one with what a person can answer to it."""

    def __init__(self, inbox: DecisionInbox, requests: RequestStore, stories: StoryRepository) -> None:
        self._inbox = inbox
        self._requests = requests
        self._stories = stories

    def execute(self, query: ListDecisionsQuery) -> Model:
        pending = [r for r in self._requests.all() if r["state"] in PENDING]
        records: typing.List[Model] = []
        for facts in self._inbox.records():
            if facts["error"] is not None:
                records.append(dict(rank=-1, id=facts["name"], state="unreadable", kind="question", story="?",
                                    stage="?", asked=None, text=str(facts["error"]), options=[], recommended=None,
                                    path=facts["path"]))
                continue
            if query.story and facts["story"] != query.story:
                continue
            state, answer = facts["state"], facts["answer"]
            given = f" → {answer.get('answer')} ({answer.get('by')})" if state in ANSWERED_WORDS else ""
            record: Model = dict(rank=RANKS[state], id=facts["id"], state=state, kind=facts["kind"],
                                 story=facts["story"], stage=facts["stage"], asked=parse_time(facts["asked"]),
                                 text=facts["title"] + given, options=facts["options"],
                                 recommended=facts["recommended"], path=facts["path"], sections=facts["sections"])
            record["actions"] = mark_pending(record_actions(record, self._stories.names_story)
                                             if state in WAITING_WORDS else [], pending)
            records.append(record)
        records.sort(key=lambda r: (r["rank"], r["id"]))
        waiting = [r for r in records if r["state"] in WAITING_WORDS | {"unreadable"}]
        # what a person does with the first record that waits: the inbox skill, or the answer written by hand
        how = make_action(self._stories.names_story, skill="/factory-decisions",
                          shell=f"write the answer into {waiting[0]['path']} under `## Answer`") if waiting else None
        return dict(project=self._inbox.project_name(), story=query.story, records=records, waiting=len(waiting),
                    store=self._inbox.where(), how=how)


def record_actions(record: Facts, names_story: NamesStory) -> typing.List[Action]:
    """What a person can answer to an open record: an acceptance is accepted or corrected (a reason code and their
    words); a question takes one of its options — the stage's recommendation first in weight — or their words."""
    story, rid = record["story"], record["id"]
    head = f"/factory-decisions {story} {rid}" if story else f"/factory-decisions {rid}"
    if record["kind"] == "acceptance":
        return offered(
            make_action(names_story, text="the story does what you wanted", skill=f"{head}: answer accepted",
                        label="accept", primary=True),
            make_action(names_story, text="What should be different?", skill=f"{head}: answer correction:",
                        label="correct"))
    return offered(*[dict(make_action(names_story, text=o["text"], skill=f"{head}: answer {o['key']}", label=o["key"],
                                      primary=o["key"] == record["recommended"]),
                          note="the stage's recommendation" if o["key"] == record["recommended"] else "")
                     for o in record["options"]],
                   make_action(names_story, text="Your answer, in your words", skill=f"{head}: answer",
                               label="answer"))
