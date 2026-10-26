"""The checks a stage's gate runs over the story and its evidence alone — registered against the stage table, each
a domain service's findings taken into the run's verdict."""

from __future__ import annotations

import typing

from ...domain.model.stage import Stage, TESTED_KINDS
from ...domain.model.stage_story import ContractNumber, HandOverName, MappedTest, ScenarioKey, Selector
from ...domain.service.backlog_checks import BacklogChecks
from ...domain.service.delivery_checks import DeliveryChecks
from ...domain.service.design_checks import DesignChecks
from ...domain.service.profile_checks import ProfileChecks
from ...domain.service.spec_checks import SpecChecks
from ...domain.service.story_checks import StoryChecks
from ...domain.service.test_checks import TestChecks
from .check_stage import check, Run

#: The contract that holds a build to the plan's files.
PLAN_FILES_CONTRACT = ContractNumber(22)


def table_tests(mapping: typing.Mapping[str, typing.Sequence[str]]) -> typing.Tuple[MappedTest, ...]:
    """The tests table's rows, unlocated."""
    return tuple(MappedTest(ScenarioKey(key), Selector(selector), None, None, None)
                 for key, selectors in (mapping or {}).items() for selector in selectors)


def after_plan(stage: Stage) -> bool:
    return stage.name.value != "plan"


def weighed(stage: Stage) -> bool:
    return bool(stage.sizes)


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
