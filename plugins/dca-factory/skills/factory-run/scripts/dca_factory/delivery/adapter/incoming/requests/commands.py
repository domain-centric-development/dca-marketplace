"""A session's command read as the request that does the same from a page."""

from __future__ import annotations

import os
import re
import typing

from ....application.shared.requests import ID_WORD
from ....domain.model.correction import REASON_CODES

#: A request as an action offers it: {kind, fields, words, open} — `open` names what the person still has to give.
Offer = typing.Dict[str, typing.Any]


def request_of(skill: typing.Optional[str], names_story: typing.Callable[[str], bool]) -> typing.Optional[Offer]:
    """The request that does what a view's action does in a session — `/factory-run <story>`, `/factory-backlog …`,
    `/factory-decisions <story> <record>: answer <key>`, `/dca-describe <change>`, `/factory-discover <words>` — as
    {kind, fields, words, open}: `open` names what the person still has to give (words, an option). None for an
    action no request does (setting the factory up, updating it, a verification). <names_story> says whether a word
    is a story's id."""
    text = " ".join(str(skill or "").split())
    head, _, rest = text.partition(" ")
    if head == "/factory-run":
        # as the skill reads it: a story's id runs that story, every other word is a wish
        if not rest:
            return None
        return dict(kind="run", fields=dict(story=rest), words="", open="") if names_story(rest) \
            else dict(kind="wish", fields={}, words=rest, open="")
    if head == "/factory-backlog":
        verb, _, tail = rest.partition(" ")
        if verb == "release" and tail:
            return dict(kind="release", fields=dict(story=tail), words="", open="")
        if verb in ("stories", "journey") and ID_WORD.match(tail or "-"):
            return dict(kind=verb, fields=dict(epic=tail), words="", open="")
        match = re.match(r"^epic (\S+) --from (\S+)$", rest)
        if match:
            topic = os.path.basename(os.path.dirname(match.group(2)))
            return dict(kind="epic-from", fields=dict(topic=topic, proposal=match.group(1)), words="", open="")
        return dict(kind="wish", fields={}, words=rest, open="" if rest else "words")
    if head == "/factory-decisions":
        # `<story> <record>: answer <words>`, `<record>: answer` (the words still to give), and at an acceptance
        # `answer accepted` or `answer correction` — which name the story, its record the factory finds itself
        match = re.match(r"^(?:(\S+) )?(\S+): answer(?: (.+))?$", rest)
        if match:
            story, record, given = match.group(1) or match.group(2), match.group(2), match.group(3) or ""
            if given == "accepted":
                return dict(kind="accept", fields=dict(story=story), words="", open="")
            if given in ("correction", "correction:"):
                return dict(kind="correct", fields=dict(story=story), words="", open="words",
                            choices=list(REASON_CODES))
            return dict(kind="answer", fields=dict(record=record), words=given, open="" if given else "words")
        story = rest.split()[0] if rest else ""
        return dict(kind="answer", fields=dict(story=story) if story else {}, words="", open="record")
    if head == "/dca-describe":
        return dict(kind="describe", fields={}, words=rest, open="" if rest else "words")
    if head == "/factory-discover":
        return dict(kind="discover", fields={}, words=rest, open="" if rest else "words")
    return None
