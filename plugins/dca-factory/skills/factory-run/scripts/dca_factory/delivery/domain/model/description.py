"""The project description: the product, the technical decisions, the designed domain — what every stage reads."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value


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


class Body(Value):
    """What a section of a part says, as written — guidance in comments left out."""

    value: str


class Section(Value):
    """One `## ` section of a part: its heading and what it says."""

    heading: Heading
    body: Body


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

    def missing(self, part: Part) -> typing.List[Heading]:
        """The headings the part requires that are not there — a part is done when every one is there and says
        something."""
        present = {h.key() for h in self.headings}
        return [h for h in REQUIRED[part] if h.key() not in present]

    def empty(self, part: Part) -> typing.List[Heading]:
        """The headings the part requires that are there and say nothing."""
        present = {h.key() for h in self.headings}
        return [h for h in REQUIRED[part] if h.key() in present and h.key() not in self.filled]
