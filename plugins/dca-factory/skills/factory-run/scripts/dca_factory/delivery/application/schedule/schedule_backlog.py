"""The schedule over the backlog — every story's state, the order and the next to run — read through the port,
decided by the domain, returned as the read model `schedule` prints for the runner and `status` shows a person."""

from __future__ import annotations

import datetime
import typing

from ...domain.model.epic import EpicId
from ...domain.model.schedule import ContextName, Entry, Holding, Liveness, Running, Slots
from ...domain.model.stage import StageName
from ...domain.model.story import StoryId
from ...domain.model.story_state import Detail
from ...domain.service.scheduling import Scheduling
from ..shared.backlog_facts import BacklogFacts
from ..status.texts import parse_time
from .stand_story import stand_story
from ...domain.model.story_state import ENDED
from ..delivery.pipeline_rules import decides, rule

Model = typing.Dict[str, typing.Any]


@decides(
    rule("RUN-SCHEDULE-1", "the backlog is scheduled", "stories run in the order their epics and dependencies give",
         ok="by epic rank, then id, then `depends_on:` — a cycle last"),
    rule("RUN-SCHEDULE-2", "a story depends on another story or epic", "nothing is built on what is not delivered",
         fail="blocked while a dependency is unknown, in a cycle or not delivered"),
    rule("RUN-SCHEDULE-3", "two stories share an id", "an id names one story", fail="both stop"),
    rule("RUN-SCHEDULE-4", "a runnable story is not committed", "a worktree starts from the committed story",
         fail="blocked until it is committed (with slots); a note without"),
    rule("RUN-SCHEDULE-5", "a stage is open in a story's journal", "a story runs in one place at a time",
         ok="running while the stage is younger than `FACTORY_STALE_AFTER`",
         note="older — possibly interrupted, and resumable"),
    rule("RUN-SCHEDULE-6", "the runner fills its slots (`--parallel`, `FACTORY_PARALLEL`, `parallel:`, else 1)",
         "stories run side by side where they do not meet", ok="worktrees first, then the order; among peers the one "
         "whose context no running story changes"),
    rule("RUN-SCHEDULE-7", "a story began in the checkout without a worktree",
         "unfinished code in the checkout belongs to one story", fail="it runs alone; no other story starts"),
)
def schedule_backlog(backlog: BacklogFacts, now: datetime.datetime, slots: typing.Optional[int] = None,
                     busy: typing.Iterable[str] = (), skip: typing.Iterable[str] = ()) -> Model:
    """The read model: `stories` by key (state, start, detail and the story's fields), `order`, `next` (and `also`
    with slots), `reason`, `wait`, `counts` and the layout `hint`."""
    hint = backlog.hint()
    rows = list(backlog.stories())
    running = {stage.story: stage for stage in backlog.open_stages()}
    stale_after = backlog.stale_after()
    entries = []
    for row in rows:
        standing = row.standing or stand_story(row.facts) if row.facts else row.standing
        assert standing is not None, row.key
        holds = set()
        if row.worktree:
            holds.add(Holding.WORKTREE)
        elif row.standing is None and standing.state not in ENDED and row.tests_written:
            holds.add(Holding.CHECKOUT)
        open_stage = running.get(row.key)
        since = parse_time(open_stage.since) if open_stage else None
        entries.append(Entry(
            StoryId(row.key), standing, tuple(StoryId(d) for d in row.depends_on), EpicId(row.epic),
            ContextName(row.context), frozenset(holds),
            Running(StageName(open_stage.stage), Detail(open_stage.since),
                    Liveness.ALIVE if since and (now - since).total_seconds() <= stale_after else Liveness.SILENT)
            if open_stage else None))
    schedule = Scheduling.schedule(entries, backlog.epics(), backlog.main_line(rows),
                                   Slots(slots) if slots else None, tuple(StoryId(s) for s in busy),
                                   tuple(StoryId(s) for s in skip))
    stories: Model = {}
    for row, entry in zip(rows, entries):
        standing = schedule.standings[entry.story]
        story: Model = dict(state=standing.state.value, start=standing.start.value if standing.start else None,
                            detail=standing.detail.value, deps=list(row.depends_on), path=row.path, epic=row.epic,
                            front=row.front, body=row.body, title=row.title, worktree=row.worktree)
        if row.kind is not None:
            story.update(kind=row.kind, holds=Holding.CHECKOUT in entry.holds)
        stories[row.key] = story
    counts: typing.Dict[str, int] = {}
    for shown in stories.values():
        counts[shown["state"]] = counts.get(shown["state"], 0) + 1
    starts = [s.value for s in schedule.starts]
    data = dict(stories=stories, order=[s.value for s in schedule.order], next=starts[0] if starts else None,
                reason=schedule.reason.value, wait=schedule.wait.value == "yes", counts=counts, hint=hint)
    if slots:
        data["also"] = starts[1:]
    return data
