"""A project file the page shows (WP-184): a picture, a PDF or a text a record, a report or a story names, or a mockup
an option shows — which paths may be shown at all, and as what.

Where the bytes come from is an adapter's: it resolves the path, keeps it inside the places named here and reads.
"""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .handed_file import MAX_BYTES, FileKind, FileName, kind_of
from .project_path import ProjectPath

#: A mockup is one static page, small.
MOCKUP_BYTES = 512 * 1024


class Refusal(enum.Enum):
    """Why a file is not shown — the page's server says it in its own protocol."""

    FORM = "form"           # a path of the wrong form
    NOTHING = "nothing"     # nothing there to show
    TOO_LARGE = "too-large"
    KIND = "kind"           # none of the kinds the page shows


#: Where the project's description and backlog lie — one of the two places a file is shown from.
PRODUCT = ProjectPath("product")


def shown_places(factory: ProjectPath) -> typing.Tuple[ProjectPath, ...]:
    """The places a file is shown from: the project's description and backlog, and the factory's own folder."""
    return PRODUCT, factory


class FileNotShown(ValueError):
    """A path the page may not show, or a file that is none of the kinds it shows."""

    def __init__(self, refusal: Refusal, message: str) -> None:
        super().__init__(message)
        self.refusal = refusal


class ShownAs(enum.Enum):
    FILE = "file"       # a picture, a PDF or a text, as what it is
    PAGE = "page"       # a mockup, a page of its own in a frame that runs no script


class ShownPath(Value):
    """A path in the project the page asked to show: relative, without `..`, beneath one of the places a file is
    shown from — the project's description and backlog (`product/`) and the factory's own folder."""

    path: ProjectPath
    places: typing.Tuple[ProjectPath, ...]

    def __post_init__(self) -> None:
        given = self.path.value
        parts = given.replace("\\", "/").split("/")
        if not given or "\0" in given or given.startswith(("/", "\\")) or ":" in parts[0] or ".." in parts:
            raise FileNotShown(Refusal.FORM, "a file is named by its path in the project")
        if not any(given.startswith(place.value.rstrip("/") + "/") for place in self.places):
            raise FileNotShown(Refusal.NOTHING, "no such file beneath product/ or the factory's folder")

    @property
    def mockup(self) -> bool:
        """A mockup is a page in a decision record's own folder — `…/decisions/<nn>/<name>.html` — or in a `mockups/`
        folder beside a discovery's report or a story."""
        parts = self.path.value.split("/")
        return self.path.value.lower().endswith(".html") and len(parts) >= 3 \
            and (parts[-3] == "decisions" or "mockups" in parts[:-1])

    @property
    def name(self) -> FileName:
        return FileName(self.path.value).base


class ShownFile(Value):
    """What the page shows of a path: its kind, its bytes and how — a mockup as a page of its own, anything else
    only as a picture, a PDF or a text."""

    kind: FileKind
    data: bytes
    shown_as: ShownAs

    @staticmethod
    def of(path: ShownPath, data: bytes) -> "ShownFile":
        if path.mockup:
            if len(data) > MOCKUP_BYTES:
                raise FileNotShown(Refusal.TOO_LARGE, "a mockup is at most 512 KB")
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                raise FileNotShown(Refusal.KIND, "a mockup is a page in UTF-8") from None
            return ShownFile(FileKind("text/html"), data, ShownAs.PAGE)
        if len(data) > MAX_BYTES:
            raise FileNotShown(Refusal.TOO_LARGE, "a file shown is at most 10 MB")
        kind = kind_of(data, path.name)
        if not kind:
            raise FileNotShown(Refusal.KIND, "a picture, a PDF or a text is shown — not this file")
        return ShownFile(kind, data, ShownAs.FILE)
