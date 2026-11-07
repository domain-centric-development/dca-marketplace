"""What a request wrote, read back as the backlog's: a story's or a task's file, an epic's, a findings file."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from ....application.shared.requests import MadeItems

#: The file names that are a backlog item, and the kind each is where its front matter names none.
ITEM_FILES = {"story.md": "story", "epic.md": "epic", "findings.md": "finding"}


class MadeItemFiles(MadeItems):
    """The items at the paths a request wrote, relative to <cwd>."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def at(self, paths: typing.Sequence[str]) -> typing.List[typing.Dict[str, str]]:
        items = []
        for path in paths:
            name = os.path.basename(path)
            if name not in ITEM_FILES:
                continue
            folder = os.path.basename(os.path.dirname(path))
            try:
                front, _ = read_front_matter(os.path.join(self._cwd, path))
            except (MarkdownError, OSError, UnicodeDecodeError):
                front = {}
            kind = ITEM_FILES[name] if name != "story.md" else str(front.get("kind") or "story")
            title = f"a finding beside {folder} settled" if kind == "finding" else str(front.get("title") or folder)
            items.append(dict(kind=kind, id=str(front.get("id") or folder), title=title,
                              status=str(front.get("status") or ""), path=path))
        return items
