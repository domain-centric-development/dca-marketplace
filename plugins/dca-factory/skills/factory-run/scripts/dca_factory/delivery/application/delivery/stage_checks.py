"""The checks a stage's gate runs over the story and its evidence alone — registered against the stage table, each
a domain service's findings taken into the run's verdict."""

from __future__ import annotations

import typing

from ...domain.model.stage import Stage, StageName, TESTED_KINDS, Trait
from ...domain.model.stage_story import ContractNumber, Count, HandOverName, MappedTest, Place, ScenarioKey, Selector, TestTable
from ...domain.model.verdict import CheckName, Said
from ...domain.service.adopt_checks import AdoptChecks
from ...domain.service.kept_checks import KeptChecks
from ...domain.service.decision_checks import Applying, DecisionChecks
from ...domain.service.integration_checks import IntegrationChecks
from ...domain.model.stage_story import Presence
from ..description.check_description import CheckDescriptionCommand
from ...domain.service.backlog_checks import BacklogChecks
from ...domain.service.delivery_checks import DeliveryChecks
from ...domain.service.design_checks import DesignChecks
from ...domain.service.profile_checks import ProfileChecks
from ...domain.service.spec_checks import SpecChecks
from ...domain.service.story_checks import StoryChecks
from ...domain.service.test_checks import TestChecks
from .check_stage import check, Run
from .pipeline_rules import rule

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


@check("story", rule=rule(
    "GATE-STORY", "every gate", "a story changes one bounded context, and every stage reads which",
    ok="the story, its context and its criteria counted", fail="the front matter names no `context:`"))
def _story(run: Run) -> None:
    run.result.take(StoryChecks.context(run.story))


@check("contract", rule=(
    rule("GATE-CONTRACT", "every gate", "a gate older than the profile would ignore what it does not know",
         ok="the profile's `contract:` is the gate's", fail="`contract:` is no number, or newer than the gate — "
         "`factory.sh update` first", note="no `contract:`, or an older one — read as it is"),
    rule("GATE-PROFILE", "every gate, for each key of the stack profile",
         "a key the pipeline does not read is a typo nobody would notice",
         note="the key is ignored — the nearest known one is named"),
))
def _contract(run: Run) -> None:
    run.result.take(ProfileChecks.contract(run.evidence))


@check("status", rule=rule(
    "GATE-APPROVED", "every gate, where the story carries `status:`", "a human releases a story before code is written",
    ok="`approved`, `adopted` or `delivered`", fail="any other status, `draft` included",
    skip="no `status:` — the project releases otherwise", reports=("approved",)))
def _status(run: Run) -> None:
    run.result.take(StoryChecks.status(run.story))


@check("epic", rule=rule(
    "GATE-EPIC", "every gate", "a story serves an epic whose outcome is said before it is built",
    ok="the epic has intent, goal, metric and domain contact",
    fail="no epic, an incomplete one, a `discovery:` report that is not there, or an epic dependency that does "
         "not hold"))
def _epic(run: Run) -> None:
    run.result.take(BacklogChecks.epic(run.story, run.evidence))


@check("outcome", stages=("plan",), kinds=TESTED_KINDS, rule=rule(
    "GATE-OUTCOME", "the plan gate of a story that `publishes:` an event (contract 14 on)",
    "the event a story raises is the one its epic measures", ok="every published event stands in the epic's metric",
    fail="an event the epic's `metric:` does not name", kinds=("story",)))
def _outcome_named(run: Run) -> None:
    run.result.take(BacklogChecks.outcome(run.story, run.contract, run.evidence))


@check("rounds", rule=rule(
    "GATE-ROUNDS", "every gate, once a story went round", "a story that does not converge goes to a person, not on",
    goes={"fail": "stop"}, ok="round n of at most 3", fail="three rounds without convergence — stop and escalate"))
def _rounds(run: Run) -> None:
    run.result.take(StoryChecks.rounds(run.story, run.evidence))


@check("pipeline", stages=after_plan, rule=rule(
    "GATE-PIPELINE", "every gate after the plan", "a stage that changes the gate changes what it is checked by",
    ok="no stage touched `.agents/factory/`", fail="a stage changed the installed pipeline — put it back"))
