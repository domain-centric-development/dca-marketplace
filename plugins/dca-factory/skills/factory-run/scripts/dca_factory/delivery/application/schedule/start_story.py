"""Where `run --story <id>` begins when no stage is named — the schedule's view of that one story."""

from __future__ import annotations

import typing

from .schedule_backlog import Model

#: (state, the stage it starts from or None, detail)
Start = typing.Tuple[str, typing.Optional[str], str]


def start_story(schedule: Model, story_id: str, slots: typing.Optional[int] = None) -> typing.Optional[Start]:
    """The story's start in the schedule's read model; None for an unknown story. A story that is delivered, waits,
    is blocked or stopped starts nowhere; one whose code is in its worktree is taken up by the runner, not started
    again; another story's unfinished code in the checkout blocks it the way it blocks the backlog run."""
    story = schedule["stories"].get(story_id)
    if story is None:
        return None
    state, stage, detail = story["state"], story["start"], story["detail"]
    if stage and not slots and story.get("worktree"):
        state, stage, detail = "blocked", None, (f"its code is in its worktree — the runner takes it up: "
                                                 f"factory.sh run --story {story_id}")
    holder = next((s for s in schedule["order"] if schedule["stories"][s].get("holds")), None)
    if stage and holder and holder != story_id:
        state, stage, detail = "blocked", None, (f"{holder} holds unfinished code in the checkout "
                                                 f"({schedule['stories'][holder]['state']}) — it is delivered first")
    return state, stage, detail
