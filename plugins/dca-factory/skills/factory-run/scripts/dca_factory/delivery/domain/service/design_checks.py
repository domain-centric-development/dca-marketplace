"""What a story's test design must hold beyond its table: every rule of a changed domain type has a unit test of its
own, every expectation of a scenario names the line that asserts it, a criterion's integrated test runs through the
real use case, and the build leaves the plan's files as the plan said."""

from __future__ import annotations

import re
import typing

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage import StoryKind
from ..model.story import Story
from ..model.plan_facts import FileChange, PlanStamp
from ..model.profile_facts import ContractNumber
from ..model.story_words import Clause, Count, Place, ScenarioKey
from ..model.suite_run import CommandKey
from ..model.test_facts import AssertionAt, MappedTest
from ..model.story_state import Detail
from ..model.verdict import CheckName, Findings, Said

INVARIANTS = CheckName("invariants")
CLAUSES = CheckName("clauses")
TESTS_REAL = CheckName("tests-real")
TESTS_PLANNED = CheckName("tests-planned")
PLAN_KEPT = CheckName("plan-kept")
INVARIANTS_COVER = CheckName("invariants-cover")
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
#: A form field that holds something — "the field „Name“ still holds …", "das Eingabefeld enthält weiterhin …": the
#: field is the subject, a verb says it holds or shows; group 1 is what it holds.
FIELD_HOLDS = re.compile(
    r"\b(?:fields?|input(?:\s+fields?|\s+box(?:es)?)?|text\s?(?:box(?:es)?|areas?|fields?)|"
    r"Feld(?:er)?|Eingabefeld(?:er)?|Textfeld(?:er)?)\b[^.;]*?"
    r"\b(?:holds?|shows?|contains?|keeps?|displays?|retains?|"
    r"enthält|enthalten|zeigt|zeigen|behält|behalten|hält|halten|steht|stehen)\b([^.;]*)", re.IGNORECASE)
#: A word that says what the field holds is what was entered — "the 201 characters entered", "den eingegebenen Text".
ENTERED = re.compile(r"\b(?:entered|typed|eingegeben\w*|eingetippt\w*|getippt\w*)\b", re.IGNORECASE)
#: A word of a step, and the words that carry no content of their own.
WORD = re.compile(r"[^\W\d_]{2,}")
FILLER = {"the", "a", "an", "its", "his", "her", "their", "der", "die", "das", "den", "dem", "des", "ein", "eine",
          "einen", "noch", "immer", "weiterhin", "still"}
#: What a step names exactly: a quoted text or a number.
NAMED = re.compile(r'„([^“”"\n]+)[“”]|“([^”\n]+)”|"([^"\n]+)"|‚([^‘’\n]+)[‘’]|«([^»\n]+)»|\b(\d+)\b')

UNIT = CommandKey("test")


def states_stored(clause: Clause, actions: typing.Tuple[Detail, ...]) -> bool:
    """Whether a clause says something about what is stored — a state word, unless the clause is a form field that
    holds what the person entered. Nothing is stored there: the page shows the request's input again, the incoming
    adapter's own translation, so the clause may be asserted at the adapter level.

    What the field holds is what was entered when a word says so ("the 201 characters entered", "den eingegebenen
    Text"), or when every quoted text and number it names stands in the scenario's `When` steps ("the title field
    still holds the 201 characters „a“" after "When the person creates a task whose title is 201 characters „a“").
    Narrow on purpose: the field is the subject — "„Alpha“ still carries the button" names another record's state and
    stays a state clause — and a field that names nothing the person entered stays one too."""
    text = clause.text.value
    if not STATE_WORDS.search(text):
        return False
    held = FIELD_HOLDS.search(text)
    if held is None:
        return True
    if ENTERED.search(held.group(1)):
        return False
    named = {next(g for g in m.groups() if g) for m in NAMED.finditer(held.group(1))}
    entered = {next(g for g in m.groups() if g) for action in actions for m in NAMED.finditer(action.value)}
    if named:
        return not named <= entered
    # Nothing quoted or counted: what the field holds in words — "the three spaces" after "(three spaces)" in the
    # `When` — is the input when every word of it stands in a `When` step.
    words = {w.lower() for w in WORD.findall(held.group(1))} - FILLER
    said = {w.lower() for action in actions for w in WORD.findall(action.value)}
    return not (words and words <= said)


