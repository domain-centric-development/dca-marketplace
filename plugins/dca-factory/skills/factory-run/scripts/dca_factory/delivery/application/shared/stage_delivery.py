"""What a passing gate writes: the plan's marks, the red tree, an acceptance asked, what goes with a delivery — into
the spec and the findings —, and the story's commit on the main line or its claim published. The story's own state is
the aggregate's: the delivery itself goes through the story repository."""

from __future__ import annotations

import dataclasses
import enum
import typing

from ....building_blocks import OutputPort
from ...domain.model.story import Delivery
from ...domain.model.story_state import Acceptance


@dataclasses.dataclass(frozen=True)
class AcceptanceFacts:
    """Whether the story waits for a person's look before it is delivered, where its acceptance stands — or why its
    acceptance cannot be read."""

    applies: bool
    acceptance: typing.Optional[Acceptance]
    refused: typing.Optional[str]


class Landing(enum.Enum):
    """Where a delivery is written: into the story where the gate read it, or into the story's own checkout, whose
    branch is published for a person to merge."""

    STORY = "story"
    CHECKOUT = "checkout"


class StageDelivery(OutputPort, typing.Protocol):
    """The writes of a passing gate over one story. `result` is the gate run's verdict the writes report into."""

    def plan_marks(self, story: str, story_path: str) -> None:
        """The story's digest as planned, the baseline of the tests that existed before it, the plan's signal."""
        ...

    def adopt(self, result: typing.Any, story: str, story_path: str, held: typing.Sequence[typing.Tuple[str, str]],
              whole: bool) -> None:
        """The scenarios the plan found holding, `(key, test)`: the whole story adopted, or those split off into an
        adopted story beside it."""
        ...

    def red_tree(self, result: typing.Any, story: str) -> None:
        """The tree as the test stage left it, where every mapped test was red in this run."""
        ...

    def acceptance(self, story: str, story_path: str) -> AcceptanceFacts:
        ...

    def ask(self, story: str, story_path: str, criteria: typing.Sequence[typing.Tuple[str, str]]
            ) -> typing.Tuple[str, str, typing.Optional[str]]:
        """The next acceptance record written beside the story: (its id, where it is, why it could not be
        written)."""
        ...

    def in_worktree(self) -> bool:
        ...

    def landing(self) -> Landing:
        """Where the integration writes the delivery: the main checkout, or — with claims on a remote — the story's own
        checkout, published."""
        ...

    def prepare(self, result: typing.Any, story: str, story_path: str, front: typing.Mapping[str, typing.Any],
                landing: Landing) -> bool:
        """What goes before the story says delivered — a story's delta merged into the spec, a task's findings
        closed; False where it could not be, the reason in `result`."""
        ...

    def delivered(self, result: typing.Any, story: str, story_path: str, front: typing.Mapping[str, typing.Any],
                  delivery: Delivery, landing: Landing) -> None:
        """What is kept beside a delivered story: the judge's confirmed defects that did not block, the flaky
        tests."""
        ...

    def take_in(self, result: typing.Any, story: str, story_path: str, landing: Landing) -> bool:
        """The story's commit taken where it lands: the main checkout fast-forwarded to it, or the status it is
        published over kept; False where it could not be, the reason in `result`."""
        ...

    def hand_on(self, result: typing.Any, story: str, story_path: str, front: typing.Mapping[str, typing.Any],
                landing: Landing, close: typing.Callable[[], None]) -> None:
        """The delivery handed on: committed on the main line, or the story's branch pushed for a person to merge."""
        ...
