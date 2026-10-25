"""The epics as folders: `<epics>/<epic>/epic.md` beside its story folders."""

from __future__ import annotations

import contextlib
import os
import typing

from .....contract import place
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from ....domain.model.epic import EpicId


def epic_dir(epics: str, epic_id: str) -> typing.Optional[str]:
    """The folder of the epic with this id — its folder's name or its `id:` — or None."""
    if not os.path.isdir(epics):
        return None
    for name in sorted(os.listdir(epics)):
        path = os.path.join(epics, name, "epic.md")
        if not os.path.isfile(path):
            continue
        if name.lower() == epic_id.lower():
            return os.path.dirname(path)
        with contextlib.suppress(MarkdownError):
            if str(read_front_matter(path)[0].get("id", "")).strip().lower() == epic_id.lower():
                return os.path.dirname(path)
    return None


class EpicFiles:
    """The epic catalog as folders, under the project the process works in."""

    def __init__(self, cwd: str) -> None:
        self._epics = os.path.join(cwd, place("epics"))

    def exists(self, epic: EpicId) -> bool:
        return epic_dir(self._epics, epic.value) is not None

    def where(self) -> str:
        return str(place("epics"))
