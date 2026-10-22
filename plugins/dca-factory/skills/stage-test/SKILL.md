---
name: stage-test
description: Test stage of a factory run — writes one end-user test per acceptance criterion plus unit tests for the invariants, and records the criterion-to-test table the story gate reads. Use after the plan stage of a story, when the orchestrator hands over a plan, or on "/stage-test". The tests must compile and be red before any production code is written. Internal stage of the pipeline — factory-run starts it; by hand only to redo this one stage of a story that has the ones before.
---

# Write the tests for one story

First read `factory-run/reference/stage-common.md` — the rules every stage holds to: a session the
runner started, one session that carries several stages, a repeat round, the shell, the gate. The
runner's prompt names its path and repeats none of it.

Input: the story, `.dca-factory/runs/<story>/plan.md`, and the `## Qualities` and `## Look and feel` of the
product description (`product/overview.md`, or where the profile's `product:` points) where the plan
says a criterion touches them. Nothing else. Open the files the plan's
`## Files` names first — the pattern to mirror, the fixture to reuse; search only for the rest.
Output: the test sources, plus `.dca-factory/runs/<story>/tests.md` with a `## Files` section naming the test
files written. You write **no** production behaviour.

## Do

1. Read the plan's criteria and the level it gave each: `e2e` for the happy path, `integration` for
   the others, `browser-only (<why>)` where only a browser observes the `Then`.
2. Write **one test per criterion, at the level the plan gave it** — for a scenario, the test follows its steps: `Given`
   is the arrangement, `When` the one action, `Then` and each `And` after it an assertion, with the
   scenario's own values — the `Given` arranged with them even where the outcome seems not to depend on
   it (a refusal that answers alike for an empty and a full state still starts from the state the
   scenario names) — in the shape the plan named, using the test
   frameworks the project already has. It asserts the behaviour a user or a caller can observe,
   not the internals. **Change no build file**: adding a dependency, a plugin, a source set or a
   runner is a stack decision, not part of a story. If the planned shape is impossible with what
   is installed, write the tests file with a `## needs-human` section naming the missing runner
   and stop — do not install it, and do not silently drop to a unit test that asserts less. The
   section names a decision record with `stage: test` (the shape, and the citation of an answered
   record: `factory-run/reference/stage-common.md`).
   Where the profile names a browser runner (`browser:` other than `none`), an end-user test of a page drives the browser: use
   the end-user testing craft (the `e2e-testing` skill, or the profile's `carrier.test`) — the
   application started by the test, the fake clock for anything that counts or expires, a stand-in for
   a permission the user answers. Never read the page's script or markup as text to infer what the
   browser would do.
2a. **An integration test** has the shape the plan wrote after its level, in the source set a
   `test.<name>:` key declares. `integration (port)`: the use case through its input port in the wired
   application, with real outgoing adapters and persistence as the project runs it in tests — the
   scenario's outcome asserted on what the use case returns, stores or publishes. `integration (adapter:
   <Adapter>)`: that incoming adapter's translation — the request it turns into a command, the page,
   status or payload it makes of the result and of each refusal — against a stubbed input port that
   answers with the outcome; stubbing the input port here is right, the use case behind it has its own
   test. **A clause about what is stored** — the list stays unchanged, the task remains open, it is done
   afterwards — is never asserted here: the stub answers what you told it, so the assertion holds whatever
   the code does. Assert it through the input port with the real store (`integration (port)`), or end to end;
   the adapter test asserts only the adapter's part (the status, the page, that the use case was not called). A plan line with the bare `integration` of an older plan is the port shape. An external system
   is stubbed **at the protocol**, with the stub the profile names (`http.stub:` — WireMock,
   WireMock.Net): the stub's answer is the test's arrangement, and allowed. Never a mock of the port
   whose adapter the plan changes — that tests everything except the translation — and never a
   shared or real instance, which makes the test pass or fail on another system. Every adapter the
   plan lists as changed is passed by at least one mapped integration test; a case the adapter
   handles that no scenario names (a malformed body, a status the story does not mention) gets an
   integration test outside the table, named under `## Notes`, like the unit tests of step 3.
   **Every branch the story adds in an adapter has a test** — the success, each refusal, each fallback
   (input that does not parse, so the port is never called): one test per branch, not one per adapter.
   An outgoing adapter that keeps state of its own beside what it stores — an index, a lookup by a second
   key — gets an adapter test that saves, changes and saves again, and asserts the lookup after the
   second save.
2b. **A journey item** (`kind: journey`) is a guard over delivered stories: one test that walks the
   epic's `## Journey` to its outcome event, in the source set `test.journey:` declares. It is
   **green** when you finish — every step exists already — and it asserts the outcome event, not
   only a page. It gets no stub for the production code and writes no production code.
2c. **An end-user test's display name is its scenario's title, verbatim** — the `Title:` line under the
   scenario's heading, else its key in words ("Shows empty state"). Two implementations of one story then
   name the test alike; the test gate refuses an end-user test without it.
2d. **Every test starts from a state it sets itself, and asserts an element.** A suite that shares one application
   and one store empties what its tests write before each test — the base class does it, through the reset the
   profile's `reset:` names, the end-user suite included; a scenario that begins "the list is empty" is then
   true. An assertion names what it is about — a selector, a role, a field, a row — never the page's whole
   text: `contains("disabled")` is true whenever any element is disabled. A test of a criterion above the unit
   level runs through the real input port, except at the plan's `integration (adapter: …)` level; the test gate
   refuses the double (`tests-real`).
2e. **Every assertion could fail.** Ask of each one: with the behaviour absent, would it turn red? An assertion on
   a mechanism the code does not use (a flash attribute count where the page renders its message from the
   model), a count of something nothing writes, an absence that holds before the feature exists — each is green
   whatever the code does. So is an assertion inside an `if` (or a loop over a filtered list): when nothing
   meets the condition it asserts nothing. So is an absence checked right after the action without waiting:
   it holds before the page has reacted — wait for the state the action leads to first, then assert what is
   absent (the end-user craft: waits are explicit). Assert the element the criterion names, in the state it
   names: "no message" is the message's element absent from the page the user sees, not an empty map beside it.
   **One break probe per clause.** For each row of `## Clauses`, name the smallest change to the production
   code that violates that clause and leaves the others standing — the message not shown, the value not
   stored, the order reversed — and check that the assertion on that clause's line turns red under it. A
   test stops at its first failing assertion, so its red run proves the first clause only; for new
   behaviour the probe is the red phase taken clause by clause, not test by test. A clause no probe can
   turn red is asserted too weakly: sharpen the assertion before the gate.
3. **A unit test for every invariant the plan's `## Invariants` names** — each rule, the guards
   included: a required value refused when absent, a trimmed one refused untrimmed, a range at both
   bounds. The test drives the domain type alone, no framework, and is its own — never a criterion's
   test. `factory-cli.py --files-skeleton <story> test` writes tests.md's `## Invariants` table with one
   row per rule the plan names (element, number, the rule's text); fill in each row's last cell,
   `<Class>#<method>`. The test gate refuses a rule without its own test, a test that is not in the
   project, and a criterion's test in that table. Each rule's test must be shown to guard it: a test of a rule
   the code does not have yet is red before the build, and that is its proof; a test of a rule the code has
   already is green, so write its **break** — `.dca-factory/runs/<story>/breaks/<Class>--<method>.patch`, the
   smallest `git apply` change to the production code that turns exactly this test red (`git diff` of the
   change, then revert it). The gate runs every rule's test once, then each break on one scratch copy; a test
   that stays green under its break, or a green one without a break, is refused (`invariant-breaks`). These belong to the domain's own vocabulary and are the part of the suite
   that survives a rewrite of the adapters. A use case gets no unit test of its own from this stage: its
   port test runs it in the wired application, and a second test of the same path with doubles proves
   the doubles.
4. Place tests where this project places tests. Look at the existing layout and follow it —
   source set, folder, naming, base classes, test data builders. Do not introduce a second
   convention next to the project's own. **Before you write a helper, a page-object call or a
   context setup, find the existing one** — in the base classes, the page objects, the other tests of
   the same level — and call it. Where the same code stands in two places already, the third use
   extracts it into the shared test support (a base class, a builder, a page object) and calls it from
   there; the test support is yours to change, the tests that existed before keep what they assert.
5. Name the test after the behaviour: `showsEmptyStateWhenNothingIsRecorded`. **Never** write a
   criterion key or number into a test name, display name, comment or documentation. The link
   between criterion and test lives in the table below and nowhere else — one place the gate reads,
   one place two implementations of the same story share; a key in a name is a second link that
   drifts when the story is renumbered, and the display name is the scenario's title (step 2), which
   already says which scenario a report is about.
6. Write the types the tests need to compile — and draw the line at **behaviour**. A type with nothing a
   criterion observes is structure, and structure is written whole here: a record with its fields and a
   null guard, an enum with its values, an interface with its methods, an exception type with its
   message. A method whose outcome a criterion asserts — a validation, a state change, a query's
   answer, a use case's body — is a stub that **refuses to answer**: it throws
   (`UnsupportedOperationException`, `NotImplementedException`, whatever the language calls it). It
   never returns a value, not even an empty list or a default — for a criterion whose expected answer
   *is* the empty case, a stub returning empty makes the test green before any code exists, and a green
   test at this stage proves nothing. The gate refuses it, and rightly: the criterion would ship
   uncovered. The line in one sentence: whatever a criterion observes, throws.
7. The gate is your test run (`factory-run/reference/stage-common.md`): a single test while you
   write it — that is where you see the assertion it fails on — then the test gate, never the whole
   suite before it. Confirm two things from its report: the test sources compile, and every new test
   fails **on its assertion**, not on a missing class or a wiring error. A test red for the wrong
   reason proves nothing. In a browser test the first step
   that can be missing is an expectation, not an action: `expect(locator).toBeVisible()` before the
   click or the fill, so a form that does not exist yet fails on the expectation and names what is
   missing. A raw `TimeoutError` from an action is red on the harness — the gate accepts the red and
   notes it, and the build stage learns nothing from it.
8. Delete every spike, scratch or exploration test before you finish. A passing spike trips no
   gate, so nothing else will catch it.
9. `formatFix:` runs last, before you finish (`factory-run/reference/stage-common.md`).

## Ask, do not recall

Where the profile names `knowledge: <skill>`, ask it instead of your recollection whenever an
answer would decide something, and cite the node by its path inside the catalog; never adopt a
knowledge source the profile did not name. The rule in full: `factory-run/reference/stage-common.md`,
beside this skill.

## Who carries this stage

`carrier.test: <name>` in the stack profile names the skill or agent that holds this project's craft
for it; use it where this tool offers it, otherwise do the stage as described here and say so in
your file. The rule in full: `factory-run/reference/stage-common.md`.

## The tests file

`.dca-factory/runs/<story>/tests.md`, with exactly one machine-readable table — the gate reads this and
nothing else from the file:

```markdown
# Tests — <story id>

<!-- gate:tests -->
| criterion | test |
| --- | --- |
| <criterion key> | <fully.qualified.Class>#<method> |

## Files
- <every test file this stage wrote or changed, one per line — written by the pipeline, see below>

## Invariants                     (written by --files-skeleton, one row per rule of the plan's `## Invariants`)
<!-- gate:invariants -->
| element | rule | invariant | test |
| --- | --- | --- | --- |
| <Element> | <n> | <the rule, from the plan> | <fully.qualified.Class>#<method> |

## Clauses                        (contract 15; written by --files-skeleton, one row per Then and each And after it)
<!-- gate:clauses -->
| criterion | n | clause | assertion | level |
| --- | --- | --- | --- | --- |
| <criterion key> | <n> | <the clause, from the story> | <path/to/Test.java>:<line> | unit / port / adapter / e2e |

## Notes
- uncovered: <criterion key> — <why no test was possible>   (only when unavoidable)
```

What each test fails on is not written here: the gate's red run records it, assertion by assertion.

`## Clauses` (contract 15) holds every expectation of every scenario — its `Then` and each `And` after it — with the
line that asserts it, in a test mapped to that criterion, and the level the assertion runs at. Fill it in after the
tests are written and formatted: the test gate refuses a clause without a line, a line where nothing is asserted, and
a clause about what is stored at the `adapter` level. A scenario whose third `And` has no row is the test that
forgot it — write the assertion, then the row.

The `## Files` list is the pipeline's to write: run `factory-cli.py --files-skeleton <story> test` when your
changes are done — it creates the file with every changed file listed, or adds the missing paths to a file you
wrote first. Fill in the other sections — the `gate:tests` table first of all — **then** run the gate; never type
the list yourself, the gate compares it with the tree. A gate run on the bare skeleton refuses on the empty
table and costs a suite run for nothing.

One row per criterion, at least. A criterion you could not turn into a test is named explicitly
under `uncovered` — never left silently missing, because the build gate can only fail on what a
test covers.

## A round sent back to this stage

Where `judge.md` in the run folder says `verdict: changes-requested`, fix exactly the confirmed defects
that are this stage's — a test that asserts too little, with its break (see the contract) — nothing else.
When the judge's verdict says `back: test` (`.dca-factory/runs/<story>/judge.md`), fix exactly the test
defects it confirmed: add the assertion the criterion names, nothing else. When the build stage wrote
`back: test` (`.dca-factory/runs/<story>/build.md`), a test cannot pass because of its own code — a
helper, a locator, a page object: repair exactly that, and leave what the test asserts as it is. The code already meets it, so
the strengthened test is green and can never be seen red. Prove instead that it bites: write its
**break** — `.dca-factory/runs/<story>/breaks/<fully.qualified.Class>--<method>.patch`, a `git apply` patch
against the production code, the smallest change that removes what the new assertion checks (the word
from the template, the link from the page). The gate applies it on a scratch copy, runs the test, wants
it red, and records the test's new version; the tree stays as it is. A test you did not change needs no
break. List the changed tests and their breaks under `## Files`.

When the prompt says the story's tests changed after this stage saw them fail — the main line was merged into
the story's branch — record each test it names as it now is: what it asserts stays the story's, so change
nothing in it. Where the code already meets it, it is green and gets its break the same way; where it is still
red, the gate records the red run. Ask nobody about it.

## Adopt mode

For a story with `status: adopted`: map every scenario in the `gate:tests` table to the existing test the
plan names, green as it is. For a scenario without one, write a **characterization test** — green on
today's code, asserting the scenario's `Then` with its values — list it under `## Characterization` in
`tests.md` (`- <Class>#<method>`), and write its **break**: `.dca-factory/runs/<story>/breaks/<Class>--<method>.patch`,
a unified diff against the working tree that changes the production code minimally so that exactly this
test turns red (`git diff` of the change, then revert it). Change no production code and no existing test;
the gate applies the break to a scratch copy and expects red there. The plan's invariants are held the same
way: every rule gets its row in the `gate:invariants` table — an existing unit test that asserts exactly that
rule, or a characterization unit test you write, listed under `## Characterization` with its break. The adopt
gate runs every rule's test green beside the scenarios' tests.

## Do not

- Do not implement production behaviour to make a test pass.
- Do not weaken an assertion to get a test to run.
- Do not change what a test that existed before this story expects — unless the plan lists it
  under `## Changed tests`. Change those to the story's new expectation; everywhere else add a
  case and leave the old lines as they are. The gate compares every test file against the state
  the plan gate recorded and refuses a changed or removed line the plan does not list and back —
  except around the assertions: where a type the test builds gains a field, give the old call the
  new argument and keep every assertion, its expected values and matchers as they were. That is
  no changed expectation and needs no question.
  A contradicting test the plan missed is a question (a decision record with `stage: test`).
- Do not add architecture or rule tests unless the plan introduces a new structural rule.
- Do not touch a build file, a dependency list or a test-runner configuration.
