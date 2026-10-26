"""The pipeline's stage table, as delivery's application asks it."""

from __future__ import annotations

import typing

from .stage_rows import STAGES


class ContractStages:
    """The stages of the contract's table, in its order."""

    def names(self) -> typing.List[str]:
        return [str(stage.name) for stage in STAGES]
