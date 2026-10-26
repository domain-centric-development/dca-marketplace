"""The factory's process and page for the checkout it runs in, through the process module's own commands."""

from __future__ import annotations

import os
import typing

from . import factory_process

Info = typing.Mapping[str, typing.Any]


class FactoryProcessFiles:
    def __init__(self, cwd: typing.Optional[str] = None) -> None:
        self._cwd = cwd or os.getcwd()

    def up(self, run_args: typing.Sequence[str], serve: bool, port: typing.Optional[int], by: str) -> int:
        return factory_process.up(self._cwd, run_args, serve, port, by)

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
