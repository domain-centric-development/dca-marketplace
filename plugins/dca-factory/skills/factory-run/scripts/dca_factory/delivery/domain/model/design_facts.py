"""The design a story is held to: the context map, the rules of its elements, its invariants and ports."""

from __future__ import annotations

import typing

from ....building_blocks import Value
from .schedule import ContextName
from .story_state import Detail
from .story_words import Count, Place, Selector


class ContextMapFacts(Value):
    """The context map a story's context is looked up on: the designed map's file where the profile names one that
    is not there, the map found, and the names it gives."""

    domain_missing: typing.Optional[Place]
    map: typing.Optional[Place]
    names: typing.FrozenSet[ContextName]


class ElementName(Value):
    """A domain type the plan names — `Task`, `TaskTitle`."""

    value: str


class Rule(Value):
    """One invariant of a domain type, as the plan words it — a guard included."""

    value: str


class ElementRules(Value):
    """A domain type's line under the plan's `## Invariants`: its rules, none where it says why it has none."""

    element: ElementName
    rules: typing.Tuple[Rule, ...]


class InvariantRow(Value):
    """A row of the tests' `gate:invariants` table: the type, the rule numbers it covers, and its unit test — the
    selector where one is written as `<Class>#<method>`, the text where it is not."""

    element: ElementName
    numbers: typing.Tuple[Count, ...]
    selector: typing.Optional[Selector]
    malformed: typing.Optional[Detail]


class InvariantFacts(Value):
    """What the plan says of the domain types it changes, and the tests' table of their rules."""

    listed: Count
    elements: typing.Tuple[ElementName, ...]
    named: typing.Tuple[ElementRules, ...]
    rows: typing.Optional[typing.Tuple[InvariantRow, ...]]


class PortName(Value):
    """A port type a test declares as a double."""

    value: str
