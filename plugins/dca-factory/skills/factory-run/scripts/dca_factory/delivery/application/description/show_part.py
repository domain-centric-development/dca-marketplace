"""Show one part of the project description as it is written, section by section — what a person reads beside the
part's standing."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ...domain.model.description import Part
from ..shared.description_store import DescriptionStore

Model = typing.Dict[str, typing.Any]


@dataclasses.dataclass(frozen=True)
class ShowPartQuery:
    """`part`: product, tech or domain — the profile key that places it."""

    part: str


class ShowPartInputPort(UseCase[ShowPartQuery, Model], typing.Protocol):
    """One part of the description, as written."""


class ShowPartUseCase:
    """A part with where it is and each of its sections with what it says; no sections where its file is missing."""

    def __init__(self, store: DescriptionStore) -> None:
        self._store = store

    def execute(self, query: ShowPartQuery) -> Model:
        part = Part(query.part)
        found = self._store.sections(part)
        return dict(part=part.value, path=self._store.path(part), present=found is not None,
                    sections=[dict(heading=s.heading.value, text=s.body.value) for s in found or ()])
