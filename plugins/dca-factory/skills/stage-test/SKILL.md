---
name: stage-test
description: Test stage of a factory run — writes one end-user test per acceptance criterion plus unit tests for the invariants, and records the criterion-to-test table the story gate reads. Use after the plan stage of a story, when the orchestrator hands over a plan, or on "/stage-test". The tests must compile and be red before any production code is written.
---

# Write the tests for one story

Input: the story and `tasks/<story>/plan.md`. Nothing else.
Output: the test sources, plus `tasks/<story>/tests.md`. You write **no** production behaviour.

## Do

1. Read the plan's criteria and the test shape it chose for each.
2. Write **one end-user test per criterion** in the shape the plan named, using the test
   frameworks the project already has. It asserts the behaviour a user or a caller can observe,
   not the internals. **Change no build file**: adding a dependency, a plugin, a source set or a
   runner is a stack decision, not part of a story. If the planned shape is impossible with what
   is installed, write the tests file with a `## needs-human` section naming the missing runner
   and stop — do not install it, and do not silently drop to a unit test that asserts less.
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
- Do not add architecture or rule tests unless the plan introduces a new structural rule.
- Do not touch a build file, a dependency list or a test-runner configuration.
