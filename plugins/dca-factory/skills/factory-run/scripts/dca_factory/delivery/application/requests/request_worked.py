"""What working or settling a request comes to, and what the factory said on the way."""

from __future__ import annotations

import dataclasses
import typing

#: (stream, line): what the factory says on its way — `out` for the person, `err` for a refusal or a failure
Said = typing.List[typing.Tuple[str, str]]


@dataclasses.dataclass(frozen=True)
class RequestWorked:
    """0 done (and gone), 3 a person is asked (waiting), 1 failed (kept, `error:`); what was said on the way; the
    commit of what it wrote, "" where there is none."""

    code: int
    said: Said
    commit: str = ""
