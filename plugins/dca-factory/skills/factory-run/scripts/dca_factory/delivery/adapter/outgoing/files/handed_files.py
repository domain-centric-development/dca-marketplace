"""The files a person hands over beside their words, kept in the factory's own folder (WP-184) — the adapter of the
`HandedFileStore` port: `.dca-factory/requests/files/<id>/<name>`, never committed. What is taken, how large and
under which name is the domain's (`handed_file`); here only the bytes go to disk and come back."""

from __future__ import annotations

import contextlib
import os
import secrets
import shutil
import time
import typing

from ....domain.model.handed_file import (FILE_ID, KEEP_DAYS, ByteSize, FileName, HandedFile, HandedFileId,
                                          HandedFileRef, kind_of)
from ....domain.model.project_path import ProjectPath
from .request_files import requests_dir
from ....application.shared.handed_file_store import HandedFileStore


def files_dir() -> str:
    return os.path.join(requests_dir(), "files")


class HandedFileFolder(HandedFileStore):
    """`HandedFileStore` on a folder of the project."""

    def keep(self, file: HandedFile) -> HandedFileRef:
        file_id = HandedFileId.fresh(secrets.token_bytes(8))
        folder = os.path.join(files_dir(), file_id.value)
        os.makedirs(folder, exist_ok=False)
        with open(os.path.join(folder, file.name.value), "xb") as out:
            out.write(file.data.value)
        return HandedFileRef(file_id, file.name, file.kind, file.size)

    def find(self, file_id: HandedFileId) -> typing.Optional[HandedFileRef]:
        path = self._path(file_id)
        if not path:
            return None
        with open(path, "rb") as file:
            kind = kind_of(file.read(4096), FileName(os.path.basename(path)))
        return HandedFileRef(file_id, FileName(os.path.basename(path)), kind, ByteSize(os.path.getsize(path))) if kind else None

    def readable(self, file_id: HandedFileId) -> typing.Optional[ProjectPath]:
        path = self._path(file_id)
        return ProjectPath(path.replace(os.sep, "/")) if path else None

    def drop(self, file_id: HandedFileId) -> None:
        with contextlib.suppress(OSError):
            shutil.rmtree(os.path.join(files_dir(), file_id.value))

    def prune(self, named: typing.Iterable[HandedFileId]) -> None:
        folder = files_dir()
        if not os.path.isdir(folder):
            return
        keep_ids, limit = {i.value for i in named}, time.time() - KEEP_DAYS * 86400
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            with contextlib.suppress(OSError):
                if name not in keep_ids and os.path.getmtime(path) < limit:
                    shutil.rmtree(path)

    @staticmethod
    def _path(file_id: HandedFileId) -> typing.Optional[str]:
        """The one file in the id's folder — no link, nothing else beside it."""
        if not FILE_ID.match(file_id.value):
            return None
        folder = os.path.join(files_dir(), file_id.value)
        names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
        if len(names) != 1 or os.path.islink(os.path.join(folder, names[0])):
            return None
        return os.path.join(folder, names[0])
