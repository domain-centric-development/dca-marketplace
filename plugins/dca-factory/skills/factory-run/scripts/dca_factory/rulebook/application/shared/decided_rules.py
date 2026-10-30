"""The rules the gate and the runner decide by, and the stage table — as the rulebook reads them."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.rule import Rule
from ...domain.model.rulebook import KindOrder, StageRow


class DecidedRules(OutputPort, typing.Protocol):
    """Delivery's rules, where they are registered: the gate's checks and pass actions, the runner's decisions."""

    def rules(self) -> typing.Tuple[Rule, ...]:
        """Every registered rule, the retired ones included."""
        ...

    def rows(self) -> typing.Tuple[StageRow, ...]:
        """The stage table."""
        ...

    def orders(self) -> typing.Tuple[KindOrder, ...]:
        """Each kind's run order."""
        ...
