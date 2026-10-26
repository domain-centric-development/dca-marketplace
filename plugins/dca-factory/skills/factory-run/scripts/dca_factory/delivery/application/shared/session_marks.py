"""A session's marks in a story's journal — the same journal the runner writes — and the person's parts recorded
around a stage it carries out. Each answers with its exit: 0 done, else why not, already said."""

from __future__ import annotations

import typing

from ....building_blocks import Store


class SessionMarks(Store, typing.Protocol):
    def window(self, story: str, work: str, edge: str, session_log: typing.Optional[str]) -> int:
        """A work window's `start` or `end` outside a stage (`backlog`, `decisions`): the session's tokens and time."""
        ...

    def stage(self, story: str, stage: str, edge: str, session_log: typing.Optional[str]) -> int:
        """A stage's `start` or `end` inside a session."""
        ...

    def record_owned(self, story: str) -> None:
        """The person's parts — the story, the answers — recorded at a stage's start."""
        ...

    def compare_owned(self, story: str, stage: str, ran: int) -> int:
        """The person's parts compared at a stage's end; non-zero where the stage changed them."""
        ...

    def append(self, story: str, lines: str) -> None:
        """Lines `<time>\t<kind>\t<name>\t…` appended to the story's journal, numbered."""
        ...
