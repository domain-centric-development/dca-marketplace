"""The contexts as the project keeps them: the spec's folders (`<spec>/<context>/[<feature>/]scenarios.md`), each
context's `glossary.md`, and the designed domain's table of contexts (`## Bounded Contexts` in the description's
domain file) — read into the spec's model."""

from __future__ import annotations

import os
import re
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import place
from ....domain.model.context_spec import (
    ContextName, ContextSpec, Feature, Statement, Subdomain, Term, TermKind, TermName)
from ....domain.model.criterion import Criterion, CriterionKey, FeatureName, Form, Line, RuleText, Selector
from .spec_files import GLOSSARY_FILE, parse_spec, SCENARIOS_FILE

#: A row of the designed domain's context table: | `cart` | Shopping cart … | Core |
CONTEXT_ROW = re.compile(r"^\|\s*`?([A-Za-z][\w -]*?)`?\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$")
SECTION = re.compile(r"^##\s+(.+?)\s*$")
TERM = re.compile(r"^###\s+(.+?)\s*$")
TYPE = re.compile(r"^\*\*Type:\*\*\s*(.+?)\s*$")


def criterion_of(item: typing.Mapping[str, typing.Any], feature: str) -> Criterion:
    return Criterion(CriterionKey(item["key"]), RuleText(item["rule"]) if item.get("rule") else None,
                     Form(item["form"]), tuple(Line(line) for line in item["lines"]),
                     tuple(Selector(t) for t in item.get("tests") or ()), FeatureName(feature))


def designed(domain_file: str) -> typing.Dict[str, typing.Tuple[str, str]]:
    """{context: (what it is for, its subdomain)} from the table under `## Bounded Contexts`, in its order."""
    found: typing.Dict[str, typing.Tuple[str, str]] = {}
    inside = False
    for line in read_text(domain_file).splitlines() if os.path.isfile(domain_file) else []:
        heading = SECTION.match(line)
        if heading:
            inside = heading.group(1).strip().lower().startswith("bounded context")
            continue
        row = CONTEXT_ROW.match(line) if inside else None
        if row and not set(row.group(2)) <= set("-: ") and row.group(1).strip().lower() != "context":
            found[row.group(1).strip().lower()] = (row.group(2).strip(), row.group(3).strip())
    return found


def terms_of(glossary: str) -> typing.List[Term]:
    """Each `### term` of a glossary with its kind — its `**Type:**` line, else its section's heading — and its first
    paragraph as its meaning; a feature, an open question or a note is no term of the model."""
    found: typing.List[Term] = []
    section, name = "", ""
    kind: typing.Optional[TermKind] = None
    meaning: typing.List[str] = []
    ended = False

    def close() -> None:
        if name and kind is not None:
            found.append(Term(TermName(name), kind, Statement(" ".join(meaning))))

    lines = read_text(glossary).splitlines() if os.path.isfile(glossary) else []
    for line in lines:
        text = line.strip()
        heading, term = SECTION.match(line), TERM.match(line)
        if heading or term:
            close()
            if heading is not None:
                section, name, kind = heading.group(1), "", None
            elif term is not None:
                name, kind = term.group(1), TermKind.named(Statement(section))
            meaning, ended = [], False
            continue
        if not name:
            continue
        said = TYPE.match(text)
        if said:
            named = TermKind.named(Statement(said.group(1)))
            kind = named if named is not None else (None if "feature" in said.group(1).lower() else TermKind.OTHER)
        elif not text:
            ended = ended or bool(meaning)
        elif not ended and not text.startswith(("**", "|", "```", "-", ">", "#")):
            meaning.append(text)
    close()
    return found


class ContextSpecFiles:
    """The contexts of the project <cwd>."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def contexts(self) -> typing.Sequence[ContextSpec]:
        spec = os.path.join(self._cwd, place("spec"))
        table = designed(os.path.join(self._cwd, place("domain")))
        held = sorted(name for name in os.listdir(spec) if os.path.isdir(os.path.join(spec, name))) \
            if os.path.isdir(spec) else []
        names = list(table) + [name for name in held if name not in table]
        return [self._context(spec, name, table.get(name, ("", ""))) for name in names]

    def _context(self, spec: str, name: str, said: typing.Tuple[str, str]) -> ContextSpec:
        folder = os.path.join(spec, name)
        files = [("", os.path.join(folder, SCENARIOS_FILE))] if os.path.isfile(os.path.join(folder, SCENARIOS_FILE)) else []
        if os.path.isdir(folder):
            files += [(sub, os.path.join(folder, sub, SCENARIOS_FILE)) for sub in sorted(os.listdir(folder))
                      if os.path.isfile(os.path.join(folder, sub, SCENARIOS_FILE))]
        features = [Feature(FeatureName(feature), tuple(criterion_of(item, feature)
                                                      for item in parse_spec(read_text(path))[1]))
                    for feature, path in files]
        return ContextSpec(ContextName(name), Statement(said[0]), Subdomain(said[1]),
                           terms_of(os.path.join(folder, GLOSSARY_FILE)), features)
