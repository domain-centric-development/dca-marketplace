"""The project description: the product, the technical decisions, the designed domain — what every stage reads."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import DomainService, Value


class Part(enum.Enum):
    """A part of the project description, by the profile key that places it."""

    PRODUCT = "product"
    TECH = "tech"
    DOMAIN = "domain"


class Heading(Value):
    """A `## ` heading of a part, as written."""

    value: str

    def key(self) -> Heading:
        """The heading as it is matched: case does not count."""
        return Heading(self.value.lower())


#: The headings a part must fill — the product: what is built, for whom, through which surfaces; the technical
#: decisions: what a stage may not decide in passing. The designed domain has none the check holds it to.
REQUIRED: typing.Mapping[Part, typing.Tuple[Heading, ...]] = {
    Part.PRODUCT: tuple(Heading(h) for h in ("What and for whom", "Surfaces", "How it works", "Look and feel",
                                             "Qualities", "Not part of the product")),
    Part.TECH: tuple(Heading(h) for h in ("Stack", "Frontend approach", "Persistence", "Runtime", "Integrations",
                                          "Version policy")),
    Part.DOMAIN: (),
}


class Written(Value):
    """A part as it is written: its headings in order, and those whose section says something — guidance in comments
    says nothing."""

    headings: typing.Tuple[Heading, ...]
    filled: typing.FrozenSet[Heading]


class DescriptionRules(DomainService):
    """A part is done when every heading it requires is there and says something."""

    @staticmethod
    def missing(part: Part, written: Written) -> typing.List[Heading]:
        present = {h.key() for h in written.headings}
        return [h for h in REQUIRED[part] if h.key() not in present]

    @staticmethod
    def empty(part: Part, written: Written) -> typing.List[Heading]:
        present = {h.key() for h in written.headings}
        return [h for h in REQUIRED[part] if h.key() in present and h.key() not in written.filled]
