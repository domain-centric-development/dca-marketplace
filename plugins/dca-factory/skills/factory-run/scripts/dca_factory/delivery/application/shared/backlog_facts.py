"""The backlog as the schedule reads it: every story, the epics' graph, what runs, the main line."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import OutputPort
from ...domain.gateway.main_line import MainLine
from ...domain.model.schedule import EpicGraph
from ...domain.model.story_state import Standing
from .story_facts import StoryFacts


@dataclasses.dataclass(frozen=True)
class BacklogStory:
    """One story file as the backlog holds it: the key the schedule shows it under, its fields for the views, and
    either its facts or — for a file that cannot be read, or an id given twice — the standing it has without a
    run."""

    key: str
    path: str
    epic: str
    front: typing.Mapping[str, typing.Any]
    body: str
    title: str
    #: None for a file that cannot be read: the views show no kind for it
    kind: typing.Optional[str]
    depends_on: typing.Tuple[str, ...]
    context: str
    #: its test stage's file is written (its code is under way), and it has its worktree
    tests_written: bool
    worktree: bool
    facts: typing.Optional[StoryFacts]
    standing: typing.Optional[Standing] = None


@dataclasses.dataclass(frozen=True)
class OpenStage:
    """A stage — or the runner's own step — whose start the journal shows and no end, and since when."""

    story: str
    stage: str
    since: str


class BacklogFacts(OutputPort, typing.Protocol):
    """The backlog where the project keeps it."""

    def stories(self) -> typing.Sequence[BacklogStory]:
        """Every story, in the order of its files."""
        ...

    def epics(self) -> EpicGraph:
        ...

    def open_stages(self) -> typing.Sequence[OpenStage]:
        ...

    def main_line(self, stories: typing.Sequence[BacklogStory]) -> MainLine:
        """The main line, for these stories."""
        ...

    def hint(self) -> typing.Optional[str]:
        """What an older layout of the project needs, None where it has none."""
        ...

    def stale_after(self) -> int:
        """Seconds after which a stage begun and not ended counts as interrupted."""
        ...
