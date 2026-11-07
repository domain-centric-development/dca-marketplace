"""The factory's process and page for the checkout it runs in, through the process module's own commands."""

from __future__ import annotations

import os
import typing

from . import factory_process
from ....application.shared.factory_process import FactoryProcess

Info = typing.Mapping[str, typing.Any]


class FactoryProcessFiles(FactoryProcess):
    def __init__(self, cwd: typing.Optional[str] = None) -> None:
        self._cwd = cwd or os.getcwd()

    def up(self, run_args: typing.Sequence[str], serve: bool, port: typing.Optional[int], by: str,
           backlog: bool = True) -> int:
        return factory_process.up(self._cwd, run_args, serve, port, by, backlog=backlog)

    def end_page(self) -> int:
        return factory_process.end_page()

    def down(self, now: bool, wait: bool, by: str) -> int:
        return factory_process.down(self._cwd, now, wait, by)

    def running_page(self) -> typing.Optional[Info]:
        return factory_process.running_page(self._cwd)

    def start_page(self, port: typing.Optional[int]) -> int:
        return factory_process.start_page(self._cwd, port)

    def worker(self) -> typing.Optional[Info]:
        return factory_process.worker(self._cwd)

    def worker_line(self, info: typing.Optional[Info]) -> str:
        return factory_process.worker_line(dict(info) if info else None)
