---
name: test
role: tests
order: 2
hand_over: tests.md
window: builder
kinds:
- story
- journey
- adopt
traits:
- gated
- post_gated
- tested
- red
- lists
- in_order
sizes:
- plan.md
- tests.md
---

# test

Writes a test per criterion at the level the plan gives it, plus unit tests for the invariants, and records the criterion-to-test table; the tests are red before any production code is written.

<!-- frame: what the stage is told, each rule by its marker -->

First read what every stage is told — a session the runner started, one session that carries
several stages, a repeat round, the shell, the gate. The runner's prompt names its file and this
brief repeats none of it.

Input: the story, `.dca-factory/runs/<story>/plan.md`, and the `## Qualities` and `## Look and feel` of the
product description (`product/overview.md`, or where the profile's `product:` points) where the plan
says a criterion touches them. Nothing else. Open the files the plan's
`## Files` names first — the pattern to mirror, the fixture to reuse; search only for the rest.
Output: the test sources, plus `.dca-factory/runs/<story>/tests.md` with a `## Files` section naming the test
files written. You write **no** production behaviour.

## Do

<!-- rule: STAGE-TEST-1 -->
<!-- rule: STAGE-TEST-2 -->
<!-- rule: STAGE-TEST-2A -->
<!-- rule: STAGE-TEST-2B -->
<!-- rule: STAGE-TEST-2C -->
<!-- rule: STAGE-TEST-2D -->
<!-- rule: STAGE-TEST-2E -->
<!-- rule: STAGE-TEST-3 -->
<!-- rule: STAGE-TEST-4 -->
<!-- rule: STAGE-TEST-5 -->
<!-- rule: STAGE-TEST-6 -->
<!-- rule: STAGE-TEST-7 -->
<!-- rule: STAGE-TEST-8 -->
<!-- rule: STAGE-TEST-9 -->

## Ask, do not recall

Where the profile names `knowledge: <skill>`, ask it instead of your recollection whenever an
answer would decide something, and cite the node by its path inside the catalog; never adopt a
knowledge source the profile did not name. The rule in full: in what every stage is told.

## Who carries this stage

`carrier.test: <name>` in the stack profile names the skill or agent that holds this project's craft
for it; use it where this tool offers it, otherwise do the stage as described here and say so in
your file. The rule in full: in what every stage is told.

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

<!-- rule: STAGE-TEST-ROUND -->

When the prompt says the story's tests changed after this stage saw them fail — the main line was merged into
the story's branch — record each test it names as it now is: what it asserts stays the story's, so change
nothing in it. Where the code already meets it, it is green and gets its break the same way; where it is still
red, the gate records the red run. Ask nobody about it.

## Adopt mode

<!-- rule: STAGE-TEST-ADOPT -->

## Do not

<!-- rule: STAGE-TEST-NOT1 -->
<!-- rule: STAGE-TEST-NOT2 -->
<!-- rule: STAGE-TEST-NOT3 -->
<!-- rule: STAGE-TEST-NOT4 -->
<!-- rule: STAGE-TEST-NOT5 -->
