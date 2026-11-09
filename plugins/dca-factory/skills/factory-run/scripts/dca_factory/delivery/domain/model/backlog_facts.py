"""The backlog's facts a gate reads: the story's epic and outcome, its findings, its decisions and proposals."""

from __future__ import annotations

import typing

from ....building_blocks import Value
from .decision_record import RecordId
from .epic import EpicId
from .profile_facts import ProfileText
from .stage import StageName
from .story_state import Detail, HandOverText
from .story_words import Count, EventName, Place, Presence


class RowState(Value):
    """Where a finding row stands: `open`, or what closed it."""

    value: str


#: A finding row nobody closed yet — the only one a task may close; its delivery sets the row to DONE_ROW.
OPEN_ROW = RowState("open")


DONE_ROW = RowState("done")


class FindingKey(Value):
    """What makes a kept finding the same as another: where it is (`file:line`) and the defect it names. A delivery
    keeps each finding not kept already — the same place and defect is one finding, however often a later round
    confirms it."""

    place: Place
    defect: Detail


class EpicField(Value):
    """A mandatory field of an epic's front matter."""

    value: str


class Metric(Value):
    """An epic's `metric:` — the outcome event that measures it."""

    value: str


class EpicFacts(Value):
    """A story's epic: its file and name, the mandatory fields it lacks, the discovery report it names and lacks, why
    its dependencies do not hold, and its metric — or why the story names no epic there is."""

    place: Place
    name: EpicId
    missing: typing.Tuple[EpicField, ...]
    discovery_missing: typing.Optional[ProfileText]
    dependency_problem: typing.Optional[Detail]
    metric: Metric
    unreadable: typing.Optional[Detail] = None


class HandOverAsk(Value):
    """A stage's hand-over as the decisions check reads it: its text, and the records its `## needs-human` names —
    None where it escalates nothing, none where it escalates without naming one."""

    stage: StageName
    place: Place
    text: HandOverText
    asks: typing.Optional[typing.Tuple[RecordId, ...]]


class DecisionsFacts(Value):
    """The store of the story's decision records, and the stages' hand-overs — or why the store cannot be read. The
    records themselves are aggregates, read on their own (`StageEvidence.decision_records`)."""

    store: Place
    hand_overs: typing.Tuple[HandOverAsk, ...]
    unreadable: typing.Optional[Detail] = None


class DecidedRecord(Value):
    """An answered decision about tests: the stage that asked it, and its text."""

    record: RecordId
    stage: typing.Optional[StageName]
    text: Detail


class ProposalFacts(Value):
    """The terms the plan proposed, whether the project keeps a glossary, and the terms neither in one nor named
    open."""

    proposed: Count
    glossary: Presence
    missing: typing.Tuple[Detail, ...]


class OutcomeEventPlaces(Value):
    """An outcome event the story publishes: the production files that declare it, and those that raise it."""

    event: EventName
    declared: typing.Tuple[Place, ...]
    raising: typing.Tuple[Place, ...]


class OutcomeFacts(Value):
    """The story's outcome events in the production code, and the files the story changed — None where no record
    says."""

    events: typing.Tuple[OutcomeEventPlaces, ...]
    changed: typing.Optional[typing.FrozenSet[Place]]
