"""What a view's press is pending on: the request written for it already, or the one it waits on."""

from __future__ import annotations

import typing

from ..shared.requests import Request

#: An action as a view draws it: its text, skill, shell form, label — and `request`, what pressing it writes.
Action = typing.Dict[str, typing.Any]


def pending_id(request: Request, pending: typing.Sequence[Request]) -> str:
    """The id of a request in <pending> (queued, running or waiting) that already does what <request> — an action's,
    as `request_of` reads it — would ask for: the same kind, about the same story, epic, record or proposal. '' where
    none does, and for one that still takes the person's words."""
    deciding = ("answer", "accept", "correct")
    fields = request.get("fields", {})
    if request.get("kind") in deciding:
        # one record takes one answer: once any is queued, every answer to that record — the person's words
        # included — waits on it
        for other in pending:
            if other.get("kind") in deciding and (
                    (fields.get("record") and other.get("record") == fields["record"])
                    or (request["kind"] != "answer" and fields.get("story") and other.get("story") == fields["story"]
                        and other.get("kind") != "answer")):
                return str(other["id"])
        return ""
    if request.get("open"):
        return ""
    ids = ("story", "epic", "record", "topic", "proposal")
    wanted = {str(v) for k, v in fields.items() if k in ids}
    for other in pending:
        named = {str(other.get(k) or "") for k in ids}
        # an option named in words is written as the option (the request check)
        given = request.get("words", "")
        if other.get("kind") == request.get("kind") and wanted <= named \
                and given in ("", other["words"], str(other.get("option") or "")):
            return str(other["id"])
    return ""


def chosen(request: Request, other: Request) -> bool:
    """Whether the pending request <other> is the very choice <request> offers: the same kind and, for an answer,
    the same option — or the person's words, where the action takes words and <other> named no option."""
    if other.get("kind") != request.get("kind"):
        return False
    if request["kind"] != "answer":
        return True
    if request.get("open") == "words":
        return not other.get("option")
    return request.get("words", "") in (str(other.get("option") or ""), other.get("words", ""))


def mark_pending(actions: typing.List[Action], pending: typing.Sequence[Request]) -> typing.List[Action]:
    """Every action whose request is written already says so instead of being offered twice: `queued` names that
    request. Where a record takes one answer and another choice of it is pending, the action says what it waits on
    (`waits_on`) — a view draws the chosen one and leaves the others out; `queued_text` says where the request is."""
    for action in actions:
        if not action.get("request"):
            continue
        found = pending_id(action["request"], pending)
        other = next((r for r in pending if r["id"] == found), None)
        mine = other is not None and chosen(action["request"], other)
        action["queued"], action["waits_on"] = (found, "") if mine else ("", found)
        # where it is: waiting to be taken, being worked, or asking the person back
        state = other.get("state", "queued") if other is not None and mine else ""
        action["queued_text"] = {"waiting": "asks you"}.get(state, state)
    return actions
