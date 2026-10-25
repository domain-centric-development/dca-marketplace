"""Which epics there are."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.epic import EpicId


class EpicCatalog(OutputPort, typing.Protocol):
    """The epics under the project's epics folder."""

    def exists(self, epic: EpicId) -> bool:
        """Whether an epic has this id — its folder's name or the `id:` of its `epic.md`, in any case."""
        ...

    def where(self) -> str:
        """The epics folder, as a person reads it."""
        ...
