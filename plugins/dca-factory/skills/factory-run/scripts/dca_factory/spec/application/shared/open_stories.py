"""The stories not delivered yet, as delivery publishes them."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.context_spec import OpenStory


class OpenStories(OutputPort, typing.Protocol):
    """Every story of the backlog not delivered and not set aside, with the criteria it brings."""

    def not_delivered(self) -> typing.Sequence[OpenStory]:
        ...
