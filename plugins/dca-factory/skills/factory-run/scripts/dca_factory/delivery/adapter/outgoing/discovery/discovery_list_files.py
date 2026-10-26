"""The discovery's topics, asked of the discovery context through its api, under the folder the profile places it."""

from __future__ import annotations

import typing

from .....discovery.api import list_reports
from .....sharedkernel.adapter.outgoing.profile.profile_files import location, read_profile, resolve_profile


class DiscoveryListFiles:
    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def topics(self) -> typing.Dict[str, typing.Any]:
        return list_reports(self._cwd, location(read_profile(resolve_profile(None, self._cwd)), "discovery"))
