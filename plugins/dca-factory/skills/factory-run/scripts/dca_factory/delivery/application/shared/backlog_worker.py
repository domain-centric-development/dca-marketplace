"""What a backlog run asks of the factory around it: the checkout it holds, and the processes that run a story or a
request."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from .requests import Request


class Child(OutputPort, typing.Protocol):
    """A story's or a request's process started beside the run."""

    def ended(self) -> typing.Optional[int]:
        """Its exit once it ended and said all it had to say; None while it runs."""
        ...


class BacklogCheckout(OutputPort, typing.Protocol):
    """The main checkout under the run's claim."""

    def prune(self) -> None:
        """A superseded story's worktree removed — it has nothing to integrate."""
        ...

    def renew(self) -> bool:
        """The claim renewed: False when another worker took the checkout over."""
        ...

    def stop_asked(self) -> typing.Optional[str]:
        """The stop file, as a person reads its place, when it exists; None otherwise."""
        ...

    def stop_place(self) -> str:
        """Where the stop file goes."""
        ...

    def claims(self) -> str:
        """The remote claims refreshed, as a person reads them; "" when the project claims nothing remotely."""
        ...

    def signalled(self) -> typing.Optional[int]:
        """The exit of a signal that arrived since the last look, taken; None when none did."""
        ...

    def wait(self, interval: int) -> None:
        """The watch's pause: <interval> seconds, cut short by the stop file or a request."""
        ...

    def pause(self) -> None:
        """A short pause while children run."""
        ...


class BacklogWorker(OutputPort, typing.Protocol):
    """The processes a backlog run starts."""

    def run(self, story: str, start: str) -> int:
        """A story run from <start> to its end, in this process: its exit."""
        ...

    def fresh(self, story: str, start: str) -> None:
        """A story run again from a stage a person named: its rounds and its window start fresh."""
        ...

    def start(self, story: str, start: str) -> Child:
        """A story run from <start> as a process of its own beside the run."""
        ...

    def work(self, busy: typing.Sequence[str]) -> None:
        """Every request a skill works that is about no story in <busy>, one after another."""
        ...

    def start_request(self, request: Request) -> Child:
        """A request worked as a process of its own beside the run."""
        ...

    def capped(self) -> bool:
        """The run's --max-stages is reached."""
        ...
