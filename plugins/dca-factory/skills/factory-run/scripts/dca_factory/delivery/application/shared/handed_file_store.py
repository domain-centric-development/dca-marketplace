"""Where the files a person hands over beside their words are kept (WP-184) — a folder of the project today, a server
tomorrow: the port answers by the domain's names alone, never by a place it chose."""

from __future__ import annotations

import typing

from ....building_blocks import Store
from ...domain.model.handed_file import HandedFile, HandedFileId, HandedFileRef
from ...domain.model.project_path import ProjectPath


class HandedFileStore(Store, typing.Protocol):
    def keep(self, file: HandedFile) -> HandedFileRef:
        """Keeps one file and names it by a fresh id."""
        ...

    def find(self, file_id: HandedFileId) -> typing.Optional[HandedFileRef]:
        """A kept file by its id, or None."""
        ...

    def readable(self, file_id: HandedFileId) -> typing.Optional[ProjectPath]:
        """Where a run reads the file inside the project — a store elsewhere brings it there first."""
        ...

    def drop(self, file_id: HandedFileId) -> None:
        """A file kept for a request that was then not written."""
        ...

    def prune(self, named: typing.Iterable[HandedFileId]) -> None:
        """The files no live request names, once older than the domain keeps them."""
        ...
