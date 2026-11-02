"""The factory's own process and its page, as this machine runs them. Each answers with its exit, already said."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort

Info = typing.Mapping[str, typing.Any]


class FactoryProcess(OutputPort, typing.Protocol):
    def up(self, run_args: typing.Sequence[str], serve: bool, port: typing.Optional[int], by: str,
           backlog: bool = True) -> int:
        """The backlog on and the factory's worker started in the background where none runs (`run --watch --stay
        --lane` with <run_args>), its page too with <serve>; <backlog> False — the worker for requests alone."""
        ...

    def end_page(self) -> int:
        """The page that runs here ended; its requests' worker ends once idle where the backlog is off. 0 when none
        runs any more."""
        ...

    def down(self, now: bool, wait: bool, by: str) -> int:
        """The backlog off; the worker ended after its running stage where no page is open — or at once with <now>;
        <wait> until it is gone."""
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
