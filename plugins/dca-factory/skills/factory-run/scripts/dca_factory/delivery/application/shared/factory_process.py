"""The factory's own process and its page, as this machine runs them. Each answers with its exit, already said."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort

Info = typing.Mapping[str, typing.Any]


class FactoryProcess(OutputPort, typing.Protocol):
    def up(self, run_args: typing.Sequence[str], serve: bool, port: typing.Optional[int], by: str) -> int:
        """The factory started in the background (`run --watch --stay` with <run_args>), its page too with <serve>."""
        ...

    def down(self, now: bool, wait: bool, by: str) -> int:
        """The factory ended after its running stage — or at once with <now>; <wait> until it is gone."""
        ...

    def running_page(self) -> typing.Optional[Info]:
        """The page this checkout runs, alive and answering: its pid, port, url — None where none."""
        ...

    def start_page(self, port: typing.Optional[int]) -> int:
        """The page started detached; its exit once it answers or failed."""
        ...

    def worker(self) -> typing.Optional[Info]:
        """Who holds the checkout, since when, how it was started, whether it lives and is stopping."""
        ...

    def worker_line(self, info: typing.Optional[Info]) -> str:
        """The worker as one line a person reads."""
        ...