class DesignChecks(DomainService):
    """The checks over the plan's and the tests' design tables."""

    @staticmethod
    def invariants(story: Story, contract: ContractNumber, tests: typing.Tuple[MappedTest, ...],
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
    def clauses(story: Story, contract: ContractNumber, tests: typing.Tuple[MappedTest, ...],
                evidence: StageEvidence) -> Findings:
        """Every expectation of every scenario — its `Then` and each `And` after it — names the line of the test that
        asserts it, in tests.md's `gate:clauses` table, with the level it runs at. A clause without a line is an
        expectation nobody asserted; a clause about what is stored, asserted in an adapter test against stubbed
        input ports, asserts only the stub. A form field that still holds what was entered is no such clause: the
        page shows the request's input again, the incoming adapter's own translation (`states_stored`)."""
        if story.kind is not StoryKind.STORY or contract.value < CLAUSES_CONTRACT.value:
            return ()
        if not story.content.clauses:
            return ()
        rows = evidence.clause_rows(story.id)
        if rows is None:
            return (CLAUSES.fail(Said(
                f"tests.md has no `{CLAUSES_MARKER}` table under `## Clauses` — `factory-cli.py --files-skeleton "
                f"<story> test` writes one row per `Then`/`And`; fill in each row's `<File>:<line>` and level")),)
        given = {(row.key.value, row.number.value): (row.location.value, row.level.value) for row in rows}
        problems, state_on_stub, counted = [], [], 0
        for scenario in story.content.clauses:
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
                if own and not fact.among \
                        and not re.search(r"(^|/)tests?[^/]*/", found.group(1)):
                    problems.append(f"{key} {n}: `{location}` is in no test of {key} and no test source")
                    continue
                if level not in CLAUSE_LEVELS:
                    problems.append(f"{key} {n}: level `{level or '—'}` is none of {', '.join(CLAUSE_LEVELS)}")
                    continue
                if level == "adapter" and states_stored(clause, scenario.actions):
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
    def tests_real(story: Story, tests: typing.Tuple[MappedTest, ...], evidence: StageEvidence) -> Findings:
        """A criterion's test above the unit level runs through the real use case — it does not declare a double of
        an input port. "The list stays unchanged" checked against a stub proves the stub. A unit test mocks what it
        wants; an output port may be replaced at any level; and a criterion the plan gave `integration (adapter: …)`
        alone tests the adapter's translation against a stubbed input port by design.

        A criterion the plan gave both shapes — through the port and `integration (adapter: …)` — has both: its
        adapter test may stub the input port, as long as at least one of its tests above the unit level runs
        without a double of an input port; that one is the port's proof. Without it the port shape is missing."""
        if not any(test.place is not None for test in tests):
            return ()
        plan = evidence.plan_levels(story.id)
        adapter_keys = plan.adapter if plan else frozenset()
        both_keys = plan.both if plan else frozenset()
        wrong: typing.Set[str] = set()
        stubbed: typing.Set[ScenarioKey] = set()
        proven: typing.Set[ScenarioKey] = set()
        for test in sorted(tests, key=lambda t: t.key.value):
            if test.key in adapter_keys or test.place is None or test.command in (None, UNIT):
                continue
            doubles = evidence.doubles(test.place)
            if test.key in both_keys:
                (stubbed if doubles else proven).add(test.key)
            elif doubles:
                wrong.add(f"{test.key.value} ({test.place.value}: {', '.join(d.value for d in doubles)})")
        if wrong:
            return (TESTS_REAL.fail(Said(
                "a criterion's integrated or end-to-end test replaces the input port it is about — it proves the "
                "double, not the use case; let it run through the real one and replace only what lies outside (a "
                "repository, an external system): " + "; ".join(sorted(wrong)))),)
        no_port = sorted(key.value for key in stubbed - proven)
        if no_port:
            return (TESTS_REAL.fail(Said(
                "the plan gives these criteria the port shape beside the adapter's, but each of their tests stubs the "
                "input port — the port shape is missing; map a test that runs through the real input port beside the "
                "adapter's: " + ", ".join(no_port))),)
        return (TESTS_REAL.ok(Said("every integrated and end-to-end test of a criterion runs through the real input "
                                   "port, or is the adapter's beside one that does")),)

    @staticmethod
    def tests_planned(story: Story, tests: typing.Tuple[MappedTest, ...], evidence: StageEvidence) -> Findings:
        """The adapter test the plan names for a criterion's adapter shape is one of the criterion's tests. The plan
        names it after the state the adapter shows; the test stage takes the name, so a test named after an action its
        stub cannot perform does not stand where the plan put the adapter's."""
        plan = evidence.plan_levels(story.id)
        if plan is None or not plan.named:
            return ()
        unnamed = sorted({p.key.value for p in plan.named if p.test is None})
        held = plan.held_names()
        if unnamed:
            return (TESTS_PLANNED.fail(Said(
                "the plan gives these criteria the adapter shape without naming its test — write "
                "`integration (adapter: <Adapter>, test: <Class>#<method>)`, the method named after the state the "
                "adapter shows: " + ", ".join(unnamed))),)
        missing = []
        for planned in held:
            rows = [t.selector for t in tests if t.key == planned.key]
            if not planned.found_in(rows):
                missing.append(f"{planned.key.value} ({planned.test.value if planned.test else ''})")
        if missing:
            return (TESTS_PLANNED.fail(Said(
                "the adapter test the plan names is not among the criterion's tests in `gate:tests` — write it under "
                "that name and map it; where a round renames, splits or drops it, write `- `<old>` → `<new>` — <why>` "
                "under `## Plan changes` in tests.md — never change plan.md after its gate: " + "; ".join(missing))),)
        renamed = [f"{r.old.value} → {', '.join(n.value for n in r.new) or 'none'} ({r.why.value})" for r in plan.renames]
        if renamed:
            return (TESTS_PLANNED.note(Said("every adapter test is mapped under the name the plan or a later stage gave "
                                            "it — renamed in tests.md's `## Plan changes`, which the judge weighs: "
                                            + "; ".join(renamed))),)
        return (TESTS_PLANNED.ok(Said(f"every adapter test the plan names is mapped to its criterion "
                                      f"({len(plan.named)})")),)

    @staticmethod
    def invariants_cover(story: Story, evidence: StageEvidence) -> Findings:
        """Every domain type the story's change touched has its line under the plan's `## Invariants` — its rules, or
        `none — <why>`. A type the plan never weighed gets a guard nobody named and a rule nobody tested: a value
        from a request reaching it through a new factory is the plan's to see, not the build's to slip in."""
        changed = evidence.changed_domain_types(story)
        if not changed:
            return ()
        facts = evidence.invariants(story)
        def plain(name: str) -> str:
            return name.replace("_", "").replace("-", "").lower()
        named = {plain(rules.element.value) for rules in facts.named} if facts else set()
        named |= {plain(rules.element.value) for rules in evidence.build_invariants(story)}
        missing = sorted({f"{t.name.value} ({t.place.value})" for t in changed if plain(t.name.value) not in named})
        if missing:
            return (INVARIANTS_COVER.fail(Said(
                "the story changes domain types the plan's `## Invariants` has no line for — add one per type under "
                "`## Invariants` in build.md, its rules or `none — <why>`, and a unit test per rule; the plan stays as "
                "it was planned: " + "; ".join(missing[:8])
                + (" …" if len(missing) > 8 else ""))),)
        return (INVARIANTS_COVER.ok(Said(f"every domain type the story changes has its `## Invariants` line "
                                         f"({len({t.name.value for t in changed})})")),)

    @staticmethod
    def plan_kept(story: Story, evidence: StageEvidence) -> Findings:
        """The plan stays as its gate passed it. A stage after the plan that changes plan.md makes every later hand-over
        one of an earlier pass, and the delivery sends the story a round back; what the build adds or takes back stands
        in build.md (`## Invariants`, `## Plan changes`), which the gates read beside the plan."""
        origin = evidence.plan_origin(story.id)
        if origin.stamp is PlanStamp.CHANGED:
            return (PLAN_KEPT.fail(Said(
                "plan.md changed after its gate passed it — put it back as the plan gate passed it, and write what "
                "the build adds or takes back in build.md: a domain type's line under `## Invariants`, a planned file "
                "taken back under `## Plan changes` (`- `<path>` — <why>`). A plan that is wrong goes back to the plan "
                "stage, never into plan.md from a later one")),)
        if origin.stamp is PlanStamp.STAMPED:
            return (PLAN_KEPT.ok(Said("plan.md is as its gate passed it")),)
        return ()

    @staticmethod
    def plan_files(story: Story, evidence: StageEvidence) -> Findings:
        """The plan's file list holds after the build — a file it says `removed` is gone, one it says `new` is there.
        A deviation the build's file explains is still one: the plan changes, or the file does."""
        planned = evidence.plan_files(story.id)
        if planned is None:
            return (PLAN_FILES.skip(Said("plan.md has no `## Files` section — nothing to hold the build to")),)
        wrong, held, taken_back = [], 0, []
        for file in planned:
            missed = (file.change is FileChange.REMOVED and file.exists) or (file.change is FileChange.NEW and not file.exists)
            if missed and file.withdrawn is not None:
                taken_back.append(f"{file.place.value} ({file.withdrawn.value})")
            elif file.change is FileChange.REMOVED and file.exists:
                wrong.append(f"{file.place.value} (planned removed, still there)")
            elif file.change is FileChange.NEW and not file.exists:
                wrong.append(f"{file.place.value} (planned new, not there)")
            else:
                held += 1
        if wrong:
            return (PLAN_FILES.fail(Said(
                "the build did not do what the plan's `## Files` says — write the file or remove it (`git rm`); where "
                "the plan was wrong, name the file and why under `## Plan changes` in build.md — never change plan.md "
                "after the tests: " + "; ".join(wrong))),)
        if taken_back:
            return (PLAN_FILES.note(Said("planned files the build took back, with its reason in build.md's `## Plan "
                                         "changes` — the judge weighs them: " + "; ".join(taken_back))),)
        if held:
            return (PLAN_FILES.ok(Said(f"every file the plan says new or removed is so ({held})")),)
        return (PLAN_FILES.ok(Said("the plan's `## Files` names no file new or removed")),)
