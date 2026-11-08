"""A file a person hands over beside their words (WP-184): a picture, a PDF or a text — what the factory takes, how
large, how many, under which name, and what it is known by once kept.

The rules are the domain's: an adapter only keeps the bytes somewhere — a folder of the project today, a server
tomorrow — and answers by the `HandedFileRef` it was given.
"""

from __future__ import annotations

import re
import typing

from ....building_blocks import Id, Value
from .words import CONTROL

MAX_BYTES = 10 * 1024 * 1024
MAX_FILES = 5
#: How long a kept file stays once no request names it, in days.
KEEP_DAYS = 14
#: The kinds a person may hand over, each with the extension its name gets.
KINDS = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp", "application/pdf": "pdf",
         "text/plain": "txt", "text/markdown": "md", "text/csv": "csv", "application/json": "json"}
TEXT_EXTENSIONS = {"txt": "text/plain", "md": "text/markdown", "csv": "text/csv", "json": "application/json"}
FILE_ID = re.compile(r"^f[0-9a-f]{16}$")


class FileBytes(Value):
    """The content of a file, as its bytes."""

    value: bytes


class FileRefused(ValueError):
    """A file the factory does not take: its kind, its size, its number, or nothing in it."""


class FileName(Value):
    """A file's name — as a person gave it, or as the factory keeps it."""

    value: str

    @property
    def extension(self) -> "FileName":
        base = self.base.value
        return FileName(base.rsplit(".", 1)[-1].lower() if "." in base else "")

    @property
    def base(self) -> "FileName":
        """The name without any folder before it, whichever slash a system wrote."""
        return FileName(self.value.replace("\\", "/").rsplit("/", 1)[-1])


class FileKind(Value):
    """What a file is — one of the kinds the factory takes, or `html` for a mockup it shows."""

    value: str

    @property
    def picture(self) -> bool:
        return self.value.startswith("image/")

    @property
    def text(self) -> bool:
        return self.value.startswith("text/") or self.value == "application/json"


class ByteSize(Value):
    """How large a file is, in bytes."""

    value: int

    def __str__(self) -> str:
        return f"{max(1, self.value // 1024)} KB"


class HandedFileId(Id):
    """A kept file's id — the factory's own, never a path a person chose."""

    value: str

    def __post_init__(self) -> None:
        if not FILE_ID.match(self.value):
            raise FileRefused(f"{self.value!r} is no handed file's id")

    @staticmethod
    def fresh(entropy: bytes) -> "HandedFileId":
        """A new id from eight random bytes the caller drew — the factory's form, never a name a person gave."""
        if len(entropy) != 8:
            raise FileRefused("a handed file's id is drawn from eight bytes")
        return HandedFileId("f" + entropy.hex())


def kind_of(data: bytes, name: FileName) -> typing.Optional[FileKind]:
    """What a file is, by its content — the name decides only between the text kinds. SVG and HTML are no kind a
    person hands over: they carry script."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return FileKind("image/png")
    if data.startswith(b"\xff\xd8\xff"):
        return FileKind("image/jpeg")
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return FileKind("image/gif")
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return FileKind("image/webp")
    if data.startswith(b"%PDF-"):
        return FileKind("application/pdf")
    extension = name.extension.value or "txt"
    if extension not in TEXT_EXTENSIONS:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if CONTROL.search(text) or re.search(r"<\s*(script|svg|html)\b", text[:4096], re.IGNORECASE):
        return None
    return FileKind(TEXT_EXTENSIONS[extension])


class HandedFile(Value):
    """One file as a person handed it over: its name as they gave it and its bytes — taken only as one of our kinds,
    not empty, at most `MAX_BYTES`."""

    given_name: FileName
    data: FileBytes

    def __post_init__(self) -> None:
        if not self.data.value:
            raise FileRefused("the file is empty")
        if len(self.data.value) > MAX_BYTES:
            raise FileRefused(f"a file is at most {MAX_BYTES // (1024 * 1024)} MB")
        if not kind_of(self.data.value, self.given_name):
            raise FileRefused("a picture (png, jpg, gif, webp), a PDF or a text (txt, md, csv, json) — not this one")

    @property
    def kind(self) -> FileKind:
        return typing.cast(FileKind, kind_of(self.data.value, self.given_name))

    @property
    def name(self) -> FileName:
        """The name it is kept under: the person's, reduced to what no path can misread, the extension its kind's."""
        base = self.given_name.base.value
        stem = base.rsplit(".", 1)[0] if "." in base else base
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-_")[:60] or "file"
        return FileName(f"{stem}.{KINDS[self.kind.value]}")

    @property
    def size(self) -> ByteSize:
        return ByteSize(len(self.data.value))


class HandedFileRef(Value):
    """A kept file as the factory names it: its id, its name, kind and size."""

    id: HandedFileId
    name: FileName
    kind: FileKind
    size: ByteSize


class HandedFiles(Value):
    """The files that go with one request — at most `MAX_FILES`."""

    files: typing.Tuple[HandedFile, ...]

    def __post_init__(self) -> None:
        if len(self.files) > MAX_FILES:
            raise FileRefused(f"at most {MAX_FILES} files go with a request")

    @property
    def any(self) -> bool:
        return bool(self.files)
