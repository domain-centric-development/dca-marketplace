"""The skeletons a stage starts its hand-over from, written by the pipeline so a model never types what the pipeline
knows — and the shape the gate holds each hand-over to. A writer answers with its exit, already said."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort


class HandOverSkeletons(OutputPort, typing.Protocol):
    def contract(self, stage: str) -> typing.Optional[str]:
        """The shape the gate holds the stage's file to, with its measure; None for a stage it holds to none."""
        ...

    def files(self, story: str, stage: str) -> int:
        """The test, build or tidy hand-over's file list from what the tree changed."""
        ...

    def plan(self, story: str) -> int:
        """plan.md's headings and a line per criterion of the story."""
        ...

    def document(self, story: str) -> int:
        """document.md's headings and every changed path and run file under `## Paths`."""
        ...
