"""The decision records as the inbox reads them — what each one says, raw."""

from __future__ import annotations

import typing

from ....building_blocks import OutputPort

Facts = typing.Dict[str, typing.Any]


class DecisionInbox(OutputPort, typing.Protocol):
    """Every decision record of the project, beside the stories and the project's own."""

    def records(self) -> typing.List[Facts]:
        """Each record as it is written: `name`, `error` (why it cannot be read, or None), `path` as a person reads
        it, and for a readable one `id`, `state`, `kind`, `story`, `stage`, `asked`, `title`, `answer` (its fields),
        `options` ({key, text}), `recommended` (an option's key or None) and `sections` (what it says beyond its
        title, the options, the recommendation and the answer)."""
        ...

    def project_name(self) -> str:
        ...

    def where(self) -> str:
        """Where a story's records are kept, as a person reads it."""
        ...
