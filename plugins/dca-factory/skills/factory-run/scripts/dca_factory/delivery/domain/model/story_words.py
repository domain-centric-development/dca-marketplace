"""The words a story's file is read into: small values with no rule of their own, which the story, the gate's
evidence and the schedule share — a leaf the other modules of the model import."""

from __future__ import annotations

import typing

from ....building_blocks import Value


class Detail(Value):
    """Why a story stands where it stands, for a person — "" where nothing needs saying."""

    value: str


class StatusWord(Value):
    """A story's `status:` as it is written, lower case — `approved`, `adopted`, `draft`, or a word nobody knows."""

    value: str


class Count(Value):
    value: int


class ScenarioKey(Value):
    """A criterion's key — the name the test stage binds."""

    value: str


class RowId(Value):
    """A finding row a task closes: `<story>#<n>`, or `<name>#<n>` of a project finding file."""

    value: str


class EventName(Value):
    """An outcome event, as a story's `publishes:` names it."""

    value: str


class Clause(Value):
    """An expectation of a scenario — its `Then` or an `And`/`But` after it — numbered from 1."""

    number: Count
    text: Detail


class ScenarioClauses(Value):
    """A scenario's expectations, and its `When` steps — what the person does or enters."""

    key: ScenarioKey
    clauses: typing.Tuple[Clause, ...]
    actions: typing.Tuple[Detail, ...]


class ContextName(Value):
    """The bounded context a story changes, as its `context:` names it — "" where it names none."""

    value: str
