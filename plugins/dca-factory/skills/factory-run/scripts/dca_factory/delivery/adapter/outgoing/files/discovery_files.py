"""Discovery's reports as delivery reads them: `<discovery>/<topic>/discovery.md`, its proposed work by name."""

from __future__ import annotations

import os
import typing

from .....contract import location, read_profile, resolve_profile
from .....gate import discovery_items
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text


class DiscoveryReportFiles:
    """The discovery reports of the project the process works in."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def report_of(self, topic: str) -> typing.Optional[str]:
        folder = location(read_profile(resolve_profile(None, self._cwd)), "discovery")
        report = f"{folder}/{topic}/discovery.md".replace(os.sep, "/")
        return report if os.path.isfile(os.path.join(self._cwd, report)) else None

    def proposals_in(self, report: str) -> typing.List[str]:
        return [str(name) for name, _fields in discovery_items(read_text(os.path.join(self._cwd, report)),
                                                                "Proposed work")]
