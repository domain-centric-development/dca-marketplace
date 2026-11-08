"""The words a story's file is read into: small values with no rule of their own, which the story, the gate's
evidence and the schedule share — a leaf the other modules of the model import."""

from __future__ import annotations

import typing

from ....building_blocks import Value
from .verdict import CheckName, Findings, Said


class Detail(Value):
    """Why a story stands where it stands, for a person — "" where nothing needs saying."""

    value: str


class Place(Value):
    """A file as the gate names it — where a person finds what a finding speaks of."""

    value: str


class StatusWord(Value):
    """A story's `status:` as it is written, lower case — `approved`, `adopted`, `draft`, or a word nobody knows."""

    value: str

    def release_findings(self, place: Place) -> Findings:
        """A draft is a story still being written: named, not refused. A status nobody knows is refused."""
        if self.value == "draft":
            return (CheckName("approved").note(Said(f"{place.value}: a draft — released with `status: approved` once it is "
                                       f"written")),)
        if self.value and self.value not in ("approved", "adopted"):
            return (CheckName("approved").fail(Said(f"{place.value}: status {self.value!r} is none of draft, approved, adopted, "
                                       f"superseded")),)
        return ()


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
