---
name: stage-test
description: Test stage of a factory run — writes one end-user test per acceptance criterion plus unit tests for the invariants, and records the criterion-to-test table the story gate reads. Use after the plan stage of a story, when the orchestrator hands over a plan, or on "/stage-test". The tests must compile and be red before any production code is written. Internal stage of the pipeline — factory-run starts it; by hand only to redo this one stage of a story that has the ones before.
---

# Write the tests for one story

Input: the story, `.dca-factory/runs/<story>/plan.md`, and the `## Qualities` and `## Look and feel` of the
product description (`project/product.md`, or where the profile's `product:` points) where the plan
says a criterion touches them. Nothing else. Open the files the plan's
`## Files` names first — the pattern to mirror, the fixture to reuse; search only for the rest.
Output: the test sources, plus `.dca-factory/runs/<story>/tests.md` with a `## Files` section naming the test
files written. You write **no** production behaviour.

## Do

1. Read the plan's criteria and the level it gave each: `e2e` for the happy path, `integration` for
   the others, `browser-only (<why>)` where only a browser observes the `Then`.
2. Write **one test per criterion, at the level the plan gave it** — for a scenario, the test follows its steps: `Given`
   is the arrangement, `When` the one action, `Then` and each `And` after it an assertion, with the
   scenario's own values — in the shape the plan named, using the test
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
   test. A plan line with the bare `integration` of an older plan is the port shape. An external system
   is stubbed **at the protocol**, with the stub the profile names (`http.stub:` — WireMock,
   WireMock.Net): the stub's answer is the test's arrangement, and allowed. Never a mock of the port
   whose adapter the plan changes — that tests everything except the translation — and never a
   shared or real instance, which makes the test pass or fail on another system. Every adapter the
   plan lists as changed is passed by at least one mapped integration test; a case the adapter
   handles that no scenario names (a malformed body, a status the story does not mention) gets an
   integration test outside the table, named under `## Notes`, like the unit tests of step 3.
2b. **A journey item** (`kind: journey`) is a guard over delivered stories: one test that walks the
   epic's `## Journey` to its outcome event, in the source set `test.journey:` declares. It is
   **green** when you finish — every step exists already — and it asserts the outcome event, not
   only a page. It gets no stub for the production code and writes no production code.
2c. **An end-user test's display name is its scenario's title, verbatim** — the `Title:` line under the
   scenario's heading, else its key in words ("Shows empty state"). Two implementations of one story then
   name the test alike; the test gate refuses an end-user test without it.
3. **A unit test for every invariant the plan's `## Invariants` names** — each rule, the guards
   included: a required value refused when absent, a trimmed one refused untrimmed, a range at both
   bounds. The test drives the domain type alone, no framework, and is its own — never a criterion's
   test. `factory-cli.py --files-skeleton <story> test` writes tests.md's `## Invariants` table with one
   row per rule the plan names (element, number, the rule's text); fill in each row's last cell,
   `<Class>#<method>`. The test gate refuses a rule without its own test, a test that is not in the
   project, and a criterion's test in that table. These belong to the domain's own vocabulary and are the part of the suite
   that survives a rewrite of the adapters. A use case gets no unit test of its own from this stage: its
   port test runs it in the wired application, and a second test of the same path with doubles proves
   the doubles.
4. Place tests where this project places tests. Look at the existing layout and follow it —
   source set, folder, naming, base classes, test data builders. Do not introduce a second
   convention next to the project's own.
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

## Notes
- uncovered: <criterion key> — <why no test was possible>   (only when unavoidable)
```

What each test fails on is not written here: the gate's red run records it, assertion by assertion.

The `## Files` list is the pipeline's to write: run `factory-cli.py --files-skeleton <story> test` when your
changes are done — it creates the file with every changed file listed, or adds the missing paths to a file you
wrote first. Fill in the other sections — the `gate:tests` table first of all — **then** run the gate; never type
the list yourself, the gate compares it with the tree. A gate run on the bare skeleton refuses on the empty
table and costs a suite run for nothing.

One row per criterion, at least. A criterion you could not turn into a test is named explicitly
under `uncovered` — never left silently missing, because the build gate can only fail on what a
test covers.

## A round sent back to this stage

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

## Adopt mode

For a story with `status: adopted`: map every scenario in the `gate:tests` table to the existing test the
plan names, green as it is. For a scenario without one, write a **characterization test** — green on
today's code, asserting the scenario's `Then` with its values — list it under `## Characterization` in
`tests.md` (`- <Class>#<method>`), and write its **break**: `.dca-factory/runs/<story>/breaks/<Class>--<method>.patch`,
a unified diff against the working tree that changes the production code minimally so that exactly this
test turns red (`git diff` of the change, then revert it). Change no production code and no existing test;
the gate applies the break to a scratch copy and expects red there.

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