def _pipeline(run: Run) -> None:
    run.result.take(DeliveryChecks.pipeline_untouched(run.story, run.evidence))


@check("owned", rule=rule(
    "GATE-OWNED", "every gate, once a stage window was recorded",
    "the story and every answer are the person's — a stage asks, it never answers",
    goes={"fail": "stop"}, ok="nothing a person owns changed during the stage",
    fail="the story or an answer changed under a stage — a person looks and confirms (`--owned-confirm`)"))
def _owned(run: Run) -> None:
    run.result.take(StoryChecks.owned(run.story, run.evidence))


@check("spec-delta", stages=("test",), rule=rule(
    "GATE-SPEC-DELTA", "the test gate, where the plan targets a spec",
    "what holds changes only where a person backed the change",
    ok="the delta adds and holds — nothing that holds changes, or every change is backed",
    fail="the delta does not fit the spec, or changes what holds without `## Changed expectations` or an answer",
    stages=("test", "integrate")))
def _spec_delta(run: Run) -> None:
    run.result.take(SpecChecks.delta(run.story, run.evidence))


@check("spec-tests", stages=("document", "adopt", "integrate"), kinds=TESTED_KINDS, rule=rule(
    "GATE-SPEC-TESTS", "the document, adopt and integrate gates, where the story changes a spec",
    "every criterion that holds keeps the test the spec names",
    ok="every test the spec names for what the story changes is there",
    fail="a test the spec names is gone — it goes under tests.md's `## Moved tests` as it is now"))
def _spec_tests(run: Run) -> None:
    run.result.take(SpecChecks.tests(run.story, table_tests(run.mapping), run.evidence))


@check("tests-committed", stages=("integrate",), kinds=TESTED_KINDS, rule=rule(
    "GATE-TESTS-COMMITTED", "the integrate gate", "a test that is not in the commit proves nothing on the main line",
    ok="every mapped and spec-named test file is in the story's commit as it is",
    fail="a test file is missing from the commit, or differs from it (an ignored one included)"))
def _tests_committed(run: Run) -> None:
    run.result.take(SpecChecks.committed(run.story, table_tests(run.mapping), run.evidence))


@check("plan-files", stages=("build",), rule=rule(
    "GATE-PLAN-FILES", "the build gate (contract 22 on)", "the plan's files are a promise; an explanation is none",
    ok="every file planned `new` is there, every one planned `removed` is gone",
    fail="a planned file is missing or still there — write it, `git rm` it, or plan again",
    skip="the plan has no `## Files`"))
def _plan_files(run: Run) -> None:
    if run.contract.value >= PLAN_FILES_CONTRACT.value:
        run.result.take(DesignChecks.plan_files(run.story, run.evidence))


@check("size", stages=weighed, rule=rule(
    "GATE-SIZE", "the gates that weigh a hand-over (test, build, tidy, document)",
    "a hand-over every later stage reads costs every later stage",
    note="the hand-over is larger than its budget per criterion — never a reason to edit it after the gate ran"))
def _size(run: Run) -> None:
    run.result.take(TestChecks.size(run.story, tuple(HandOverName(name) for name in run.stage.sizes), run.evidence))


def read_table(run: Run) -> typing.Tuple[typing.Dict[str, typing.List[str]], typing.Dict[str, str]]:
    """The run's tests table and its tests located, the findings said: a row for every criterion and no other
    (`tests-mapped`), each test there (`tests-exist`)."""
    path, mapping, unreadable = run.tests.table(run.story_id)
    if unreadable is not None:
        run.result.take((TESTS_MAPPED.fail(Said(unreadable)),))
        return {}, {}
    table = TestTable(Place(path), tuple(ScenarioKey(key) for key in mapping),
                      Count(sum(len(selectors) for selectors in mapping.values())))
    run.result.take(TestChecks.mapped(run.story.criteria, table))
    if not mapping:
        return mapping, {}
    located, looked = run.tests.locate(mapping)
    run.result.take(TestChecks.exist(looked))
    return mapping, located


