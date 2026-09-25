---
name: stage-test
description: Test stage of a factory run — writes one end-user test per acceptance criterion plus unit tests for the invariants, and records the criterion-to-test table the story gate reads. Use after the plan stage of a story, when the orchestrator hands over a plan, or on "/stage-test". The tests must compile and be red before any production code is written.
---

# Write the tests for one story

Input: the story, `tasks/<story>/plan.md`, and the `## Qualities` and `## Look and feel` of the
product scope where the plan says a criterion touches them. Nothing else. Open the files the plan's
`## Files` names first — the pattern to mirror, the fixture to reuse; search only for the rest.
Output: the test sources, plus `tasks/<story>/tests.md` with a `## Files` section naming the test
files written. You write **no** production behaviour.

## Do

1. Read the plan's criteria and the test shape it chose for each.
2. Write **one end-user test per criterion** — for a scenario, the test follows its steps: `Given`
   is the arrangement, `When` the one action, `Then` and each `And` after it an assertion, with the
   scenario's own values — in the shape the plan named, using the test
   frameworks the project already has. It asserts the behaviour a user or a caller can observe,
   not the internals. **Change no build file**: adding a dependency, a plugin, a source set or a
   runner is a stack decision, not part of a story. If the planned shape is impossible with what
   is installed, write the tests file with a `## needs-human` section naming the missing runner
   and stop — do not install it, and do not silently drop to a unit test that asserts less. The
   section names a decision record (`decision: <story>-<nn>`), written to
   `.agents/factory/decisions/<story>-<nn>.md` with the front matter `id: <story>-<nn>`,
   `story:`, `stage: test`, `asked:` (UTC) and the sections `## Question`, `## Options`,
   `## Recommendation` — never an answer (full shape: `factory-run/templates/decision.md.tmpl`).
   Where the profile names a browser runner (`browser:` other than `none`), an end-user test of a page drives the browser: use
   the end-user testing craft (the `e2e-testing` skill, or the profile's `carrier.test`) — the
   application started by the test, the fake clock for anything that counts or expires, a stand-in for
   a permission the user answers. Never read the page's script or markup as text to infer what the
   browser would do.
3. Add unit tests for the invariants the plan names: the rules an aggregate or value object must
   never break. These belong to the domain's own vocabulary and are the part of the suite that
   survives a rewrite of the adapters.
4. Place tests where this project places tests. Look at the existing layout and follow it —
   source set, folder, naming, base classes, test data builders. Do not introduce a second
   convention next to the project's own.
5. Name the test after the behaviour: `showsEmptyStateWhenNothingIsRecorded`. **Never** write a
   criterion key or number into a test name, display name, comment or documentation. The link
   between criterion and test lives in the table below and nowhere else.
6. Add only the minimum stubs the test sources need to compile — a class, an empty method, a
   port interface. A stub **refuses to answer**: it throws (`UnsupportedOperationException`,
   `NotImplementedException`, whatever the language calls it). It never returns a value, not even
   an empty list or a default — for a criterion whose expected answer *is* the empty case, a stub
   returning empty makes the test green before any code exists, and a green test at this stage
   proves nothing. The gate refuses it, and rightly: the criterion would ship uncovered.
7. Run the project's compile and test commands from the stack profile. Confirm two things: the
   test sources compile, and every new test fails **on its assertion**, not on a missing class or
   a wiring error. A test red for the wrong reason proves nothing.
8. Delete every spike, scratch or exploration test before you finish. A passing spike trips no
   gate, so nothing else will catch it.
9. Where the stack profile declares `formatFix:`, run it last, before you finish: it corrects the
   formatting of what you wrote, so the stages after you find their own files as the formatter
   wants them. The gate and the commit hook only check `format:` and change no file.

## Ask, do not recall — but only a source the project named

Where the stack profile names a **knowledge skill** — `knowledge: <skill>`, one that answers
architecture questions from a catalog and cites the node it read — use it instead of your own
recollection whenever the answer would decide something: which pattern applies, why a rule exists,
whether a construct is a pitfall, what a recipe prescribes. Name the node you relied on in your
file, the way you name a file and line for a claim about the code.

**Never adopt a knowledge source the profile did not name.** A catalog that happens to be installed
may be a vendored copy of an older release: its rule ids, marker names and recipes can describe a
version the project does not use, and a citation makes that wrongness look verified. If you notice
such a skill, say so in your file — "`<skill>` is available but not named in the profile, so it was
not used" — and decide from the project's own rules, markers and documents instead. Those are the
source of truth; a catalog is a convenience the project has to vouch for.

Without a `knowledge:` entry, work from what the project itself carries: its rule catalog and the
report its architecture suite prints, its building blocks, its glossary, its documents. Nothing
here fails for the absence of a knowledge skill.

## Who carries this stage

The stack profile may name a carrier for this stage — `carrier.test: <name>` — the skill or
agent that holds this project's craft for it. A review **skill** works in every tool; an **agent**
only where the tool has agents. Use the named carrier when this tool offers it; otherwise do the
stage as described here and say in your file which it was ("in-session; `<carrier>` not available
here"). A missing carrier is a missing preference, never a reason to skip the stage.

## The tests file

`tasks/<story>/tests.md`, with exactly one machine-readable table — the gate reads this and
nothing else from the file:

```markdown
# Tests — <story id>

<!-- gate:tests -->
| criterion | test |
| --- | --- |
| <criterion key> | <fully.qualified.Class>#<method> |

## Files
- <every test file this stage wrote or changed, one per line>

## Notes
- <test>: currently fails on <the assertion>, because <what is missing>
- unit tests: <class>#<method> for invariant <rule>
- uncovered: <criterion key> — <why no test was possible>   (only when unavoidable)
```

One row per criterion, at least. A criterion you could not turn into a test is named explicitly
under `uncovered` — never left silently missing, because the build gate can only fail on what a
test covers.

## Do not

- Do not implement production behaviour to make a test pass.
- Do not weaken an assertion to get a test to run.
- Do not change what a test that existed before this story expects — unless the plan lists it
  under `## Changed tests`. Change those to the story's new expectation; everywhere else add a
  case and leave the old lines as they are. The gate compares every test file against the state
  the plan gate recorded and refuses a changed or removed line the plan does not list and back.
  A contradicting test the plan missed is a question (a decision record with `stage: test`).
- Do not add architecture or rule tests unless the plan introduces a new structural rule.
- Do not touch a build file, a dependency list or a test-runner configuration.
