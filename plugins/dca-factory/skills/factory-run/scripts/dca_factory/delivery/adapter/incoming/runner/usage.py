"""A request's usage as the runner measured it — tab-separated `key=value` fields — booked through the cost use
case."""

from __future__ import annotations

import typing

from ....application.cost.book_request_cost import BookRequestCostCommand, BookRequestCostInputPort
from ....domain.model.usage import Cost, ModelName, TokenCount, Tokens, Usage


def usage_of(fields: str) -> typing.Optional[Usage]:
    """The usage the fields carry; None where they carry none (`unknown`, no `input=`)."""
    measured = dict(f.split("=", 1) for f in fields.split("\t") if "=" in f)
    if "input" not in measured:
        return None
    count = lambda key: TokenCount(int(measured.get(key, 0) or 0))   # noqa: E731
    return Usage(ModelName(measured.get("model", "unknown")),
                 Tokens(count("input"), count("cache_read"), count("cache_write"), count("output")),
                 Cost(float(measured["cost"])) if measured.get("cost") else None)


def book_request_usage(port: BookRequestCostInputPort, request_id: str, tool: str,
                       fields: str) -> typing.List[typing.Tuple[str, str]]:
    """A request's usage booked on the stories it worked on: one `usage <window> request=<id>` line on each window
    its process opened, an even share each. Returns the windows, (story, window), booked or not."""
    booked = port.execute(BookRequestCostCommand(request_id, tool, usage_of(fields)))
    return [(window.story.value, window.name) for window in booked.windows]
