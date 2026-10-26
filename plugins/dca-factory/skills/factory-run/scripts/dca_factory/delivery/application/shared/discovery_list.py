"""The discovery's topics as the discovery context lists them: each with its proposed epics — and which the backlog
holds already — and its proposed description changes."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort

Model = typing.Dict[str, typing.Any]


class DiscoveryList(OutputPort, typing.Protocol):
    def topics(self) -> Model:
        """`store` and `topics`, each `{topic, title, report, proposals, description_changes}`."""
        ...