@check("tests-mapped", stages=tested, kinds=TESTED_KINDS, rule=(
    rule("GATE-TESTS-MAPPED", "every gate that runs tests", "a criterion without a test is one no gate can fail on",
         ok="every criterion has a test, and no row names another",
         fail="the table is unreadable, a criterion has no test, or a row names a criterion the story lacks"),
    rule("GATE-TESTS-EXIST", "every gate that runs tests, for each mapped test",
         "a test that is only a row is indistinguishable from a red one",
         ok="the test is found in its file", fail="no source file, or the class without the method"),
))
def _mapping(run: Run) -> None:
    mapping, located = read_table(run)
    run.mapping, run.located = mapping, (located if mapping else None)


# Integrated, the story's diff carries the main line's changes beside its own: the file list, the tests that existed
# before and the red proof were the stages' to hold, and they held.
@check("files-listed", stages=listing, rule=(
    rule("GATE-FILES-LISTED", "the gates of the stages that list their files (test, build, tidy)",
         "the judge and the next stage read the list, not the tree",
         ok="the hand-over lists every file the stage changed",
         fail="no `## Files`, or a changed file missing from it", skip="the stage's changes were not recorded",
         note="a listed path the stage did not change"),
    rule("GATE-TESTS-KEPT", "the listing gates, against the tests that existed before the story",
         "a test that held before the story keeps holding unless a person backed the change",
         ok="every earlier test kept (lines added only), or each change backed by the plan and an answer",
         fail="an earlier test changed, removed or switched off without backing",
         note="a test arranged around its assertions, or renamed with what it tests",
         skip="no baseline (outside git), or a lost one"),
))
def _files_listed(run: Run) -> None:
    run.result.take(KeptChecks.files_listed(run.story, StageName(run.stage.name), mapped(run), run.evidence))
    run.result.take(KeptChecks.tests_kept(run.story, run.evidence))


@check("test-design", stages=red, rule=(
    rule("GATE-PLAN-LEVELS", "the test gate", "every scenario's level is chosen once, in the plan",
         ok="every key of the plan has its level", fail="a key without `level:`"),
    rule("GATE-INVARIANTS", "the test gate of a story (contract 13 on) or an adoption (24 on)",
         "every rule of a domain type gets a unit test of its own, beside the criteria",
         ok="every invariant the plan names has its own unit test in tests.md's `gate:invariants` table",
         fail="a domain type without an `## Invariants` line, no table, a row that does not fit, or a rule untested",
         kinds=("story", "adopt"), stages=("test", "adopt")),
    rule("GATE-LEVELS", "the test gate of a story with an `e2eTest:` command (contract 9 on)",
         "an end-user test is the happy path's; the rest runs lower",
         ok="end-user tests only for the happy path and browser-only scenarios",
         fail="an end-user test for another scenario — integrate it", kinds=("story",)),
    rule("GATE-CLAUSES", "the test gate of a story with `Then`/`And` clauses (contract 15 on)",
         "each clause is asserted somewhere a reader can find it",
         ok="every clause names the assertion that holds it, at a fitting level",
         fail="no `gate:clauses` table, a clause without a line, no assertion there, or a state clause at "
              "adapter level", kinds=("story",)),
    rule("GATE-TEST-TITLES", "the test gate with end-user tests (contract 9 on), not for an adoption",
         "a reader finds a scenario's test by its title", ok="each end-user test carries its scenario's title",
         fail="an end-user test whose name is not the scenario's title", kinds=("story", "journey")),
))
def _test_design(run: Run) -> None:
    run.result.take(TestChecks.plan_levels(run.story, run.evidence))
    tests = mapped(run)
    run.result.take(DesignChecks.invariants(run.story, run.contract, tests, run.evidence))
    run.result.take(TestChecks.levels(run.story, run.contract, tests, run.evidence))
    run.result.take(DesignChecks.clauses(run.story, run.contract, tests, run.evidence))
    run.result.take(TestChecks.titles(run.story, run.contract, tests, run.evidence))


@check("tests-real", stages=("test", "adopt"), rule=rule(
    "GATE-TESTS-REAL", "the test and adopt gates (contract 21 on)",
    "a criterion's test runs through the real use case; only what lies outside is replaced",
    ok="no integrated or end-to-end test replaces its input port",
    fail="a criterion's test mocks the input port it should drive"))
def _tests_real(run: Run) -> None:
    if run.contract.value >= TESTS_REAL_CONTRACT.value:
        run.result.take(DesignChecks.tests_real(run.story, mapped(run), run.evidence))


