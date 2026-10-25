"""The schedule as the cli and the runner call it: one story's state, the schedule over every story, and the lines
`schedule` and `--start` print for the runner — wired to the delivery context's read models
(`delivery/application/schedule/`), which decide in the domain (`StoryStanding`, `Scheduling`).
"""

import os
import sys
from datetime import datetime, timezone
from .sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, factory_home
from .delivery.application.schedule.stand_story import stand_story
from .delivery.adapter.outgoing.files.story_facts_files import StoryFactsFiles
from .delivery.adapter.outgoing.files.backlog_files import BacklogFiles
from .delivery.application.schedule.schedule_backlog import schedule_backlog
from .delivery.adapter.outgoing.tools.streams import tokens_of
from .delivery.adapter.outgoing.git.worktrees import has_worktree
from .delivery.adapter.outgoing.files.usage_files import journal_usage


def story_state(cwd, runs, story_id, front, story_path=None):
    """(state, stage to run from or None, detail) for one story, from its files alone."""
    standing = stand_story(StoryFactsFiles(cwd, runs, story_id, front, story_path))
    return standing.state.value, standing.start.value if standing.start else None, standing.detail.value


def schedule_data(cwd, epics, runs, slots=None, busy=(), skip=()):
    """Every story's state, the order and the next one to run — read off the files, printed by `schedule` for the
    runner and by `status` for a person (`delivery/application/schedule/schedule_backlog.py`)."""
    return schedule_backlog(BacklogFiles(cwd, epics, runs), datetime.now(timezone.utc), slots, busy, skip)


def schedule(cwd, epics, runs, slots=None, busy=(), skip=()):
    """Print every story's state and the next one to run; return 0. The runner and the tests read
    these lines (`schedule:`, `wait:`, `next:`): they are a contract, not the person's view. With `slots`,
    one `next:` line per story that may start now."""
    data = schedule_data(cwd, epics, runs, slots, busy, skip)
    stories, order, nxt, reason, wait = data["stories"], data["order"], data["next"], data["reason"], data["wait"]
    if data["hint"]:
        print(f"layout: {data['hint']}")
    for story_id in order:
        story = stories[story_id]
        start = f"from {story['start']}" if story["start"] else ""
        # What the story cost so far, from the runner's journal — kept per story on disk, so a
        # restart, a second session or a new run never resets it. An in-session run writes none.
        journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
        spent = ""
        if os.path.isfile(journal):
            used = journal_usage(runs, story_id)
            count = sum(e["invocations"] for e in used.values())
            tokens = sum(tokens_of(e) for e in used.values())
            spent = (f" · {count} stage invocation(s)" + (f", {tokens:,} tokens" if tokens else "")) if count else ""
        print(f"{story_id}  {story['state']:<11} {start:<13} {story['detail']}{spent}".rstrip())
    counts = data["counts"]
    print("schedule: " + (", ".join(f"{n} {state}" for state, n in sorted(counts.items()))
                          or "no story under " + epics + "/"))
    print(f"wait: {'yes' if wait else 'no'}")
    print(f"next: {nxt} {stories[nxt]['start']}" if nxt else f"next: none — {reason}")
    for also in data.get("also", []):
        print(f"next: {also} {stories[also]['start']}")
    return 0


def start_of(cwd, epics, runs, story_id, slots=None):
    """Where `run --story <id>` begins when no stage is named: the schedule's view of that one story, as
    (state, stage or None, detail); None for an unknown story. A story that is delivered, waits, is blocked or
    stopped starts nowhere; another story's unfinished code in the checkout blocks it the way it blocks the
    backlog run."""
    data = schedule_data(cwd, epics, runs, slots)
    story = data["stories"].get(story_id)
    if story is None:
        return None
    state, stage, detail = story["state"], story["start"], story["detail"]
    if stage and not slots and has_worktree(story_id, factory_home() or cwd):
        state, stage, detail = "blocked", None, (f"its code is in its worktree — the runner takes it up: "
                                                 f"factory.sh run --story {story_id}")
    holder = next((s for s in data["order"] if data["stories"][s].get("holds")), None)
    if stage and holder and holder != story_id:
        state, stage, detail = "blocked", None, (f"{holder} holds unfinished code in the checkout "
                                                 f"({data['stories'][holder]['state']}) — it is delivered first")
    return state, stage, detail


def start(cwd, epics, runs, story_id, slots=None):
    """`start_of` printed as `state:`, `start:` (a stage, or `none`) and `detail:`. Exit 2 for an unknown story."""
    found = start_of(cwd, epics, runs, story_id, slots)
    if found is None:
        print(f"factory: no story {story_id} under {epics}/", file=sys.stderr)
        return 2
    state, stage, detail = found
    print(f"state: {state}")
    print(f"start: {stage or 'none'}")
    print(f"detail: {detail}")
    return 0
