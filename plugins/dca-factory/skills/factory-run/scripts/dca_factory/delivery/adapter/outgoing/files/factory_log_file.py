"""The factory's log on disk (WP-183) — the adapter of `FactoryLog`: `factory.log` in the factory's folder, as the
factory it starts writes it; what is said of it is the use case's."""

from __future__ import annotations

import os
import typing

from ..process.factory_process import LOG_FILE
from .request_files import factory_dir


class FactoryLogFile:
    """`FactoryLog` on the factory's folder of a project."""

    def __init__(self, cwd: str) -> None:
        folder = factory_dir()
        self._path = os.path.join(folder if os.path.isabs(folder) else os.path.join(cwd, folder), LOG_FILE)

    def size(self) -> typing.Optional[int]:
        return os.path.getsize(self._path) if os.path.isfile(self._path) else None

    def read(self, offset: int) -> typing.Tuple[str, int]:
        with open(self._path, "rb") as handle:
            handle.seek(offset)
            chunk = handle.read()
        return chunk.decode("utf-8", errors="replace"), offset + len(chunk)
