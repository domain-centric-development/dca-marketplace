"""What the stories' journals book, read from the evidence folder."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from ....application.shared.usage_ledger import Spent
from ..tools.streams import tokens_of
from .run_marks import run_stories
from .usage_files import journal_usage


class UsageLedgerFiles:
    def __init__(self, runs: str) -> None:
        self._runs = runs

    def stories(self) -> typing.Sequence[str]:
        return run_stories(self._runs)

    def spent(self, story: str) -> typing.Optional[Spent]:
        if not os.path.isfile(os.path.join(evidence_dir(self._runs, story), "journal.tsv")):
            return None
        used = journal_usage(self._runs, story)
        return Spent(sum(e["invocations"] for e in used.values()), sum(tokens_of(e) for e in used.values()))
