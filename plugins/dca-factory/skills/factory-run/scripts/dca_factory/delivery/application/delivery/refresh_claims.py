"""Fetch the remote's claims into the cache the schedule reads, releasing a delivered story's claim — before a run picks its next story."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import UseCase
from ..shared.story_claims import StoryClaims


@dataclasses.dataclass(frozen=True)
class RefreshClaimsCommand:
    """No field: the profile names the remote."""


class RefreshClaimsInputPort(UseCase[RefreshClaimsCommand, int], typing.Protocol):
    """Its exit."""


class RefreshClaimsUseCase:
    def __init__(self, claims: StoryClaims) -> None:
        self._claims = claims

    def execute(self, command: RefreshClaimsCommand) -> int:
        return self._claims.refresh()
