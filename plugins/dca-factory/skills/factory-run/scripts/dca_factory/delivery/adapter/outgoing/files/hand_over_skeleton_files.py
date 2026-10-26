"""The hand-overs' skeletons and contracts under the run folder, through the pipeline's skeleton writers."""

from __future__ import annotations

import typing

from .skeletons import contract_text, document_skeleton, files_skeleton, plan_skeleton


class HandOverSkeletonFiles:
    def __init__(self, cwd: str, runs: str) -> None:
        self._cwd, self._runs = cwd, runs

    def contract(self, stage: str) -> typing.Optional[str]:
        return contract_text(stage, self._runs)

    def files(self, story: str, stage: str) -> int:
        return files_skeleton(self._runs, story, stage, self._cwd)

    def plan(self, story: str) -> int:
        return plan_skeleton(self._runs, story, self._cwd)

    def document(self, story: str) -> int:
        return document_skeleton(self._runs, story, self._cwd)
