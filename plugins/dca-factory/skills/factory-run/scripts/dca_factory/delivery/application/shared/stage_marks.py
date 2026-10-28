"""What a gate run leaves in a story's evidence beside its verdict: the judge's signal, the runner's record of the
suites it ran."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort


class StageMarks(OutputPort, typing.Protocol):
    """The marks of a gate run over one story."""

    def judge_passed(self, story: str) -> None:
        """The judge's confirmed defects of the pass the judge passed, as the journal's signal."""
        ...

    def record_suites(self, story: str) -> bool:
        """The runner's own record of its suite runs on this tree, opened for this gate run — False where the runner's
        key is not in the environment, so nothing is recorded or reused."""
        ...
