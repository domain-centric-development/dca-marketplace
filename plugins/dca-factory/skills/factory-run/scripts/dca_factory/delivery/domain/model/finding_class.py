"""A confirmed finding's class, in the shape of Orthogonal Defect Classification's closer: what had to change (target),
what kind of correction (type), and whether something was missing, wrong or too much (qualifier). Three short closed
lists the judge picks from; the gate checks them, the lessons count them. Counted, never guessed: a class nobody wrote
is no class."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import Value
from .story_words import Detail


def written(cls: typing.Any, word: Detail) -> typing.Any:
    """The member a cell names, case and back ticks aside — None for a word outside the list."""
    said = word.value.strip().strip("`").strip().lower()
    return next((member for member in cls if member.value == said), None)


class FindingTarget(enum.Enum):
    """What has to change to correct the finding."""

    STORY = "story"
    PLAN = "plan"
    CODE = "code"
    TEST = "test"
    DOCS = "docs"
    GLOSSARY = "glossary"
    PROFILE = "profile"

    @classmethod
    def written(cls, word: Detail) -> typing.Optional[FindingTarget]:
        return written(cls, word)


class FindingType(enum.Enum):
    """The kind of correction: ODC's types, the maintainability types a review finds, traceability between test,
    scenario and criterion, and the method's domain codes."""

    ASSIGNMENT = "assignment"
    CHECKING = "checking"
    ALGORITHM = "algorithm"
    INTERFACE = "interface"
    RELATIONSHIP = "relationship"
    TIMING = "timing"
    DOCUMENTATION = "documentation"
    DUPLICATION = "duplication"
    NAMING = "naming"
    DEAD_CODE = "dead-code"
    COMMENT = "comment"
    #: a test, a scenario and a criterion that do not lead to one another — a test title no scenario has, a scenario
    #: no test proves
    TRACEABILITY = "traceability"
    DOMAIN_CONCEPT = "domain-concept"
    DOMAIN_BOUNDARY = "domain-boundary"
    DOMAIN_INVARIANT = "domain-invariant"
    DOMAIN_TERM = "domain-term"

    @classmethod
    def written(cls, word: Detail) -> typing.Optional[FindingType]:
        return written(cls, word)


class FindingQualifier(enum.Enum):
    """Whether the correction adds what was missing, changes what was wrong, or removes what was too much."""

    MISSING = "missing"
    INCORRECT = "incorrect"
    EXTRANEOUS = "extraneous"

    @classmethod
    def written(cls, word: Detail) -> typing.Optional[FindingQualifier]:
        return written(cls, word)


class FindingClass(Value):
    """The three attributes of one finding."""

    target: FindingTarget
    type: FindingType
    qualifier: FindingQualifier

    @classmethod
    def written(cls, target: Detail, kind: Detail, qualifier: Detail) -> typing.Optional[FindingClass]:
        """The class three cells name — None where one of them is missing or outside its list."""
        found = (FindingTarget.written(target), FindingType.written(kind), FindingQualifier.written(qualifier))
        return cls(*found) if all(f is not None for f in found) else None  # type: ignore[arg-type]

    def keys(self, perspective: Detail) -> typing.Tuple[Detail, Detail]:
        """The two levels it is counted on, finest first: `<perspective>/<target>/<type>/<qualifier>`, then
        `<target>/<type>`."""
        return (Detail(f"{perspective.value}/{self.target.value}/{self.type.value}/{self.qualifier.value}"),
                Detail(f"{self.target.value}/{self.type.value}"))
