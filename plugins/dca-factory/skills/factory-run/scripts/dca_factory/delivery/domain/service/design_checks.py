"""What a story's test design must hold beyond its table: every rule of a changed domain type has a unit test of its
own, every expectation of a scenario names the line that asserts it, a criterion's integrated test runs through the
real use case, and the build leaves the plan's files as the plan said."""

from __future__ import annotations

import re
import typing

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage import StoryKind
from ..model.stage_story import (
    AssertionAt, CommandKey, ContractNumber, Count, FileChange, MappedTest, Place, Presence, StageStory)
from ..model.verdict import CheckName, Findings, Said

INVARIANTS = CheckName("invariants")
CLAUSES = CheckName("clauses")
TESTS_REAL = CheckName("tests-real")
PLAN_FILES = CheckName("plan-files")

INVARIANTS_MARKER = "<!-- gate:invariants -->"
CLAUSES_MARKER = "<!-- gate:clauses -->"
#: The contract that holds a story's domain types to their invariants, and the one that holds an adoption's.
INVARIANTS_CONTRACT = ContractNumber(13)
ADOPTED_INVARIANTS_CONTRACT = ContractNumber(24)
#: The contract that holds every clause to its assertion.
CLAUSES_CONTRACT = ContractNumber(15)

CLAUSE_LEVELS = ("unit", "port", "adapter", "e2e")

#: Words that make a clause a statement about what is stored — it holds through the input port with the real store,
#: never in an adapter test whose input ports are stubs, where the assertion only reads back the stub's answer.
STATE_WORDS = re.compile(r"\b(bleibt|bleiben|unverändert|weiterhin|danach|gespeichert|gelöscht|remains?|stays?|"
                         r"unchanged|still|afterwards|stored|persisted|deleted)\b", re.IGNORECASE)

UNIT = CommandKey("test")


