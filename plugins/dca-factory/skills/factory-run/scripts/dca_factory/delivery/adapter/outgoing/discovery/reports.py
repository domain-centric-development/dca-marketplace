"""Discovery's reports as delivery reads them — through discovery's open host service, never its files."""

from __future__ import annotations

import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import location, read_profile, resolve_profile
from .....discovery.api import proposals_in, report_of


class DiscoveryReportFiles:
    """The discovery reports of the project the process works in, as discovery says them."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def report_of(self, topic: str) -> typing.Optional[str]:
        return report_of(self._cwd, location(read_profile(resolve_profile(None, self._cwd)), "discovery"), topic)

    def proposals_in(self, report: str) -> typing.List[str]:
        return proposals_in(self._cwd, report)
