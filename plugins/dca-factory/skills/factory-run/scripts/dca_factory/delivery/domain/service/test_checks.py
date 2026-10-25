"""What a story's tests must be at a tested stage: one at least per criterion, each there, each at the lowest level
that observes its outcome, an end-user test under its scenario's title — and the hand-overs within their measure."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage import StoryKind
from ..model.stage_story import (
    CommandKey, ContractNumber, HandOverName, MappedTest, ScenarioKey, StageStory, TestLocation, TestTable, TitleFound)
from ..model.verdict import CheckName, Findings, Said

TESTS_MAPPED = CheckName("tests-mapped")
TESTS_EXIST = CheckName("tests-exist")
PLAN_LEVELS = CheckName("plan-levels")
LEVELS = CheckName("levels")
TEST_TITLES = CheckName("test-titles")
SIZE = CheckName("size")

E2E = CommandKey("e2eTest")
#: The contract that marks one happy path per story and holds tests to their level.
LEVELS_CONTRACT = ContractNumber(9)

#: A hand-over's measure: a base and a share per criterion, set from the bench's stories (the leanest files carried
#: what the next stage needed at these sizes; the largest were half again as big and said nothing more). A note,
#: never a refusal: the number is the measure `--contract` names, a stage with a reason writes it, and the
#: measurement decides.
HANDOVER_BUDGET = {"plan.md": (3000, 300), "tests.md": (1500, 200), "build.md": (1500, 150),
                   "tidy.md": (1500, 0), "judge.md": (3000, 100), "document.md": (2500, 150)}


class TestChecks(DomainService):
    """The checks over the tests table and the tests it names."""

    @staticmethod
    def mapped(criteria_of_story: typing.Tuple[ScenarioKey, ...], table: TestTable) -> Findings:
        criteria = [key.value for key in criteria_of_story]
        mapped = {key.value for key in table.keys}
        where = table.place.value
        found = []
        uncovered = [key for key in criteria if key not in mapped]
        if uncovered:
            found.append(TESTS_MAPPED.fail(Said(
                f"{where}: no end-user test for {', '.join(uncovered)} — every acceptance criterion needs at least one "
                f"test, or the build gate can never fail on it.")))
        unknown = [key for key in dict.fromkeys(k.value for k in table.keys) if key not in criteria]
        if unknown:
            found.append(TESTS_MAPPED.fail(Said(
                f"{where}: test rows name criteria the story does not have: {', '.join(unknown)}")))
        if not uncovered and not unknown:
            found.append(TESTS_MAPPED.ok(Said(f"{table.tests.value} test(s) mapped to {len(criteria)} criterion(s)")))
        return tuple(found)

    @staticmethod
    def exist(locations: typing.Tuple[TestLocation, ...]) -> Findings:
        """A selector must point at a test that is actually there. Without this check a missing test looks exactly
        like a red one, and the run would certify nothing."""
        found = []
        for test in locations:
            selector, key = test.selector.value, test.key.value
            cls, _sep, method = selector.partition("#")
            if test.found is not None:
                found.append(TESTS_EXIST.ok(Said(f"{selector} found in {test.found.value} ({key}, by "
                                                 f"{test.shape.value})")))
            elif test.candidate is not None:
                found.append(TESTS_EXIST.fail(Said(
                    f"{selector}: {test.candidate.value} has no {method} — criterion {key!r} has no test, only a row "
                    f"in the table")))
            else:
                found.append(TESTS_EXIST.fail(Said(
                    f"{selector}: no source file for {cls.rsplit('.', 1)[-1]} — criterion {key!r} has no test, and a "
                    f"missing test is indistinguishable from a red one at the runner")))
        return tuple(found)

    @staticmethod
    def plan_levels(story: StageStory, evidence: StageEvidence) -> Findings:
        """A plan line the pipeline's skeleton wrote and the stage never finished — a key with no level after it —
        is a plan that was not made: refused at the test gate, before any test is read against it."""
        plan = evidence.plan_levels(story.story)
        if plan is None or not plan.unfinished:
            return ()
        keys = [key.value for key in plan.unfinished]
        return (PLAN_LEVELS.fail(Said(
            f"plan.md gives no level to {', '.join(keys[:6])}" + (" …" if len(keys) > 6 else "")
            + " — the skeleton's line is still empty; the plan stage gives each criterion "
              "`level: e2e | integration | browser-only (<why>)`")),)

    @staticmethod
    def levels(story: StageStory, contract: ContractNumber, tests: typing.Tuple[MappedTest, ...],
               evidence: StageEvidence) -> Findings:
        """A scenario's test runs at the lowest level that observes its `Then`. A test the end-user command runs
        belongs to the happy path or to a scenario the plan gave `browser-only`; every other end-user test is a
        browser test where an integrated one would do."""
        if story.kind is not StoryKind.STORY or contract.value < LEVELS_CONTRACT.value or not tests \
                or evidence.command(E2E) is None:
            return ()
        plan = evidence.plan_levels(story.story)
        allowed = set(story.happy_paths) | (plan.browser_only if plan else frozenset())
        wrong = [f"{t.key.value} ({t.selector.value})" for t in sorted(tests, key=lambda t: t.key.value)
                 if t.place is not None and t.command == E2E and t.key not in allowed]
        if wrong:
            return (LEVELS.fail(Said(
                "end-user tests for scenarios that are neither the happy path nor `browser-only` in the plan — "
                "integrate them (a `test.<name>:` source set), or give the plan's line `level: browser-only (<why>)`: "
                + "; ".join(wrong))),)
        return (LEVELS.ok(Said("every end-user test belongs to the happy path or a browser-only scenario")),)

    @staticmethod
    def titles(story: StageStory, contract: ContractNumber, tests: typing.Tuple[MappedTest, ...],
               evidence: StageEvidence) -> Findings:
        """An end-user test carries its scenario's title verbatim, as its display name."""
        if story.kind is StoryKind.ADOPT or contract.value < LEVELS_CONTRACT.value or not tests \
                or evidence.command(E2E) is None:
            return ()
        wrong = [f"{t.selector.value} ({t.key.value}) — \"{t.title.title.value}\""
                 for t in sorted(tests, key=lambda t: t.key.value)
                 if t.title is not None and t.title.found is TitleFound.UNTITLED]
        if wrong:
            return (TEST_TITLES.fail(Said(
                "end-user tests without their scenario's title as display name — write it verbatim (the scenario's "
                "`Title:` line, else its key in words): " + "; ".join(wrong))),)
        if any(t.place is not None and t.command == E2E for t in tests):
            return (TEST_TITLES.ok(Said("every end-user test carries its scenario's title")),)
        return ()

    @staticmethod
    def size(story: StageStory, names: typing.Tuple[HandOverName, ...], evidence: StageEvidence) -> Findings:
        """A note when a hand-over is larger than what it has to say for a story of its criteria."""
        count = len(story.criteria)
        found = []
        for hand_over in evidence.hand_over_sizes(story.story, names):
            name, size = hand_over.name.value, hand_over.size.value
            if name not in HANDOVER_BUDGET:
                continue
            base, per = HANDOVER_BUDGET[name]
            budget = base + per * count
            if size > budget:
                found.append(SIZE.note(Said(
                    f"{name} is {size / 1000:.1f} kB of the stage's own text; what it has to say for {count} criteria "
                    f"fits in {budget / 1000:.1f} kB (the contract's measure): keys and levels, not the story's text; "
                    f"one citation per row; nothing the story, the plan or the code already says. A note, not a "
                    f"refusal — never a reason to edit the file after the gate ran")))
        return tuple(found)
