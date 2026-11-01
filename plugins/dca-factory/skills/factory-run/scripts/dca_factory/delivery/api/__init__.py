"""Delivery's open host service: what another context may ask delivery, in delivery's published terms."""

from __future__ import annotations

import os
import typing

from ...sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from ...sharedkernel.adapter.outgoing.profile.profile_files import place
from ..adapter.outgoing.files.epic_files import epic_holding
from ..adapter.outgoing.files.story_layout import story_files

#: A story's states that hold no change any more: delivered, adopted (it describes what holds), set aside.
CLOSED = ("delivered", "adopted", "superseded")


def epic_of_proposal(cwd: str, proposal: str) -> str:
    """The epic of the backlog that holds a proposal of discovery — '' where none does yet."""
    return epic_holding(os.path.join(cwd, place("epics")), proposal)


def open_stories(cwd: str) -> typing.List[typing.Dict[str, str]]:
    """Every story of the backlog not delivered and not set aside — {id, title, status, context, body}, as written; a
    story file that does not read is left out (the backlog view names it)."""
    found = []
    for path in story_files(os.path.join(cwd, place("epics"))):
        try:
            front, body = read_front_matter(path)
        except MarkdownError:
            continue
        status = str(front.get("status") or "").strip()
        if status in CLOSED:
            continue
        found.append(dict(id=str(front.get("id") or os.path.basename(os.path.dirname(path))).strip(),
                          title=str(front.get("title") or "").strip(), status=status,
                          context=str(front.get("context") or "").strip(), body=body))
    return found
