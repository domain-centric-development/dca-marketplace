"""A story published as its branch (several factories, one backlog): what its delivery changed there, taken back."""

from __future__ import annotations

import dataclasses
import typing


@dataclasses.dataclass(frozen=True)
class TakenBack:
    """The spec files set back as the remote main line has them, and that main line by its name."""

    spec_files: typing.Tuple[str, ...]
    main: str


class PublishedBranches(typing.Protocol):
    def published(self, story: str) -> bool:
        """The story has a published branch in this checkout."""
        ...

    def take_back(self, story: str) -> TakenBack:
        """The branch back to before its delivery, committed: the spec's scenarios and journeys as the remote main
        line has them, the story's state lines out and its status as before it was published."""
        ...
