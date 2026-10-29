"""Where a story begins, read from the backlog's files through the schedule."""

from __future__ import annotations

import datetime
import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import place
from ....application.schedule.schedule_backlog import schedule_backlog
from ....application.schedule.start_story import start_story
from ....application.shared.story_starts import Start
from .backlog_files import BacklogFiles


class ScheduledStarts:
    """Where a story begins, as the schedule of the checkout reads it now."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def start(self, story: str) -> typing.Optional[Start]:
        schedule = schedule_backlog(BacklogFiles(self._cwd, place("epics"), place("runs")),
                                    datetime.datetime.now(datetime.timezone.utc), 1)
        return start_story(schedule, story, 1)
