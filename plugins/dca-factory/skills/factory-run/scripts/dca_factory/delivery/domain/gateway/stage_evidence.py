"""What a stage's checks read for themselves — the profile, the run folder, the project's files.

A gateway, not supplied facts: each check reads only what it alone needs, and only reads; a use case that loaded
every check's facts up front would read the project for checks that do not run at this stage."""

from __future__ import annotations

import typing

from ....building_blocks import DomainGateway
from ..model.decision_record import RecordId
from ..model.stage import StageName
from ..model.decision_record import DecisionRecord
from ..model.story import Story
from ..model.backlog_facts import DecidedRecord, DecisionsFacts, EpicFacts, OutcomeFacts, ProposalFacts, RowState
from ..model.brief_facts import BriefFacts, OwnedFacts, RoundsRecord
from ..model.delivery_facts import (
    DocumentFacts, Integration, MainTests, PipelineFacts, ReviewFacts, StageChanges, StoryCommit, StoryPass)
from ..model.guarded import GuardedFacts
from ..model.design_facts import ContextMapFacts, InvariantFacts, PortName
from ..model.plan_facts import HandOverName, HandOverSize, PlanAdoption, PlanLevels, PlannedFile
from ..model.profile_facts import GateRelease, InstructionFile, ModelKey, ProfileText, UnknownKey
from ..model.story_words import Count, Place, RowId, Selector
from ..model.suite_run import CommandKey
from ..model.test_facts import (
    AssertionFact, ClauseRow, KeptTests, MappedTest, PlannedTestChange, RedProof, SpecDelta, SpecTests, TestSource)
from ..model.story import StoryId
from ..model.story_state import Detail


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

    def place_of(self, story: StoryId) -> Place:
        """Where the story's file is — what a finding about it names."""
        ...

    def rounds(self, story: StoryId) -> typing.Optional[RoundsRecord]:
        """The story's round counter — None where it ran no round."""
        ...

    def owned(self, story: Story) -> OwnedFacts:
        ...

    def brief(self, story: StoryId, stage: StageName, hand_over: HandOverName) -> BriefFacts:
        """The brief <stage> was given and the one its hand-over <hand_over> names."""
        ...

    def context_map(self) -> ContextMapFacts:
        ...

    def instruction_file(self) -> typing.Optional[InstructionFile]:
        """The first instruction file the project keeps — None where it keeps none."""
        ...

    def epic(self, story: Story) -> EpicFacts:
        """The story's epic, or why there is none: the story names none, or the epic has no file."""
        ...

    def finding_row(self, row: RowId) -> typing.Optional[RowState]:
        """Where the named finding row stands — None where there is no such row."""
        ...

    def decisions(self, story: Story) -> DecisionsFacts:
        """The store of the story's decision records and the stages' hand-overs — or why the store cannot be read."""
        ...

    def decision_records(self, story: Story) -> typing.Sequence[DecisionRecord]:
        """The story's decision records, in id order — none where the store cannot be read (`decisions` says why)."""
        ...

    def record_place(self, story: Story, record: RecordId) -> Place:
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

    def invariants(self, story: Story) -> typing.Optional[InvariantFacts]:
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

    def test_source(self, test: Place) -> typing.Optional[TestSource]:
        """The whole text of a test's file — None where it cannot be read."""
        ...

    def plan_files(self, story: StoryId) -> typing.Optional[typing.Tuple[PlannedFile, ...]]:
        """The files the plan says new or removed — None where its plan has no `## Files`."""
        ...

    def stage_changes(self, story: StoryId, stage: StageName,
                      tests: typing.Tuple[MappedTest, ...]) -> StageChanges:
        """What the stage changed — its changed-files record, or inside a shared builder's window the tree against
        the story's base — and what its hand-overs list."""
        ...

    def plan_adoption(self, story: StoryId) -> typing.Optional[PlanAdoption]:
        """The plan's `## Adopt` rows, each test looked up — None where the plan has no such section."""
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

    def spec_delta(self, story: Story) -> typing.Optional[SpecDelta]:
        """The plan's spec delta as the spec reads it — None where there is no plan or the story changes no spec."""
        ...

    def spec_backing(self, story: Story) -> typing.Optional[Detail]:
        """What backs a change of what holds: the story's `## Changed expectations`, or a decision a person answered
        — None where nothing does."""
        ...

    def spec_tests(self, story: Story, tests: typing.Tuple[MappedTest, ...]) -> typing.Optional[SpecTests]:
        """The tests the story's spec names — None where the story changes no spec."""
        ...

    def story_commit(self, story: Story, tests: typing.Tuple[MappedTest, ...]) -> typing.Optional[StoryCommit]:
        """The story's commit against its test files — None where it names no test file."""
        ...

    def story_pass(self, story: Story) -> StoryPass:
        ...

    def outcome(self, story: Story) -> OutcomeFacts:
        """The story's published events in the production code."""
        ...

    def document(self, story: StoryId) -> DocumentFacts:
        ...

    def proposals(self, story: StoryId) -> typing.Optional[ProposalFacts]:
        """The plan's proposed terms against the glossaries — None where the plan proposes none."""
        ...

    def reviews(self, story: StoryId) -> ReviewFacts:
        ...

    def pipeline(self, story: StoryId) -> PipelineFacts:
        ...

    def guarded(self, story: StoryId) -> GuardedFacts:
        """The guarded set, the plan's announced guarded changes and the paths the story's stages changed."""
        ...

    def integration(self, story: StoryId) -> Integration:
        ...

    def main_tests(self, story: StoryId) -> typing.Optional[MainTests]:
        """The main line's side of the tests the merge met — None where the merge met none."""
        ...
