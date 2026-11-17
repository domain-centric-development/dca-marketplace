"""The findings without a class (WP-223): how many there are, and what a request that classifies them may change."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.story_words import Count, Detail


class UnclassedFindings(OutputPort, typing.Protocol):
    """The findings rows of the project without a listed class — those from before contract 39."""

    def count(self) -> Count:
        """How many rows of every findings file carry no listed target, type and qualifier."""
        ...


class ClassFill(OutputPort, typing.Protocol):
    """What a `classify-findings` request wrote, held to what it may change: the three class cells of rows that had
    none, and the file's `classes:` mark — nothing else."""

    def refused(self, paths: typing.Sequence[str]) -> typing.Optional[Detail]:
        """Why the written <paths> change more than that — None where they change only that."""
        ...

    def restore(self, paths: typing.Sequence[str]) -> None:
        """Put the written <paths> back as the last commit holds them."""
        ...
