"""What a stage's checks read for themselves — the profile, the run folder, the project's files.

A gateway, not supplied facts: each check reads only what it alone needs, and only reads; a use case that loaded
every check's facts up front would read the project for checks that do not run at this stage."""

from __future__ import annotations

import typing

from ....building_blocks import DomainGateway
from ..model.decision_record import RecordId
from ..model.stage_story import (
    CommandKey, ContextMapFacts, DecisionsFacts, EpicFacts, GateRelease, HandOverName, HandOverSize,
    InstructionFile, ModelKey, OwnedFacts, Place, PlanLevels, ProfileText, RoundsRecord, RowId, RowState, StageStory, UnknownKey)
from ..model.story import StoryId


class StageEvidence(DomainGateway, typing.Protocol):
    """The evidence of one project, as a gate reads it."""

    def gate(self) -> GateRelease:
        """The gate that checks."""
        ...

    def declared_contract(self) -> ProfileText:
        """The profile's `contract:` as written — empty where it declares none."""
        ...

    def unknown_keys(self) -> typing.Tuple[UnknownKey, ...]:
        ...

    def model_keys(self) -> typing.Tuple[ModelKey, ...]:
        """The profile's `model` and `model.…` keys."""
        ...

    def rounds(self, story: StoryId) -> typing.Optional[RoundsRecord]:
        """The story's round counter — None where it ran no round."""
        ...

    def owned(self, story: StageStory) -> OwnedFacts:
        ...

    def context_map(self) -> ContextMapFacts:
        ...

    def instruction_file(self) -> typing.Optional[InstructionFile]:
        """The first instruction file the project keeps — None where it keeps none."""
        ...

    def epic(self, story: StageStory) -> EpicFacts:
        """The story's epic; the gate's error where the story names none or the epic has no file."""
        ...

    def finding_row(self, row: RowId) -> typing.Optional[RowState]:
        """Where the named finding row stands — None where there is no such row."""
        ...

    def decisions(self, story: StageStory) -> DecisionsFacts:
        """The story's decision records and the stages' hand-overs; the gate's error where the store cannot be read."""
        ...

    def record_place(self, story: StageStory, record: RecordId) -> Place:
        """Where the record by this id belongs."""
        ...

    def command(self, key: CommandKey) -> typing.Optional[ProfileText]:
        """The profile's command under this key — None where it names none."""
        ...

    def plan_levels(self, story: StoryId) -> typing.Optional[PlanLevels]:
        """The levels the story's plan gave — None where it has no plan yet."""
        ...

    def hand_over_sizes(self, story: StoryId,
                        names: typing.Tuple[HandOverName, ...]) -> typing.Tuple[HandOverSize, ...]:
        """The hand-overs of these names the story's run holds, with the bytes the stage wrote of each."""
        ...
