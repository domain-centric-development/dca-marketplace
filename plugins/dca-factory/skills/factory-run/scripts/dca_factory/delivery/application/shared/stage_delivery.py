"""What a passing gate writes: the plan's marks, the red tree, an acceptance asked, the delivery — into the story,
the spec and the findings —, and the story's commit on the main line or its claim published."""

from __future__ import annotations

import dataclasses
import typing

from ...domain.model.story_state import Acceptance


@dataclasses.dataclass(frozen=True)
class AcceptanceFacts:
    """Whether the story waits for a person's look before it is delivered, where its acceptance stands — or why its
    acceptance cannot be read."""

    applies: bool
    acceptance: typing.Optional[Acceptance]
    refused: typing.Optional[str]


class StageDelivery(typing.Protocol):
    """The writes of a passing gate over one story. `result` is the gate run's verdict the writes report into."""

    def plan_marks(self, story: str, story_path: str) -> None:
        """The story's digest as planned, the baseline of the tests that existed before it, the plan's signal."""
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

    def deliver(self, result: typing.Any, story: str, story_path: str, front: typing.Mapping[str, typing.Any]) -> None:
        """The one write a delivering gate makes into a story, with the spec merged and the findings kept."""
        ...

    def integrate(self, result: typing.Any, story: str, story_path: str, front: typing.Mapping[str, typing.Any],
                  close: typing.Callable[[], None]) -> None:
        """The story on the main line: committed there — or, with claims on a remote, published."""
        ...
