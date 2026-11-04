"""Where the bytes of a file the page shows come from (WP-184) — the project's folders today: the port reads a path the
domain allowed, and answers nothing where the file is not there, or is reached only by a link out of its place."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.project_path import ProjectPath
from ...domain.model.shown_file import ShownPath


class ShownFileSource(OutputPort, typing.Protocol):
    def factory_folder(self) -> ProjectPath:
        """The factory's own folder in the project, as the project configures it."""
        ...

    def read(self, path: ShownPath) -> typing.Optional[bytes]:
        """The file's bytes — None where there is none, or where its real place lies outside the path's places."""
        ...
