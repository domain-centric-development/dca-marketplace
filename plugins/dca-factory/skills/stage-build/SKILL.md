---
name: stage-build
description: Build stage of a factory run — writes the production code that turns the story's red tests green, with the smallest change that works. Use after the test stage of a story, when the orchestrator hands over the failing tests or a gate report, or on "/stage-build". Keeps the domain framework-free and the architecture suite green. Internal stage of the pipeline — factory-run starts it; by hand only to redo this one stage of a story that has the ones before.
---

# Build one story

First read `factory-run/reference/stage-common.md` — the rules every stage holds to: a session the
runner started, one session that carries several stages, a repeat round, the shell, the gate. The
runner's prompt names its path and repeats none of it.

Input: the story, `.dca-factory/runs/<story>/plan.md`, `.dca-factory/runs/<story>/tests.md`, the product
description's `## Look and feel` and `## Qualities` (`project/product.md`, or where the profile's
`product:` points), and — in a repeat round — the gate or judge report. Nothing
else. Open the files the plan's and the tests' `## Files` name first; search the tree only for what
they do not answer.
Output: the production code, plus `.dca-factory/runs/<story>/build.md`.

## Do

1. Read the plan and the failing tests. Implement the **smallest** change that makes them pass —
   the smallest that also meets the product description's `## Look and feel` and `## Qualities`, where
   the change has a surface. A page built to no stated look is correct only where the product
   description states none.
2. Follow the plan's change list. An element the plan did not name is a sign the plan was wrong:
   note it in the build file rather than quietly extending the design. The same holds for a **guard in a
   domain type** — a null check, a trim, a range, a uniqueness rule — that the plan's `## Invariants`
   does not name: it is code no test asked for, so it stays out; name it in the build file as an
   unplanned invariant (`<Element>: <rule>`), and the judge reads it as the plan's gap it is. Every guard
   the plan names has a unit test already — make it pass, add none beside it.
3. Keep the architecture intact — the same rules the plan worked under: no framework types in the
   domain, ports declared inward and implemented in adapters, no raw cross-context imports, one
   aggregate per transaction, domain events published and cleared where the plan says so.
4. Use the project's own building blocks and conventions: its markers, its base types, its
   package layout, its error handling. Where the project ships an architecture rule suite, run it
   and take it as binding.
5. The gate is your test run (`factory-run/reference/stage-common.md`): the single test you are
   making green as often as you like, then the build gate, never the whole suite before it. Do not
   finish while the gate names something red — and write nothing about the gate into your file: its
   report is the record.
6. In a repeat round, work only on what the gate or the judge confirmed. Do not take the
   opportunity to refactor elsewhere.
7. `formatFix:` runs last, before you finish (`factory-run/reference/stage-common.md`).

## Ask, do not recall

Where the profile names `knowledge: <skill>`, ask it instead of your recollection whenever an
answer would decide something, and cite the node by its path inside the catalog; never adopt a
knowledge source the profile did not name. The rule in full: `factory-run/reference/stage-common.md`,
beside this skill.

## Who carries this stage

`carrier.build: <name>` in the stack profile names the skill or agent that holds this project's
craft for it; use it where this tool offers it, otherwise do the stage as described here and say so
in your file. `carrier.guard: <name>` names the skill that holds the architecture's invariants while
you edit — apply it to every file you write, the same way. The rule in full: `factory-
run/reference/stage-common.md`.

## The build file

```markdown
# Build — <story id>

## Changed
| File | Why |
(one row per file this stage changed — the gate checks the table against the files the pipeline
recorded as changed, and the next stages read these files first. The rows' first column is the
pipeline's: run `factory-cli.py --files-skeleton <story> build` when your changes are done — it creates
the file with every changed file as a row, or adds the missing rows to a file you wrote first — and
fill in the why)

## Deviations from the plan
- <element>: <what differed and why>        (omit when there were none — "the plan held" is one word,
                                             not a restatement of its design notes)
```

That is the whole file. The criteria are not restated here — the judge re-checks each one against the
code itself — and the gate's outcome is not recorded here: its report is the evidence, and a stage edits
no hand-over after the gate ran.

## Do not

- Do not change a test to make it pass. **A test that cannot pass because of its own code** — a
  helper, a locator, a fixture, a page object that can never find what the page renders — while what
  it asserts stays exactly as it is, is not yours to repair and not a human's to decide: write the
  finding in `build.md` (the test, the line, why it cannot pass, and how you showed that the code
  meets the scenario) and a line `back: test` on its own; the round goes to the test stage, which
  repairs the test and proves with a break that it still bites.
- **A test whose expectation cannot hold** — two assertions that exclude each other, a substring
  that also matches what must be there — is a question about what the story expects, not a
  deviation: write `## needs-human` naming a decision record with `stage: build` that names the
  test, the line and why it cannot hold, and stop (`factory-run/reference/stage-common.md`). Once a human has answered — and repaired
  the test where the answer says so — the build runs again and cites the id in `build.md`.
- Do not write a criterion key into code, documentation or a comment.
- Do not leave commented-out code, a `TODO` for the criterion you were asked to deliver, or a
  disabled test behind.
