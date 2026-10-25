"""The story as a stage's gate reads it, and the facts its checks are handed."""

from __future__ import annotations

import dataclasses
import typing

from ....building_blocks import Value
from .decision_record import DecisionState, RecordId, RecordKind
from .epic import EpicId
from .schedule import ContextName
from .stage import StageName, StoryKind
from .story import DeliveredOn, StoryId
from .story_state import Detail, HandOverText, Rounds, StatusWord


@dataclasses.dataclass(frozen=True)
class Place(Value):
    """A file as the gate names it — where a person finds what a finding speaks of."""

    value: str


@dataclasses.dataclass(frozen=True)
class ScenarioKey(Value):
    """A criterion's key — the name the test stage binds."""

    value: str


@dataclasses.dataclass(frozen=True)
class RowId(Value):
    """A finding row a task closes: `<story>#<n>`, or `<name>#<n>` of a project finding file."""

    value: str


@dataclasses.dataclass(frozen=True)
class RowState(Value):
    """Where a finding row stands: `open`, or what closed it."""

    value: str


@dataclasses.dataclass(frozen=True)
class EventName(Value):
    """An outcome event, as a story's `publishes:` names it."""

    value: str


@dataclasses.dataclass(frozen=True)
class StageStory(Value):
    """One story under a gate: what its front matter and its criteria say."""

    story: StoryId
    place: Place
    epic: typing.Optional[EpicId]
    context: ContextName
    kind: StoryKind
    status: StatusWord
    delivered_on: DeliveredOn
    criteria: typing.Tuple[ScenarioKey, ...]
    happy_paths: typing.Tuple[ScenarioKey, ...]
    depends_on: typing.Tuple[StoryId, ...]
    closes: typing.Tuple[RowId, ...]
    publishes: typing.Tuple[EventName, ...]


@dataclasses.dataclass(frozen=True)
class ContractNumber(Value):
    """A gate contract: what the gate reads and writes, raised when that changes incompatibly."""

    value: int


@dataclasses.dataclass(frozen=True)
class GateRelease(Value):
    """The gate that checks: the contract it implements and its version."""

    contract: ContractNumber
    version: Detail


@dataclasses.dataclass(frozen=True)
class ProfileKey(Value):
    value: str


@dataclasses.dataclass(frozen=True)
class ProfileText(Value):
    """A profile value, as written."""

    value: str


@dataclasses.dataclass(frozen=True)
class UnknownKey(Value):
    """A profile key nobody reads, and the nearest key that is read."""

    key: ProfileKey
    near: typing.Optional[ProfileKey]


@dataclasses.dataclass(frozen=True)
class ModelKey(Value):
    """A `model…` key of the profile and its value."""

    key: ProfileKey
    value_written: ProfileText


@dataclasses.dataclass(frozen=True)
class RoundsRecord(Value):
    """The rounds a story ran without converging, as its counter holds them — None where the counter is no number."""

    place: Place
    rounds: typing.Optional[Rounds]


@dataclasses.dataclass(frozen=True)
class OwnedPart(Value):
    """Something of the person's a stage may not change: the story, an answer."""

    value: str


@dataclasses.dataclass(frozen=True)
class OwnedFacts(Value):
    """What a stage changed of the person's: the parts a past window marked, and those changed while this one runs —
    None where nothing records what they were."""

    marked: typing.Tuple[OwnedPart, ...]
    changed: typing.Optional[typing.Tuple[OwnedPart, ...]]


@dataclasses.dataclass(frozen=True)
class ContextMapFacts(Value):
    """The context map a story's context is looked up on: the designed map's file where the profile names one that
    is not there, the map found, and the names it gives."""

    domain_missing: typing.Optional[Place]
    map: typing.Optional[Place]
    names: typing.FrozenSet[ContextName]


@dataclasses.dataclass(frozen=True)
class ByteSize(Value):
    value: int


@dataclasses.dataclass(frozen=True)
class InstructionFile(Value):
    """The project's instruction file a tool loads first, and its size."""

    place: Place
    size: ByteSize


@dataclasses.dataclass(frozen=True)
class EpicField(Value):
    """A mandatory field of an epic's front matter."""

    value: str


@dataclasses.dataclass(frozen=True)
class Metric(Value):
    """An epic's `metric:` — the outcome event that measures it."""

    value: str


@dataclasses.dataclass(frozen=True)
class EpicFacts(Value):
    """A story's epic: its file and name, the mandatory fields it lacks, the discovery report it names and lacks, why
    its dependencies do not hold, and its metric."""

    place: Place
    name: EpicId
    missing: typing.Tuple[EpicField, ...]
    discovery_missing: typing.Optional[ProfileText]
    dependency_problem: typing.Optional[Detail]
    metric: Metric


@dataclasses.dataclass(frozen=True)
class AnswerField(Value):
    """A line a confirmed answer carries: `answer:`, `by:`, `at:`."""

    value: str


@dataclasses.dataclass(frozen=True)
class DecisionFacts(Value):
    """One decision record of the story, as its gate reads it: where it stands, the stage that asked it (open or a
    draft) or applies its answer, its question, the answer and who gave it, the answer lines a draft lacks."""

    record: RecordId
    kind: RecordKind
    state: DecisionState
    stage: typing.Optional[StageName]
    question: Detail
    place: Place
    answer: Detail
    by: Detail
    missing: typing.Tuple[AnswerField, ...]


@dataclasses.dataclass(frozen=True)
class HandOverAsk(Value):
    """A stage's hand-over as the decisions check reads it: its text, and the records its `## needs-human` names —
    None where it escalates nothing, none where it escalates without naming one."""

    stage: StageName
    place: Place
    text: HandOverText
    asks: typing.Optional[typing.Tuple[RecordId, ...]]


@dataclasses.dataclass(frozen=True)
class DecisionsFacts(Value):
    """The story's decision records under their store, and the stages' hand-overs."""

    store: Place
    records: typing.Tuple[DecisionFacts, ...]
    hand_overs: typing.Tuple[HandOverAsk, ...]
