"""What a stage's checks read for themselves — the profile, the run folder, the project's files.

A gateway, not supplied facts: each check reads only what it alone needs, and only reads; a use case that loaded
every check's facts up front would read the project for checks that do not run at this stage."""

from __future__ import annotations

import typing

from ....building_blocks import DomainGateway
from ..model.decision_record import RecordId
from ..model.stage import StageName
from ..model.stage_story import (
    DecidedRecord, KeptTests, MappedTest, PlannedTestChange, RedProof, StageChanges,
    AssertionFact, ClauseRow, CommandKey, ContextMapFacts, Count, InvariantFacts, PlannedFile, PortName, Selector, DecisionsFacts, EpicFacts, GateRelease, HandOverName, HandOverSize,
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

    def invariants(self, story: StageStory) -> typing.Optional[InvariantFacts]:
        """The plan's domain types and their invariants, and the tests' table of them — None where there is no plan."""
        ...

    def test_place(self, selector: Selector) -> typing.Optional[Place]:
        """The file that holds the test: named after its class, in its package, mentioning its method."""
        ...

    def clause_rows(self, story: StoryId) -> typing.Optional[typing.Tuple[ClauseRow, ...]]:
        """The tests' table of the lines that assert the scenarios' clauses — None where it has none."""
        ...

    def assertion_at(self, file: Place, line: Count, among: typing.Tuple[Place, ...]) -> AssertionFact:
        """What the line of the file does, and whether the file is one of `among`."""
        ...

    def doubles(self, test: Place) -> typing.Tuple[PortName, ...]:
        """The input ports a test file declares as doubles."""
        ...

    def plan_files(self, story: StoryId) -> typing.Optional[typing.Tuple[PlannedFile, ...]]:
        """The files the plan says new or removed — None where its plan has no `## Files`."""
        ...

    def stage_changes(self, story: StoryId, stage: StageName,
                      tests: typing.Tuple[MappedTest, ...]) -> StageChanges:
        """What the stage changed — its changed-files record, or inside a shared builder's window the tree against
        the story's base — and what its hand-overs list."""
        ...

    def kept_tests(self, story: StoryId) -> typing.Optional[KeptTests]:
        """The tests that existed before the story against their baseline — None where no baseline was taken."""
        ...

    def decided_tests(self, story: StoryId) -> typing.Tuple[DecidedRecord, ...]:
        """The answered decisions a test stage or a build stage asked."""
        ...

    def planned_test_changes(self, story: StoryId) -> typing.Tuple[PlannedTestChange, ...]:
        ...

    def answered_records(self, story: StoryId) -> typing.FrozenSet[RecordId]:
        """The story's records that are answered or applied — none where its records cannot be read."""
        ...

    def red_proof(self, story: StoryId, stage: StageName,
                  tests: typing.Tuple[MappedTest, ...]) -> typing.Optional[RedProof]:
        """The red ledger against the tests as they are — None where the story has none."""
        ...
