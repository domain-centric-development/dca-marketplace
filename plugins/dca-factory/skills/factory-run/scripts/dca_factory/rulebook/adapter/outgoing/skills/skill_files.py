"""The skills' text as the rulebook reads it: every rule id it names is a citation the rulebook checks, and a paragraph
still marked `<!-- rule: STAGE-PLAN-9A -->` on the line before it is a told rule's copy — a problem, since its words
stand in its rule file, placed by its stage's frame."""

from __future__ import annotations

import os
import re
import typing

from ....domain.model.rule import (
    Citation, KindName, Part, Rule, RuleId, Source, StageName, Words)
from ....application.shared.instructed_rules import InstructedRules

MARKER = re.compile(r"^\s*<!--\s*rule:\s*(\S+)\s*-->\s*$")
CITED = re.compile(r"(?<![\w-])(?:GATE|RUN|STAGE)(?:-[A-Z0-9]+)+(?![\w-])")
HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
NUMBERED = re.compile(r"^\s*(?:\d+[a-z]?\.|[-*])\s+")
#: The areas of a STAGE- id that are no stage: what every stage is told, the files they hand over, the backlog.
EVERY_STAGE = ("common", "files", "backlog")
#: The last part of an id that names the story kind a paragraph holds for: a skill's `## Task mode`, `## Adopt mode`.
MODES = ("task", "adopt")
#: The skills folder of the plugin beside the package, then the project's tool folders — the first that has the
#: factory's reference.
TOOL_FOLDERS = (".claude/skills", ".agents/skills", ".codex/skills", ".opencode/skills")
REFERENCE = os.path.join("factory-run", "reference", "file-contracts.md")


def skills_folder(cwd: str, package: str) -> typing.Optional[str]:
    """Where the skills are: the plugin's folder above the package, else a tool folder of the project."""
    beside = os.path.abspath(os.path.join(package, "..", "..", ".."))
    for folder in [beside] + [os.path.join(cwd, f) for f in TOOL_FOLDERS]:
        if os.path.isfile(os.path.join(folder, REFERENCE)):
            return folder
    return None


def indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def plain(paragraph: str) -> str:
    """A paragraph as one line: the list mark, the emphasis and the line breaks taken out — how the rulebook shows it
    and compares a skill's words with its rule file."""
    lines = paragraph.splitlines()
    text = " ".join(NUMBERED.sub("", line, count=1).strip() if i == 0 else line.strip() for i, line in enumerate(lines))
    text = re.sub(r"\*\*|__", "", text)
    return re.sub(r"\s+", " ", text).strip()


class SkillFiles(InstructedRules):
    """The markdown of every skill under <folder> — none where no folder was found."""

    def __init__(self, folder: typing.Optional[str]) -> None:
        self._folder = folder
        self._read: typing.Optional[typing.Tuple[typing.Tuple[Rule, ...], typing.Tuple[Citation, ...]]] = None

    def where(self) -> str:
        return self._folder or ""

    def rules(self) -> typing.Tuple[Rule, ...]:
        return self._parsed()[0]

    def citations(self) -> typing.Tuple[Citation, ...]:
        return self._parsed()[1]

    def _files(self) -> typing.List[str]:
        if not self._folder:
            return []
        found = []
        for top, dirs, files in os.walk(self._folder):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in ("scripts", "templates", "catalog"))
            found += [os.path.join(top, name) for name in sorted(files) if name.endswith(".md")]
        return found

    def _parsed(self) -> typing.Tuple[typing.Tuple[Rule, ...], typing.Tuple[Citation, ...]]:
        if self._read is None:
            rules: typing.List[Rule] = []
            citations: typing.List[Citation] = []
            for path in self._files():
                found, cited = self._read_file(path)
                rules += found
                citations += cited
            self._read = (tuple(rules), tuple(citations))
        return self._read

    def _read_file(self, path: str) -> typing.Tuple[typing.List[Rule], typing.List[Citation]]:
        assert self._folder is not None
        shown = os.path.relpath(path, self._folder).replace(os.sep, "/")
        skill = os.path.basename(shown) if "/reference/" in shown else shown.split("/")[0]
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        rules: typing.List[Rule] = []
        citations: typing.List[Citation] = []
        heading, fenced = "", False
        for index, line in enumerate(lines):
            if line.lstrip().startswith("```"):
                fenced = not fenced
            found = HEADING.match(line) if not fenced else None
            if found:
                heading = found.group(2).strip()
            marked = MARKER.match(line)
            if marked is None:
                citations += [Citation(Words(cited), Source(f"{shown}:{index + 1}")) for cited in CITED.findall(line)]
                continue
            paragraph: typing.List[str] = []
            for following in lines[index + 1:]:
                if not following.strip() or MARKER.match(following) or HEADING.match(following):
                    break
                if paragraph and NUMBERED.match(following) and indent(following) <= indent(paragraph[0]):
                    break      # the next item of the same list is a paragraph of its own
                paragraph.append(following)
            rule_id = marked.group(1)
            try:
                checked = RuleId(rule_id)
            except ValueError:
                citations.append(Citation(Words(rule_id), Source(f"{shown}:{index + 1}")))
                continue
            area = checked.area().value.lower()
            mode = checked.value.rsplit("-", 1)[-1].lower()
            rules.append(Rule(
                checked, Part.INSTRUCTION, () if area in EVERY_STAGE else (StageName(area),),
                (KindName(mode),) if mode in MODES else (),
                Words(f"{skill} — {heading}" if heading else skill), (), Words(""), Words(plain("\n".join(paragraph))), (),
                Source(f"{shown}:{index + 2}")))
        return rules, citations

