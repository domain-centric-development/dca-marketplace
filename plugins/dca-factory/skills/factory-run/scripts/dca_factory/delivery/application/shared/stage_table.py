"""Which stages a story runs through."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort


class StageTable(OutputPort, typing.Protocol):
    """The stages, as the pipeline's table lists them."""

    def names(self) -> typing.List[str]:
        ...