@check("red-proof", stages=listing, kinds=TESTED_KINDS, rule=rule(
    "GATE-RED-PROOF", "the gates that expect green (build, tidy; test for a journey or adoption), with a red ledger",
    "a green test proves something only as the version that was seen red",
    goes={"fail": "test"}, ok="no test changed since it was recorded red, or changed on an answer",
    fail="a test changed since its red proof — the test stage records it red again",
    skip="the ledger has no digests (an older one)"))
def _red_proof(run: Run) -> None:
    # the red proof compares digests, so it belongs here, before any process
    if run.expected == "green":
        run.result.take(KeptChecks.red_proof(run.story, StageName(run.stage.name), mapped(run), run.evidence))


@check("suites", rule=rule(
    "GATE-SUITES", "every gate run with `--record-suites`", "a suite run once is reused only under a key",
    note="no `FACTORY_SUITES_KEY` — nothing is recorded or reused"))
def _suites(run: Run) -> None:
    if run.args.record_suites and not run.marks.record_suites(run.story_id):
        run.result.note("suites", "--record-suites without FACTORY_SUITES_KEY in the environment — nothing is "
                                  "recorded or reused")


@check("decisions", rule=rule(
    "GATE-DECISIONS", "every gate", "a question is a record a person answers, and an answer lands where it is cited",
    goes={"ask": "stop"},
    ok="every answered record is applied by its stage and stamped", fail="a `## needs-human` without a record, "
       "a record open or a draft, or an answer its stage did not apply or cite",
    note="no record, or an answer a later stage applies", ask="a stage writes a decision record and stops"))
def _decisions(run: Run) -> None:
    """An answer applied is stamped in its record and becomes an `answered:` line of the story before it is said."""
    checked = DecisionChecks.check(run.story, StageName(run.stage.name), run.evidence)
    for item in checked.items:
        if isinstance(item, Applying):
            run.result.take((DecisionChecks.applied(item, run.stamps.apply(run.story, item)),))
        else:
            run.result.take((item,))


@check("plan-adopts", stages=("plan",), rule=rule(
    "GATE-PLAN-ADOPTS", "the plan gate of a story whose plan has `## Adopt` rows",
    "what already holds is adopted with its test, never built again",
    ok="every row names a criterion and a test that is there", fail="a row names no criterion or a missing test, "
       "or a split would leave the story without its happy path", kinds=("story",)))
def _plan_adopts(run: Run) -> None:
    run.result.take(AdoptChecks.found(run.story, run.evidence))


@check("plan", stages=("plan",), rule=(
    rule("GATE-HAPPY-PATH", "the plan gate of a story (contract 9 on)", "one scenario is the story's happy path, "
         "the one end-user test", ok="exactly one `(happy path)` scenario", fail="none, or more than one",
         skip="an adoption tests nothing new", kinds=("story", "adopt")),
    rule("GATE-JOURNEY", "the plan gate of a journey", "a journey runs over delivered stories",
         ok="the journey names the stories it runs over", fail="no `depends_on:`", kinds=("journey",)),
    rule("GATE-TASK", "the plan gate of a task", "a task changes no behaviour; the existing suite is its evidence",
         ok="no criteria, and every finding it closes is open", fail="a criterion, or `closes:` a finding that is "
         "not open", kinds=("task",)),
    rule("GATE-CONTEXT-MAP", "the plan gate", "a story's context is one the designed domain knows",
         ok="the story's context stands on the context map", fail="it does not, or `domain:` names no file",
         skip="no context map"),
    rule("GATE-INSTRUCTION-SIZE", "the plan gate", "an instruction file over 32 KiB is truncated without a word",
         ok="`AGENTS.md` (or `CLAUDE.md`) is within 32 KiB", skip="it is larger — move detail into referenced files"),
    rule("GATE-DESCRIPTION", "the plan gate", "every stage reads the product and the technical decisions",
         ok="both parts are there with their headings", fail="a part the profile names is missing, or a heading empty",
         note="a part is missing and the profile names none — `/factory-setup` writes it", reports=("product", "tech")),
    rule("GATE-MODELS", "the plan gate, where the profile names models", "a model key nobody reads is a silent default",
         ok="every `model` key names a tool and a stage it knows", fail="a key without a tool, an unknown tool or "
         "stage, or an empty value"),
))
def _plan(run: Run) -> None:
    run.result.take(StoryChecks.happy_path(run.story, run.contract, run.evidence))
    run.result.take(BacklogChecks.context_map(run.story, run.evidence))
    run.result.take(ProfileChecks.instruction_size(run.evidence))
    # the two mandatory parts of the project description — the description feature's check, said as the gate says
    # its checks
    for verdict in run.describe.execute(CheckDescriptionCommand()).verdicts:
        getattr(run.result, verdict.state)(verdict.part, verdict.said)
    run.result.take(ProfileChecks.models(run.evidence))


