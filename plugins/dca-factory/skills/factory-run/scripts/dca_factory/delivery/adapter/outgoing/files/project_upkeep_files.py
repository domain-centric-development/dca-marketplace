"""The project's layout migrated and its `.gitignore` kept, through the pipeline's own writers."""

from __future__ import annotations

import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_rel
from .migrations import migrate_layout
from .story_record import ignore_journals_in


class ProjectUpkeepFiles:
    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def migrate(self) -> int:
        return migrate_layout(self._cwd)

    def journals_into_git(self) -> typing.Optional[str]:
        return evidence_rel() if ignore_journals_in(self._cwd, evidence_rel()) else None
