"""The checks a stage's gate runs over the story and its evidence alone — registered against the stage table, each
a domain service's findings taken into the run's verdict."""

from __future__ import annotations

import typing

from ...domain.model.stage import Stage, StageName, TESTED_KINDS, Trait
from ...domain.model.stage_story import ContractNumber, Count, HandOverName, MappedTest, Place, ScenarioKey, Selector, TestTable
from ...domain.model.verdict import CheckName, Said
from ...domain.service.kept_checks import KeptChecks
from ...domain.service.backlog_checks import BacklogChecks
from ...domain.service.delivery_checks import DeliveryChecks
from ...domain.service.design_checks import DesignChecks
from ...domain.service.profile_checks import ProfileChecks
from ...domain.service.spec_checks import SpecChecks
from ...domain.service.story_checks import StoryChecks
from ...domain.service.test_checks import TestChecks
from .check_stage import check, Run

#: The contract that holds a build to the plan's files, and the one that holds a criterion's test to the real use case.
PLAN_FILES_CONTRACT = ContractNumber(22)
TESTS_REAL_CONTRACT = ContractNumber(21)
TESTS_MAPPED = CheckName("tests-mapped")


def table_tests(mapping: typing.Mapping[str, typing.Sequence[str]]) -> typing.Tuple[MappedTest, ...]:
    """The tests table's rows, unlocated."""
    return tuple(MappedTest(ScenarioKey(key), Selector(selector), None, None, None)
                 for key, selectors in (mapping or {}).items() for selector in selectors)


def after_plan(stage: Stage) -> bool:
    return stage.name.value != "plan"


def weighed(stage: Stage) -> bool:
    return bool(stage.sizes)


def tested(stage: Stage) -> bool:
    return Trait.TESTED in stage.traits


def listing(stage: Stage) -> bool:
    return Trait.LISTS in stage.traits


def red(stage: Stage) -> bool:
    return Trait.RED in stage.traits


def mapped(run: Run) -> typing.Tuple[MappedTest, ...]:
    """The run's tests table, read once with each test's file, command and title check."""
    cached = getattr(run, "mapped_tests", None)
    if cached is None or cached[0] is not run.mapping or cached[1] is not run.located:
        cached = (run.mapping, run.located, run.tests.mapped(run.body, run.mapping or {}, run.located or {}))
        run.mapped_tests = cached
    return typing.cast(typing.Tuple[MappedTest, ...], cached[2])


@check("story")
def _story(run: Run) -> None:
    run.result.take(StoryChecks.context(run.story))


@check("contract")
def _contract(run: Run) -> None:
    run.result.take(ProfileChecks.contract(run.evidence))


@check("status")
def _status(run: Run) -> None:
    run.result.take(StoryChecks.status(run.story))


@check("epic")
def _epic(run: Run) -> None:
    run.result.take(BacklogChecks.epic(run.story, run.evidence))


@check("outcome", stages=("plan",), kinds=TESTED_KINDS)
def _outcome_named(run: Run) -> None:
    run.result.take(BacklogChecks.outcome(run.story, run.contract, run.evidence))


@check("rounds")
def _rounds(run: Run) -> None:
    run.result.take(StoryChecks.rounds(run.story, run.evidence))


@check("pipeline", stages=after_plan)
def _pipeline(run: Run) -> None:
    run.result.take(DeliveryChecks.pipeline_untouched(run.story, run.evidence))


@check("owned")
def _owned(run: Run) -> None:
    run.result.take(StoryChecks.owned(run.story, run.evidence))


@check("spec-delta", stages=("test",))
def _spec_delta(run: Run) -> None:
    run.result.take(SpecChecks.delta(run.story, run.evidence))


@check("spec-tests", stages=("document", "adopt", "integrate"), kinds=TESTED_KINDS)
def _spec_tests(run: Run) -> None:
    run.result.take(SpecChecks.tests(run.story, table_tests(run.mapping), run.evidence))


@check("tests-committed", stages=("integrate",), kinds=TESTED_KINDS)
def _tests_committed(run: Run) -> None:
    run.result.take(SpecChecks.committed(run.story, table_tests(run.mapping), run.evidence))


@check("plan-files", stages=("build",))
def _plan_files(run: Run) -> None:
    if run.contract.value >= PLAN_FILES_CONTRACT.value:
        run.result.take(DesignChecks.plan_files(run.story, run.evidence))


@check("size", stages=weighed)
def _size(run: Run) -> None:
    run.result.take(TestChecks.size(run.story, tuple(HandOverName(name) for name in run.stage.sizes), run.evidence))


@check("tests-mapped", stages=tested, kinds=TESTED_KINDS)
def _mapping(run: Run) -> None:
    path, mapping, unreadable = run.tests.table(run.story_id)
    if unreadable is not None:
        run.result.take((TESTS_MAPPED.fail(Said(unreadable)),))
        run.mapping, run.located = {}, None
        return
    table = TestTable(Place(path), tuple(ScenarioKey(key) for key in mapping),
                      Count(sum(len(selectors) for selectors in mapping.values())))
    run.result.take(TestChecks.mapped(run.story.criteria, table))
    run.mapping, run.located = mapping, None
    if mapping:
        located, looked = run.tests.locate(mapping)
        run.result.take(TestChecks.exist(looked))
        run.located = located


# Integrated, the story's diff carries the main line's changes beside its own: the file list, the tests that existed
# before and the red proof were the stages' to hold, and they held.
@check("files-listed", stages=listing)
def _files_listed(run: Run) -> None:
    run.result.take(KeptChecks.files_listed(run.story, StageName(run.stage.name), mapped(run), run.evidence))
    run.result.take(KeptChecks.tests_kept(run.story, run.evidence))


@check("test-design", stages=red)
def _test_design(run: Run) -> None:
    run.result.take(TestChecks.plan_levels(run.story, run.evidence))
    tests = mapped(run)
    run.result.take(DesignChecks.invariants(run.story, run.contract, tests, run.evidence))
    run.result.take(TestChecks.levels(run.story, run.contract, tests, run.evidence))
    run.result.take(DesignChecks.clauses(run.story, run.contract, tests, run.evidence))
    run.result.take(TestChecks.titles(run.story, run.contract, tests, run.evidence))


@check("tests-real", stages=("test", "adopt"))
def _tests_real(run: Run) -> None:
    if run.contract.value >= TESTS_REAL_CONTRACT.value:
        run.result.take(DesignChecks.tests_real(run.story, mapped(run), run.evidence))


@check("red-proof", stages=listing, kinds=TESTED_KINDS)
def _red_proof(run: Run) -> None:
    # the red proof compares digests, so it belongs here, before any process
    if run.expected == "green":
        run.result.take(KeptChecks.red_proof(run.story, StageName(run.stage.name), mapped(run), run.evidence))
