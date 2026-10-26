"""A discovery report: its sections, the sources it cites, the work and the description changes it proposes."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService, Id, Value

#: The sections of a report, in their order.
SECTIONS = ("Problem", "Users and evidence", "Options", "Outcome", "Risks and open questions", "Proposed work",
            "Sources")

#: The section that proposes bodies of work.
PROPOSED_WORK = "Proposed work"

#: An optional section between the proposed work and the sources: a change the findings make to the project
#: description, one `### <file> — <section>` each with `- change:`. Discover writes it, never the description:
#: a released change goes through the description skill.
DESCRIPTION_CHANGES = "Proposed description changes"

#: The fields every proposed body of work carries before it can become an epic; `domain_contact` may stay `open`.
FIELDS = ("intent", "goal", "metric")

#: The parts of the project description a change may name.
DESCRIPTION_FILES = ("overview.md", "tech.md", "domain.md")


class Topic(Id):
    """What a discovery is about — the name of its folder."""

    value: str


class Text(Value):
    """A heading, a name, a field's text, as the report writes it."""

    value: str


class SourceId(Value):
    """A source as the report cites it — `S1`, `S12`."""

    value: str

    def number(self) -> Count:
        return Count(int(self.value[1:]))


class Count(Value):
    """A number of things."""

    value: int


class Item(Value):
    """One `### <name>` block of a section: its name and its `- <field>: <text>` lines."""

    name: Text
    fields: typing.Mapping[Text, Text]

    def field(self, name: Text) -> Text:
        return self.fields.get(name, Text(""))


class Report(Value):
    """A report as written: its `## ` headings in order, the sources it lists, the ones its text cites, and the items
    of its proposed work and its proposed description changes."""

    headings: typing.Tuple[Text, ...]
    sources: typing.Mapping[SourceId, Text]
    cited: typing.FrozenSet[SourceId]
    proposals: typing.Tuple[Item, ...]
    changes: typing.Tuple[Item, ...]


class Problem(Value):
    """What is wrong with a report, in one sentence."""

    value: str


class ReportRules(DomainService):
    """What a report must hold: its sections in order, a source for every citation, every proposed body of work with
    intent, goal and metric, every description change naming its part and the change."""

    @staticmethod
    def sections(report: Report) -> typing.List[Problem]:
        """The sections present and in order, and a source listed for every citation."""
        problems = []
        headings = [h.value for h in report.headings]
        missing = [h for h in SECTIONS if h not in headings]
        order = [h for h in headings if h in SECTIONS]
        if missing:
            problems.append(Problem("missing " + ", ".join(f"`## {h}`" for h in missing)))
        elif order != list(SECTIONS):
            problems.append(Problem("the sections are out of order — " + " → ".join(SECTIONS)))
        unknown = sorted(report.cited - set(report.sources), key=lambda c: c.number().value)
        if unknown:
            problems.append(Problem("cited but not under `## Sources`: " + ", ".join(f"[{c.value}]" for c in unknown)))
        return problems

    @staticmethod
    def proposals(report: Report) -> typing.List[Problem]:
        """Every proposed body of work complete, every description change in its place and complete."""
        problems = []
        headings = [h.value for h in report.headings]
        if PROPOSED_WORK in headings and not report.proposals:
            problems.append(Problem("`## Proposed work` proposes nothing — one `### <id>` per body of work, or a line "
                                    "saying why none"))
        for item in report.proposals:
            lacking = [f for f in FIELDS if not item.field(Text(f)).value
                       or item.field(Text(f)).value.lower() == "open" or "{{" in item.field(Text(f)).value]
            if lacking:
                problems.append(Problem(f"proposed `{item.name.value}` lacks {', '.join(lacking)}"))
        if DESCRIPTION_CHANGES in headings:
            # the position is a finding only when both neighbours are there — a missing one is reported above
            if PROPOSED_WORK in headings and "Sources" in headings and \
                    not headings.index(PROPOSED_WORK) < headings.index(DESCRIPTION_CHANGES) < headings.index("Sources"):
                problems.append(Problem(f"`## {DESCRIPTION_CHANGES}` stands between `## Proposed work` and "
                                        "`## Sources`"))
            if not report.changes:
                problems.append(Problem(f"`## {DESCRIPTION_CHANGES}` proposes nothing — one `### <file> — <section>` "
                                        f"per change, or leave the section out"))
            for item in report.changes:
                if not any(item.name.value.startswith(f) for f in DESCRIPTION_FILES):
                    problems.append(Problem(f"description change `{item.name.value}` names none of "
                                            f"{', '.join(DESCRIPTION_FILES)} — `### <file> — <section>`"))
                if not item.field(Text("change")).value or "{{" in item.field(Text("change")).value:
                    problems.append(Problem(f"description change `{item.name.value}` says no `- change:`"))
        return problems
