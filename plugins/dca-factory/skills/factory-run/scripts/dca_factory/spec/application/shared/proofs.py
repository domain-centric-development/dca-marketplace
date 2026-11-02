"""What stands behind the spec: the tests the code holds, and the stories that delivered what holds."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.context_spec import Delivery
from ...domain.model.criterion import Selector


class TestSources(OutputPort, typing.Protocol):
    """The project's code, asked which named tests it holds — as the gate finds a test."""

    def located(self, selectors: typing.Sequence[Selector]) -> typing.AbstractSet[Selector]:
        ...


class Deliveries(OutputPort, typing.Protocol):
    """The delivered stories, each with the criteria it brought and how it was delivered."""

    def delivered(self) -> typing.Sequence[Delivery]:
        ...
