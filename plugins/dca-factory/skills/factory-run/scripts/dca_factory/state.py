"""The schedule as the cli and the runner call it: one story's state, the schedule over every story and where one
story starts — wired to the delivery context's read models (`delivery/application/schedule/`), which decide in the
domain (`StoryStanding`, `Scheduling`).
"""

from datetime import datetime, timezone
from .delivery.application.schedule.stand_story import stand_story
from .delivery.adapter.outgoing.files.story_facts_files import StoryFactsFiles
from .delivery.adapter.outgoing.files.backlog_files import BacklogFiles
from .delivery.application.schedule.schedule_backlog import schedule_backlog
from .delivery.application.schedule.start_story import start_story


def story_state(cwd, runs, story_id, front, story_path=None):
    """(state, stage to run from or None, detail) for one story, from its files alone."""
    standing = stand_story(StoryFactsFiles(cwd, runs, story_id, front, story_path))
    return standing.state.value, standing.start.value if standing.start else None, standing.detail.value


def schedule_data(cwd, epics, runs, slots=None, busy=(), skip=()):
    """Every story's state, the order and the next one to run — read off the files, printed by `schedule` for the
    runner and by `status` for a person (`delivery/application/schedule/schedule_backlog.py`)."""
    return schedule_backlog(BacklogFiles(cwd, epics, runs), datetime.now(timezone.utc), slots, busy, skip)


def start_of(cwd, epics, runs, story_id, slots=None):
    """Where `run --story <id>` begins when no stage is named, as (state, stage or None, detail); None for an unknown
    story (`delivery/application/schedule/start_story.py`)."""
    return start_story(schedule_data(cwd, epics, runs, slots), story_id, slots)
