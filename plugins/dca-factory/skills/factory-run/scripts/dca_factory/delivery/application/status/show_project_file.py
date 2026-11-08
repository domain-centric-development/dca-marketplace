"""Show one project file the page names (WP-184): a picture, a PDF or a text a record, a report or a story names, or a
mockup an option shows — the domain decides whether and as what, the source only reads."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.handed_file import FileBytes
from ...domain.model.project_path import ProjectPath
from ...domain.model.shown_file import FileNotShown, Refusal, ShownFile, ShownPath, shown_places
from ..shared.shown_file_source import ShownFileSource


@dataclasses.dataclass(frozen=True)
class ShowProjectFileQuery:
    path: str


class ShowProjectFileInputPort(UseCase[ShowProjectFileQuery, ShownFile], typing.Protocol):
    """Show one project file."""


class ShowProjectFileUseCase:
    """The path checked by the domain, the bytes read by the source, the file taken as the domain shows it —
    FileNotShown with its refusal otherwise."""

    def __init__(self, source: ShownFileSource) -> None:
        self._source = source

    def execute(self, query: ShowProjectFileQuery) -> ShownFile:
        path = ShownPath(ProjectPath(query.path), shown_places(self._source.factory_folder()))
        data = self._source.read(path)
        if data is None:
            raise FileNotShown(Refusal.NOTHING, "no such file beneath product/ or the factory's folder")
        return ShownFile.of(path, FileBytes(data))
