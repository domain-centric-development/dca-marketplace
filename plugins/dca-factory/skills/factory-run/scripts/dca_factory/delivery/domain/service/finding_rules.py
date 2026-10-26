"""The judge's confirmed defects kept beside a delivered story, open until a person or a task closes them."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService
from ..model.stage_story import FindingKey


class FindingRules(DomainService):
    """Which findings a delivery keeps."""

    @staticmethod
    def kept(known: typing.AbstractSet[FindingKey],
             found: typing.Sequence[FindingKey]) -> typing.FrozenSet[FindingKey]:
        """What of <found> a delivery keeps: each finding not kept already — the same place and defect is one
        finding, however often a later round confirms it."""
        return frozenset(key for key in found if key not in known)
