"""The tree a change outside a story is checked on, as git holds it: the staged paths, the index against the working
tree, the commit it starts from."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort
from ...domain.model.stage_story import Snapshot


class ChangeIndex(OutputPort, typing.Protocol):
    """The index and the working tree of one project."""

    def backlog_paths(self) -> typing.Optional[typing.List[str]]:
        """The staged paths when every one is the backlog, the description or the pipeline's protocol, else None."""
        ...

    def snapshot(self) -> Snapshot:
        """The index as a tree, and how the working tree differs from it."""
        ...

    def head(self) -> typing.Optional[str]:
        """The commit checked out, None outside git."""
        ...

    def tree(self) -> str:
        """The index as a tree now."""
        ...

    def detach(self) -> None:
        """The commands that follow read no temporary index of the commit being made (`git commit -a`): a test that
        runs git in a repository of its own would read this commit's index as its own."""
        ...
