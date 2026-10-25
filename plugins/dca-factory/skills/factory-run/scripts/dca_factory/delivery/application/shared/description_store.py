"""The project description's files, as the use cases read them."""

from __future__ import annotations

import typing

from ....building_blocks import Store
from ...domain.model.description import Part, Written


class DescriptionStore(Store, typing.Protocol):
    """The parts of the project description, where the profile places them."""

    def path(self, part: Part) -> str:
        """Where the part is, as a project path."""
        ...

    def named(self, part: Part) -> str:
        """The place the profile names for the part — '' where it names none and the default holds."""
        ...

    def read(self, part: Part) -> typing.Optional[Written]:
        """The part as written — None where its file is not there."""
        ...