@check("document", stages=("document",), rule=(
    rule("GATE-STORY-PASS", "the document gate", "a delivery rests on one pass through every stage of the current story",
         goes={"fail": "again"},
         ok="every hand-over is of this pass, the judge said pass, the story unchanged since the plan",
         fail="a hand-over missing or from an earlier pass, no `verdict: pass`, or the story changed since the plan — a "
              "round from where the story's state resumes: the stage of the missing pass, plan for a changed story",
         skip="no story digest from the plan gate"),
    rule("GATE-OUTCOME-RAISED", "the document gate of a story that `publishes:` an event (contract 14 on)",
         "the epic's outcome event is raised by this story's code", ok="the event is declared and raised in what "
         "the story changed", fail="not declared, not raised, or raised only outside the story's files",
         kinds=("story",), reports=("outcome",)),
    rule("GATE-DOCUMENTED", "the document gate", "a document claim is checkable against the code",
         ok="every path resolves and every line names its source",
         fail="a path that does not resolve, a line without `Verified by`, or a `## needs-human`"),
    rule("GATE-GLOSSARY", "the document gate, where the plan proposed terms", "a term the plan proposed lands somewhere",
         ok="every proposed term is in a glossary or under `## Not documented`", fail="a term in neither",
         skip="the project has no glossary"),
    rule("GATE-REVIEWS", "the document gate, for each review perspective of the profile",
         "the judge reads every review it was given", ok="the review was read", fail="a review without findings "
         "sections that says nothing found", note="no review file — the judge ran that pass itself"),
))
def _document(run: Run) -> None:
    passed = DeliveryChecks.story_pass(run.story, run.evidence)
    run.result.take(passed.findings)
    if passed.judge_passed is Presence.PRESENT:
        run.marks.judge_passed(run.story_id)
    run.result.take(DeliveryChecks.outcome_raised(run.story, run.contract, run.evidence))
    run.result.take(DeliveryChecks.documented(run.story, run.evidence))
    run.result.take(DeliveryChecks.proposals_landed(run.story, run.evidence))
    run.result.take(DeliveryChecks.reviews(run.story, run.evidence))


@check("integrate", stages=("integrate",), rule=(
    rule("GATE-INTEGRATE", "the integrate gate", "the integrate step runs in the story's worktree, against its target",
         fail="not in the story's worktree, or no target recorded"),
    rule("GATE-CONFLICTS", "the integrate gate", "a merge is finished before it is checked",
         ok="no unmerged path, no conflict marker", fail="an unmerged path, or a marker in a file the story changed"),
    rule("GATE-MOVED", "the integrate gate", "the main line moved: the step merges again",
         goes={"fail": "integrate"}, fail="the target moved since the merge — merged again, no round"),
    rule("GATE-MAIN-TESTS", "the integrate gate after a merge with conflicts",
         "the main line's tests are its own; a resolution keeps them",
         ok="no test the main line holds was changed by the resolution",
         fail="the resolution changed a main-line test — put its side back",
         note="a test taken as adapted to a rename, or waived by an answer"),
))
def _integrated(run: Run) -> None:
    run.result.take(IntegrationChecks.integrated(run.story, run.evidence))
    run.result.take(IntegrationChecks.main_tests(run.story, run.evidence))
    # The spec as the main line holds it now: a key another story added meanwhile, or a criterion it changed, is a
    # question to a person — never a silent last-writer-wins (WP-98 R3).
    run.result.take(SpecChecks.delta(run.story, run.main_line))
