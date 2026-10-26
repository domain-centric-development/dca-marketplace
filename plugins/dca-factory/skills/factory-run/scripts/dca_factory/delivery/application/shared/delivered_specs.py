"""The delivered stories beside the spec they delivered into, and the shape of every context's spec."""

from __future__ import annotations

import dataclasses
import typing


@dataclasses.dataclass(frozen=True)
class DeliveredCriteria:
    """One delivered story: when, where its keys are unique (its context, or the journeys), its criteria's keys, the
    keys its spec holds now, the spec file as a person reads it, and the keys its plan removed."""

    when: str
    story: str
    place: str
    keys: typing.Tuple[str, ...]
    held: typing.FrozenSet[str]
    target: str
    removes: typing.Tuple[str, ...]


class DeliveredSpecs(typing.Protocol):
    """The stories and the spec as the files hold them."""

    def delivered(self) -> typing.List[DeliveredCriteria]:
        """Every delivered story that names a spec."""
        ...

    def shapes(self) -> typing.List[str]:
        """What every context's spec file breaks of its shape, one line each."""
        ...
