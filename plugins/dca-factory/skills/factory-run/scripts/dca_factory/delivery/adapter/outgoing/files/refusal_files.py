"""The refused gate runs in the stories' journals: an event `gate` with `exit=1`, its `fail=` checks, its `by=` —
`runner`, or none in an older journal, is the runner's; anything else a stage's own."""

from __future__ import annotations

import typing

from ....application.shared.gate_refusals import Refused, RefusedBy
from ....domain.model.story import StoryId
from ....domain.model.verdict import CheckName
from .journal_files import journal_events
from .run_marks import run_stories


class GateRefusalFiles:
    def __init__(self, runs: str) -> None:
        self._runs = runs

    def stories(self) -> typing.Sequence[StoryId]:
        return [StoryId(story) for story in run_stories(self._runs)]

    def refused(self, story: StoryId) -> typing.Sequence[Refused]:
        found = []
        for event in journal_events(self._runs, story.value):
            fields = event["fields"]
            if event["kind"] != "gate" or fields.get("exit") != "1":
                continue
            by = RefusedBy.RUNNER if fields.get("by", "runner") == "runner" else RefusedBy.STAGES
            found.append(Refused(by, tuple(CheckName(c) for c in fields.get("fail", "").split(",") if c)))
        return found
