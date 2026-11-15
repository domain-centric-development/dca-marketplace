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

Read what every stage is told first (its file: in the prompt).

Input, nothing else: the story, `.dca-factory/runs/<story>/plan.md`, and `## Qualities` / `## Look and feel` of
`product/overview.md` (or `product:`) where the plan says a criterion touches them. Open the plan's `## Files` first;
search only for the rest.
Output: the test sources and `.dca-factory/runs/<story>/tests.md`. **No** production behaviour.

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

`knowledge: <skill>` in the profile: ask it, cite the node path; never a source the profile does not name.

## Who carries this stage

`carrier.test: <name>`: use that skill or agent; none in this tool → do the stage as written here and say so in your file.

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

- The gate's red run records what each test fails on; do not write it here.
- `## Clauses`: every `Then` and each `And` after it, with the asserting line in a test mapped to that criterion and
  its level. Fill after the tests are written and formatted. Refused: a clause without a line, a line asserting
  nothing, a stored-state clause at `adapter` level. A missing `And` row = a missing assertion: write it, then the row.
- `## Files`: when your changes are done run `factory-cli.py --files-skeleton <story> test` (creates the file or adds
  missing paths); never type the list. Fill `gate:tests` first, **then** run the gate — a bare skeleton is refused
  and wastes a suite run.
- At least one row per criterion. A criterion without a test goes under `uncovered`, never silently missing: the
  build gate fails only on what a test covers.

## A round sent back to this stage

<!-- rule: STAGE-TEST-ROUND -->

Prompt says the story's tests changed after this stage saw them fail (main merged into the branch): record each
named test as it now is, change nothing in it. Green → it gets its break; still red → the gate records the red run.
Ask nobody.

## Adopt mode

<!-- rule: STAGE-TEST-ADOPT -->

## Do not

<!-- rule: STAGE-TEST-NOT1 -->
<!-- rule: STAGE-TEST-NOT2 -->
<!-- rule: STAGE-TEST-NOT3 -->
<!-- rule: STAGE-TEST-NOT4 -->
<!-- rule: STAGE-TEST-NOT5 -->
