"""The upkeep feature's commands of the cli: an older layout migrated, the journals let into git."""

from __future__ import annotations

import typing

from ....application.upkeep.let_journals_into_git import LetJournalsIntoGitCommand
from ....application.upkeep.migrate_layout import MigrateLayoutCommand
from . import root


def migrate_layout(cwd: str) -> int:
    return root.wiring.migrate_layout(cwd).execute(MigrateLayoutCommand())


def let_journals_into_git(cwd: str) -> typing.Optional[str]:
    return root.wiring.let_journals_into_git(cwd).execute(LetJournalsIntoGitCommand())
