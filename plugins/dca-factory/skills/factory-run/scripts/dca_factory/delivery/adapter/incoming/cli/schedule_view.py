"""The lines `schedule` and `--start` print for the runner: a contract the runner and the tests read
(`schedule:`, `wait:`, `next:`; `state:`, `start:`, `detail:`), not the person's view."""

from __future__ import annotations

import typing

from ....application.schedule.schedule_backlog import Model
from ....application.schedule.start_story import Start


def schedule_lines(data: Model, epics: str, spent: typing.Mapping[str, str]) -> typing.List[str]:
    """Every story's state and the next one to run — with slots, one `next:` line per story that may start now.
    `spent` is what a story cost so far, by story, as its row ends."""
    stories, order, nxt, reason, wait = data["stories"], data["order"], data["next"], data["reason"], data["wait"]
    lines = [f"layout: {data['hint']}"] if data["hint"] else []
    for story_id in order:
        story = stories[story_id]
        start = f"from {story['start']}" if story["start"] else ""
        lines.append(f"{story_id}  {story['state']:<11} {start:<13} {story['detail']}{spent.get(story_id, '')}".rstrip())
    counts = data["counts"]
    lines.append("schedule: " + (", ".join(f"{n} {state}" for state, n in sorted(counts.items()))
                                 or "no story under " + epics + "/"))
    lines.append(f"wait: {'yes' if wait else 'no'}")
    lines.append(f"next: {nxt} {stories[nxt]['start']}" if nxt else f"next: none — {reason}")
    lines += [f"next: {also} {stories[also]['start']}" for also in data.get("also", [])]
    return lines


def start_lines(found: Start) -> typing.List[str]:
    state, stage, detail = found
    return [f"state: {state}", f"start: {stage or 'none'}", f"detail: {detail}"]
