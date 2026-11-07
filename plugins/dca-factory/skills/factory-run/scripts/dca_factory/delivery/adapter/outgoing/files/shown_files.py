"""The bytes of a file the page shows, read from the project (WP-184) — the adapter of `ShownFileSource`: the path
resolved, so a link out of the places the domain allowed answers nothing, and read no further than a shown file
may be large."""

from __future__ import annotations

import os
import typing

from ....domain.model.handed_file import MAX_BYTES
from ....domain.model.project_path import ProjectPath
from ....domain.model.shown_file import ShownPath
from .request_files import factory_dir
from ....application.shared.shown_file_source import ShownFileSource


class ShownProjectFiles(ShownFileSource):
    """`ShownFileSource` on the project's folders."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def factory_folder(self) -> ProjectPath:
        return ProjectPath(factory_dir().replace(os.sep, "/"))

    def read(self, path: ShownPath) -> typing.Optional[bytes]:
        project = os.path.realpath(self._cwd)
        roots = [os.path.realpath(os.path.join(project, place.value)) for place in path.places]
        real = os.path.realpath(os.path.join(project, path.path.value))
        if not any(real.startswith(root + os.sep) for root in roots) or not os.path.isfile(real):
            return None
        with open(real, "rb") as file:
            return file.read(MAX_BYTES + 1)
