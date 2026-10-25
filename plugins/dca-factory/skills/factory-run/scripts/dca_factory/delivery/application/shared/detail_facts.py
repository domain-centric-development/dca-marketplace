"""What a story's or an epic's detail reads beyond the status: its file taken apart, and what its journal and its
running stream say — raw; what they mean for a person is the detail's read model's."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort

Facts = typing.Dict[str, typing.Any]


class DetailFacts(OutputPort, typing.Protocol):
    """One story or one epic, as its detail reads it."""

    def story_text(self, path: str, body: str, front: Facts) -> Facts:
        """A story's file taken apart: `description` (its own words), `sections` and `criteria_at` (where its
        criteria stood among them), `scenarios`, the number of `criteria`, its `kind`."""
        ...

    def story_journal(self, story_id: str, windows: typing.Iterable[str],
                      stages: typing.Iterable[str]) -> Facts:
        """What the story's journal says beyond its figures: per shared window its `parts` (summed per stage, in the
        stages' order) and whether they are `incomplete`; per stage the calls the tool `denied` it."""
        ...

    def stream_now(self, story_id: str, window: str) -> typing.List[Facts]:
        """The parts the newest stream of a shared window shows so far, [] without one."""
        ...

    def epic_folders(self) -> typing.Dict[str, str]:
        """Every epic folder, lower case, with the epic id its file names."""
        ...

    def epic_text(self, epic: str) -> Facts:
        """An epic's file taken apart: its `front` and `body`, its `sections` and `stories_at` (where its stories
        stood) — empty where it has no readable file."""
        ...
