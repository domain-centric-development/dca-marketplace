"""The discovery reports as files: `<discovery>/<topic>/discovery.md`, the excerpts it cites beside it, its
`.gitignore` keeping the handed-over originals out of git."""

from __future__ import annotations

import os
import re
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from ....domain.model.report import DESCRIPTION_CHANGES, Item, PROPOSED_WORK, Report, SourceId, Text, Topic

REPORT_FILE = "discovery.md"
SOURCE_LINE = re.compile(r"^\s*-\s*\[(S\d+)\]\s*(.+?)\s*$")
CITATION = re.compile(r"\[(S\d+)\]")


def discovery_items(text: str, section: str) -> typing.List[typing.Tuple[str, typing.Dict[str, str]]]:
    """The `### <name>` blocks of one `## <section>` of a discovery report: [(name, {field: value})]."""
    marker = f"\n## {section}"
    if marker not in text:
        return []
    body = text.split(marker, 1)[1].split("\n## ", 1)[0]
    return [(item.splitlines()[0].strip(),
             {k.lower(): v for k, v in re.findall(r"^\s*-\s*([A-Za-z_]+):\s*(.*?)\s*$", item, re.M)})
            for item in re.split(r"^### ", body, flags=re.M)[1:]]


def parse(text: str) -> Report:
    """The report as written."""
    sources: typing.Dict[SourceId, Text] = {}
    for line in section_of(text, "sources") or []:
        match = SOURCE_LINE.match(line)
        if match:
            sources[SourceId(match.group(1))] = Text(match.group(2))

    def items(section: str) -> typing.Tuple[Item, ...]:
        return tuple(Item(Text(name), {Text(k): Text(v) for k, v in fields.items()})
                     for name, fields in discovery_items(text, section))
    return Report(headings=tuple(Text(h.strip()) for h in re.findall(r"^## (.+)$", text, re.M)), sources=sources,
                  cited=frozenset(SourceId(c) for c in CITATION.findall(text.split("\n## Sources", 1)[0])),
                  proposals=items(PROPOSED_WORK), changes=items(DESCRIPTION_CHANGES))


class ReportFiles:
    """The report store as files, under the project <cwd>, in the discovery folder <folder> the profile names."""

    def __init__(self, cwd: str, folder: str) -> None:
        self._cwd = cwd
        self._folder = folder.replace(os.sep, "/")

    def where(self) -> str:
        return self._folder

    def topics(self) -> typing.List[Topic]:
        root = os.path.join(self._cwd, self._folder)
        if not os.path.isdir(root):
            return []
        return [Topic(name) for name in sorted(os.listdir(root)) if os.path.isfile(os.path.join(root, name, REPORT_FILE))]

    def report_path(self, topic: Topic) -> str:
        return f"{self._folder}/{topic.value}/{REPORT_FILE}"

    def read(self, topic: Topic) -> typing.Optional[Report]:
        text = self.text(topic)
        return parse(text) if text is not None else None

    def title(self, topic: Topic) -> str:
        found = re.search(r"^# (?:Discovery:\s*)?(.+)$", self.text(topic) or "", re.M)
        return found.group(1).strip() if found else topic.value

    def resolves(self, topic: Topic, path: str) -> bool:
        return os.path.isfile(os.path.join(self._cwd, self._folder, topic.value, path)) \
            or os.path.isfile(os.path.join(self._cwd, path))

    def ignores_originals(self, topic: Topic) -> bool:
        ignore = os.path.join(self._cwd, self._folder, topic.value, ".gitignore")
        return os.path.isfile(ignore) and re.search(r"^/?originals/?\s*$", read_text(ignore), re.M) is not None

    def text(self, topic: Topic) -> typing.Optional[str]:
        path = os.path.join(self._cwd, self.report_path(topic))
        return read_text(path) if os.path.isfile(path) else None