class DesignChecks(DomainService):
    """The checks over the plan's and the tests' design tables."""

    @staticmethod
    def invariants(story: StageStory, contract: ContractNumber, tests: typing.Tuple[MappedTest, ...],
                   evidence: StageEvidence) -> Findings:
        """Every domain type the plan changes names its invariants — its rules, the guards included, one per `;` —
        and every rule has its own unit test in tests.md's `gate:invariants` table: a selector that exists as class
        and method, and that is no criterion's test. A guard nobody named is code no test asked for; a rule whose
        only test is a criterion's is a rule nobody tested on its own.

        An adoption changes no domain type, so its plan names the ones its scenarios exercise — each with its rules,
        or `- none — <why>` where they exercise none — and every rule is held the same way."""
        adopt = story.kind is StoryKind.ADOPT
        if story.kind not in (StoryKind.STORY, StoryKind.ADOPT) or contract.value < (
                ADOPTED_INVARIANTS_CONTRACT if adopt else INVARIANTS_CONTRACT).value:
            return ()
        facts = evidence.invariants(story)
        if facts is None:
            return ()
        if adopt and not facts.listed.value:
            return (INVARIANTS.fail(Said(
                "plan.md: an adoption names the invariants of the domain types its scenarios exercise under "
                "`## Invariants` — `- <Element>: <rule>; <rule>` per type, its guards included, or `- none — <why>` "
                "where the scenarios exercise none")),)
        named = {entry.element.value: [rule.value for rule in entry.rules] for entry in facts.named}
        elements = list(named) if adopt else [e.value for e in facts.elements]
        if not elements and not any(named.values()):
            if adopt:
                return (INVARIANTS.ok(Said("the adoption's scenarios exercise no domain type with a rule of its own "
                                           "— the plan says why")),)
            return ()
        missing = [e for e in elements if e not in named]
        if missing:
            return (INVARIANTS.fail(Said(
                "plan.md changes domain types without an `## Invariants` line: " + ", ".join(missing)
                + " — name each one's rules, its guards included (`- <Element>: <rule>; <rule>`), or "
                  "`- <Element>: none — <why>`")),)
        if not any(named.values()):
            return (INVARIANTS.ok(Said("every domain type the plan changes names why it has no invariant of its "
                                       "own")),)
        if facts.rows is None:
            return (INVARIANTS.fail(Said(
                f"tests.md has no `{INVARIANTS_MARKER}` table under `## Invariants` — `factory-cli.py --files-skeleton "
                f"<story> test` writes it with one row per rule; fill in each row's test")),)
        criterion_tests = {test.selector for test in tests}
        covered: typing.Set[typing.Tuple[str, int]] = set()
        problems = []
        for row in facts.rows:
            element = row.element.value
            rules = named.get(element)
            if rules is None:
                problems.append(f"{element} is not in plan.md's `## Invariants`")
                continue
            numbers = [n.value for n in row.numbers]
            wrong = [n for n in numbers if not 1 <= n <= len(rules)]
            if not numbers or wrong:
                problems.append(f"{element} has {len(rules)} rule(s), the row names "
                                f"{', '.join(map(str, wrong)) or 'none'}")
                continue
            if row.malformed is not None:
                problems.append(f"{row.malformed.value!r} is not `<Class>#<method>`")
            elif row.selector is None:
                continue                      # the skeleton's row, not filled: reported as untested below
            elif row.selector in criterion_tests:
                problems.append(f"{row.selector.value} is a criterion's test — an invariant gets a unit test of its "
                                f"own")
            elif evidence.test_place(row.selector) is None:
                problems.append(f"{row.selector.value} is not in the project (no file named after the class mentions "
                                f"the method)")
            else:
                covered.update((element, n) for n in numbers)
        untested = [f"{e} {n} ({rules[n - 1][:60]})" for e, rules in named.items() for n in range(1, len(rules) + 1)
                    if (e, n) not in covered]
        if problems:
            return (INVARIANTS.fail(Said("the `gate:invariants` table: " + "; ".join(problems[:6]) + (" …" if len(problems) > 6 else ""))),)
        if untested:
            return (INVARIANTS.fail(Said("invariants without a unit test of their own: " + "; ".join(untested[:6])
                                         + (" …" if len(untested) > 6 else "")
                                         + " — the row's last cell, `<Class>#<method>`")),)
        return (INVARIANTS.ok(Said(f"every rule the plan names has a unit test of its own "
                                   f"({sum(len(r) for r in named.values())} rules, {len(facts.rows)} rows)")),)

    @staticmethod
    def clauses(story: StageStory, contract: ContractNumber, tests: typing.Tuple[MappedTest, ...],
                evidence: StageEvidence) -> Findings:
        """Every expectation of every scenario — its `Then` and each `And` after it — names the line of the test that
        asserts it, in tests.md's `gate:clauses` table, with the level it runs at. A clause without a line is an
        expectation nobody asserted; a clause about what is stored, asserted in an adapter test against stubbed
        input ports, asserts only the stub."""
        if story.kind is not StoryKind.STORY or contract.value < CLAUSES_CONTRACT.value:
            return ()
        if not story.clauses:
            return ()
        rows = evidence.clause_rows(story.story)
        if rows is None:
            return (CLAUSES.fail(Said(
                f"tests.md has no `{CLAUSES_MARKER}` table under `## Clauses` — `factory-cli.py --files-skeleton "
                f"<story> test` writes one row per `Then`/`And`; fill in each row's `<File>:<line>` and level")),)
        given = {(row.key.value, row.number.value): (row.location.value, row.level.value) for row in rows}
        problems, state_on_stub, counted = [], [], 0
        for scenario in story.clauses:
            key = scenario.key.value
            own = tuple(t.place for t in tests if t.key == scenario.key and t.place is not None)
            for clause in scenario.clauses:
                n, text = clause.number.value, clause.text.value
                location, level = given.get((key, n), ("", ""))
                if not location:
                    problems.append(f"{key} {n} ({text[:50]}) has no assertion line")
                    continue
                found = re.match(r"(.+?):L?(\d+)", location)
                fact = evidence.assertion_at(Place(found.group(1)), Count(int(found.group(2))), own) if found else None
                if fact is None or fact.state is AssertionAt.NO_FILE:
                    problems.append(f"{key} {n}: `{location}` is no `<File>:<line>` in the project")
                    continue
                if fact.state is AssertionAt.NOTHING:
                    problems.append(f"{key} {n}: `{location}` asserts nothing — no assertion at or just above that "
                                    f"line")
                    continue
                assert found is not None
                if own and fact.among is Presence.ABSENT \
                        and not re.search(r"(^|/)tests?[^/]*/", found.group(1)):
                    problems.append(f"{key} {n}: `{location}` is in no test of {key} and no test source")
                    continue
                if level not in CLAUSE_LEVELS:
                    problems.append(f"{key} {n}: level `{level or '—'}` is none of {', '.join(CLAUSE_LEVELS)}")
                    continue
                if level == "adapter" and STATE_WORDS.search(text):
                    state_on_stub.append(f"{key} {n} ({text[:60]})")
                    continue
                counted += 1
        if problems:
            return (CLAUSES.fail(Said("the `gate:clauses` table: " + "; ".join(problems[:6]) + (" …" if len(problems) > 6 else ""))),)
        if state_on_stub:
            return (CLAUSES.fail(Said(
                "clauses about what is stored, asserted at the adapter level: " + "; ".join(state_on_stub[:6])
                + " — an adapter test's input ports are stubs, so the assertion reads back the stub; assert the "
                  "clause through the input port with the real store (`port`), or end to end")),)
        return (CLAUSES.ok(Said(f"every expectation of every scenario names its assertion ({counted} clause(s))")),)

    @staticmethod
    def tests_real(story: StageStory, tests: typing.Tuple[MappedTest, ...], evidence: StageEvidence) -> Findings:
        """A criterion's test above the unit level runs through the real use case — it does not declare a double of
        an input port. "The list stays unchanged" checked against a stub proves the stub. A unit test mocks what it
        wants; an output port may be replaced at any level; and a criterion the plan gave `integration (adapter: …)`
        tests the adapter's translation against a stubbed input port by design."""
        if not any(test.place is not None for test in tests):
            return ()
        plan = evidence.plan_levels(story.story)
        adapter_keys = plan.adapter if plan else frozenset()
        wrong = set()
        for test in sorted(tests, key=lambda t: t.key.value):
            if test.key in adapter_keys or test.place is None or test.command in (None, UNIT):
                continue
            doubles = evidence.doubles(test.place)
            if doubles:
                wrong.add(f"{test.key.value} ({test.place.value}: {', '.join(d.value for d in doubles)})")
        if wrong:
            return (TESTS_REAL.fail(Said(
                "a criterion's integrated or end-to-end test replaces the input port it is about — it proves the "
                "double, not the use case; let it run through the real one and replace only what lies outside (a "
                "repository, an external system): " + "; ".join(sorted(wrong)))),)
        return (TESTS_REAL.ok(Said("every integrated and end-to-end test of a criterion runs through the real input "
                                   "port")),)

    @staticmethod
    def plan_files(story: StageStory, evidence: StageEvidence) -> Findings:
        """The plan's file list holds after the build — a file it says `removed` is gone, one it says `new` is there.
        A deviation the build's file explains is still one: the plan changes, or the file does."""
        planned = evidence.plan_files(story.story)
        if planned is None:
            return (PLAN_FILES.skip(Said("plan.md has no `## Files` section — nothing to hold the build to")),)
        wrong, held = [], 0
        for file in planned:
            if file.change is FileChange.REMOVED and file.presence is Presence.PRESENT:
                wrong.append(f"{file.place.value} (planned removed, still there)")
            elif file.change is FileChange.NEW and file.presence is Presence.ABSENT:
                wrong.append(f"{file.place.value} (planned new, not there)")
            else:
                held += 1
        if wrong:
            return (PLAN_FILES.fail(Said(
                "the build did not do what the plan's `## Files` says — remove the file (`git rm`) or write it, or "
                "plan again; an explanation in build.md does not change the plan: " + "; ".join(wrong))),)
        if held:
            return (PLAN_FILES.ok(Said(f"every file the plan says new or removed is so ({held})")),)
        return (PLAN_FILES.ok(Said("the plan's `## Files` names no file new or removed")),)
