"""The schedule over every story: the order, what blocks a story, and which may start now — decided over the
stories' standings and the epics' graph, asking the main line only where a story could start."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService
from ..gateway.main_line import MainLine
from ..model.epic import EpicId
from ..model.schedule import Entry, EpicGraph, Holding, Liveness, Schedule, Slots, Wait
from ..model.story import StoryId
from ..model.story_state import Detail, RUNNABLE, StateName, Standing

DONE = (StateName.DELIVERED, StateName.SUPERSEDED)
WAITING = (StateName.WAITING, StateName.RUNNING)
Standings = typing.Dict[StoryId, Standing]


def runnable(standing: Standing) -> typing.Optional[Standing]:
    """The standing where it can run now, else None."""
    return standing if standing.state.value in RUNNABLE else None


def blocked(why: Detail) -> Standing:
    return Standing(StateName.BLOCKED, None, why)


def noted(standing: Standing, note: Detail) -> Standing:
    """The standing with one more note after its detail."""
    return Standing(standing.state, standing.start, Detail(
        (standing.detail.value + " · " if standing.detail.value else "") + note.value))


class Scheduling(DomainService):
    """Every story's place and the stories that start now.

    One story with unfinished code in the checkout at a time: a story past its plan stage that is not delivered and
    has no worktree holds the checkout, because its tests and code are in the working tree and a second story would
    build on them. Such a story is next if it can run, and nothing else starts while it cannot. A story that stopped
    at its plan stage wrote no code, so independent work runs past it.

    With slots — the runner, which gives every story a worktree of its own — a story's code is in its worktree, so a
    story that waits holds nothing: up to that many stories run at once, `busy` names the ones this runner runs
    already. A story with a worktree goes first (it has code), then the order; between stories of one epic the one
    whose context no running story changes. `skip` names the stories that stopped in this run: they read as stopped,
    so what depends on them is blocked."""

    @staticmethod
    def twin(story: StoryId, others: typing.Sequence[Detail]) -> typing.Optional[Standing]:
        """Two stories under one id would share a run folder and a row: each stops, naming where the others are."""
        if not others:
            return None
        return Standing(StateName.STOPPED, None, Detail(
            f"id {story.value!r} is not unique — also {', '.join(o.value for o in others)}; give one of them another"))

    @staticmethod
    def schedule(entries: typing.Sequence[Entry], graph: EpicGraph, main_line: MainLine,
                 slots: typing.Optional[Slots] = None, busy: typing.Tuple[StoryId, ...] = (),
                 skip: typing.Tuple[StoryId, ...] = ()) -> Schedule:
        stories = {entry.story: entry for entry in entries}
        standings: Standings = {entry.story: entry.standing for entry in entries}
        for story in skip:
            if story in standings and standings[story].state not in DONE:
                standings[story] = Standing(StateName.STOPPED, None,
                                            Detail("stopped in this run — skipped (--keep-going)"))
        order, cycle = Scheduling.order(stories, graph)
        Scheduling.block(order, cycle, stories, standings, graph)
        # A story the runner would give a worktree is taken from the main line's commit: one the checkout holds
        # uncommitted would be missing from — or older in — the tree the integrate step tests (#162). The runner
        # leaves it; a session working in this checkout may take it as it is.
        for story in order:
            entry = stories[story]
            if not runnable(standings[story]) or entry.holds:
                continue
            why = main_line.uncommitted(story)
            if why and slots:
                standings[story] = blocked(Detail(f"{why.value} — commit it: the runner starts a story from the "
                                                  f"main line's commit"))
            elif why:
                standings[story] = noted(standings[story], Detail(f"{why.value} — the runner takes it once it is "
                                                                  f"committed"))
        # A stage that started and has not ended is running — unless it has shown no sign of life for longer
        # than a stage may take, then it was interrupted and the story may be picked up again.
        for entry in entries:
            if entry.running is None or standings[entry.story].state in DONE:
                continue                              # done is done: a killed runner's open stage changes nothing
            stage, since = entry.running.stage.value, entry.running.since.value
            if entry.running.liveness == Liveness.ALIVE:
                standings[entry.story] = Standing(StateName.RUNNING, None, Detail(f"stage {stage} since {since}"))
            else:
                standings[entry.story] = noted(standings[entry.story], Detail(
                    f"stage {stage} started {since} and never ended — possibly interrupted"))
        holders = [s for s in order if Holding.CHECKOUT in stories[s].holds]
        if slots:
            return Scheduling.slotted(order, stories, standings, holders, slots, busy)
        return Scheduling.alone(order, stories, standings, holders, main_line)

    @staticmethod
    def order(stories: typing.Mapping[StoryId, Entry],
              graph: EpicGraph) -> typing.Tuple[typing.Tuple[StoryId, ...], typing.Tuple[StoryId, ...]]:
        """Dependency order, ties by the epic's place (an epic's `depends_on:` first, then its id) and then the
        story's id; whatever is left after that sits on a cycle, which is returned beside the order."""
        rank = {epic: index for index, epic in enumerate(graph.ranked)}
        placed: typing.Set[StoryId] = set()
        order: typing.List[StoryId] = []
        remaining = sorted(stories, key=lambda s: (rank.get(stories[s].epic, len(rank)), s.value))
        while remaining:
            free = [s for s in remaining if all(d in placed or d not in stories for d in stories[s].depends_on)]
            if not free:
                break
            order.append(free[0])
            placed.add(free[0])
            remaining.remove(free[0])
        return tuple(order + remaining), tuple(remaining)

    @staticmethod
    def block(order: typing.Sequence[StoryId], cycle: typing.Sequence[StoryId],
              stories: typing.Mapping[StoryId, Entry], standings: Standings, graph: EpicGraph) -> None:
        """Block every story that could run but waits for a story or an epic, in the order — a dependency blocked
        before it reads as blocked."""
        for story in order:
            if not runnable(standings[story]):
                continue
            needs = stories[story].depends_on
            unknown = [d.value for d in needs if d not in stories]
            if story in cycle:
                standings[story] = blocked(Detail("on a dependency cycle: "
                                                  + ", ".join(sorted(s.value for s in cycle))))
            elif unknown:
                standings[story] = blocked(Detail("depends on unknown " + ", ".join(unknown)))
            else:
                pending = [d for d in needs if standings[d].state != StateName.DELIVERED]
                if pending:
                    standings[story] = blocked(Detail("depends on " + ", ".join(
                        f"{d.value} ({standings[d].state.value})" for d in pending)))
                else:
                    waits = Scheduling.epic_waits(stories[story].epic, graph, stories, standings)
                    if waits:
                        standings[story] = blocked(waits)

    @staticmethod
    def epic_waits(epic: EpicId, graph: EpicGraph, stories: typing.Mapping[StoryId, Entry],
                   standings: Standings) -> typing.Optional[Detail]:
        """Why a story of this epic may not start yet because of its epic's `depends_on:`, or None. An epic it
        depends on is done when it has stories and every one of them is delivered or superseded — an epic without a
        story has not been built, so what depends on it waits."""
        if epic in graph.cycle:
            return Detail(f"its epic {epic.value} is on a dependency cycle between epics: "
                          f"{', '.join(sorted(e.value for e in graph.cycle))}")
        for needed in graph.needs.get(epic, ()):
            if needed not in graph.needs:
                return Detail(f"its epic {epic.value} depends on unknown epic {needed.value}")
            own = [s for s, entry in stories.items() if entry.epic == needed
                   and standings[s].state != StateName.SUPERSEDED]
            done = sum(1 for s in own if standings[s].state == StateName.DELIVERED)
            if not own or done < len(own):
                return Detail(f"its epic {epic.value} depends on epic {needed.value} ({done} of {len(own)} delivered)"
                              if own else f"its epic {epic.value} depends on epic {needed.value}, which has no story "
                                          f"yet")
        return None

    @staticmethod
    def alone(order: typing.Tuple[StoryId, ...], stories: typing.Mapping[StoryId, Entry], standings: Standings,
              holders: typing.Sequence[StoryId], main_line: MainLine) -> Schedule:
        """The schedule for a session in the checkout: one story at a time."""
        nxt: typing.Optional[StoryId] = None
        reason, wait = "", False
        stray = main_line.stray() if not holders else ()
        if stray:
            shown = ", ".join(d.value for d in stray[:3])
            reason = (f"{len(stray)} changed file(s) in the checkout that no story's run folder claims "
                      f"({shown}{', …' if len(stray) > 3 else ''}) — a run folder removed mid-story, or work "
                      f"in progress; commit or stash it, or restore the run folder, before another story starts")
        elif holders:
            holder = standings[holders[0]]
            if runnable(holder):
                nxt = holders[0]
            else:
                reason = (f"{holders[0].value} holds unfinished code in the checkout ({holder.state.value}) — "
                          f"no other story starts until it is delivered")
                wait = holder.state in WAITING
        else:
            running = [s for s in order if standings[s].state == StateName.RUNNING]
            # A story the runner began in its worktree has its code there: a session in this checkout does not take
            # it up.
            elsewhere = [s for s in order if runnable(standings[s]) and Holding.WORKTREE in stories[s].holds]
            nxt = None if running else next((s for s in order if runnable(standings[s]) and s not in elsewhere),
                                            None)
            wait = any(standings[s].state in WAITING for s in order)
            if running:
                reason = (f"{running[0].value} is running ({standings[running[0]].detail.value}) — one story at a "
                          f"time per checkout")
            elif nxt is None and elsewhere:
                reason = (f"{elsewhere[0].value} has its code in its worktree — the runner takes it up: "
                          f"factory.sh run --story {elsewhere[0].value}")
            elif nxt is None:
                reason = "nothing can run"
        return Schedule(order, standings, (nxt,) if nxt else (), Detail(reason), Wait.YES if wait else Wait.NO)

    @staticmethod
    def slotted(order: typing.Tuple[StoryId, ...], stories: typing.Mapping[StoryId, Entry], standings: Standings,
                holders: typing.Sequence[StoryId], slots: Slots, busy: typing.Tuple[StoryId, ...]) -> Schedule:
        """The schedule for a runner with slots (WP-92): every story in its worktree, up to that many at once."""
        for story in busy:
            if story in standings and standings[story].state not in DONE:
                standings[story] = Standing(StateName.RUNNING, None, Detail("in this runner"))
        running = [s for s in order if standings[s].state == StateName.RUNNING]
        picked: typing.List[StoryId] = []
        reason = ""
        if holders:
            # A story that began in the checkout before it had a worktree finishes there, alone — as before.
            holder = holders[0]
            if runnable(standings[holder]) and holder not in busy and not running:
                picked = [holder]
            else:
                reason = (f"{holder.value} holds unfinished code in the checkout ({standings[holder].state.value}) — "
                          f"no other story starts until it is delivered")
        else:
            def coded(story: StoryId) -> int:
                """0 for a story with its worktree — its code is there, it goes first —, else 1."""
                return 0 if Holding.WORKTREE in stories[story].holds else 1
            candidates = sorted((s for s in order if runnable(standings[s]) and s not in busy),
                                key=lambda s: (coded(s), order.index(s)))
            changing = {stories[s].context for s in running}
            while candidates and len(picked) + len(running) < slots.value:
                first = candidates[0]
                peers = [c for c in candidates if (coded(c), stories[c].epic) == (coded(first), stories[first].epic)]
                choice = next((c for c in peers if stories[c].context not in changing), first)
                picked.append(choice)
                candidates.remove(choice)
                changing.add(stories[choice].context)
            if not picked:
                reason = (f"{len(running)} of {slots.value} slot(s) busy: {', '.join(s.value for s in running)}"
                          if running and len(running) >= slots.value else "nothing can run")
        wait = any(standings[s].state in WAITING for s in order)
        return Schedule(order, standings, tuple(picked), Detail(reason), Wait.YES if wait else Wait.NO)
