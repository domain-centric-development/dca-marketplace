# File contracts between the stages

Every stage is a closed assignment: it reads the story and its predecessor's file, and it
writes exactly one file of its own. No stage relies on chat history, so a stage can run in a
fresh context, in a subagent or in a separate process without changing the result.

| Stage | Reads | Writes |
|---|---|---|
| `stage-plan` | the story, the project's glossary and context map if present | `tasks/<story>/plan.md` |
| `stage-test` | the story, `plan.md` | `tasks/<story>/tests.md` (with the `gate:tests` table) |
| `stage-build` | the story, `plan.md`, `tests.md` | `tasks/<story>/build.md` |
| `stage-tidy` | the story, `plan.md`, `build.md`, and the code as the build stage left it | `tasks/<story>/tidy.md` |
| `stage-judge` | the story and all its predecessors, the diff, and the profile's `reviews:`/`review.<perspective>:` lines | `tasks/<story>/judge.md` |
| `stage-document` | the story, all predecessors, the project's documents and glossaries | `tasks/<story>/document.md` |

`tasks/<story>/.tests-red` records which selectors the test stage actually saw fail. The build gate
requires each green test to appear in it, because a runner that matched **no** test exits 0 exactly
like a passing one: without the record, a criterion with a mistyped or misplaced test would be
certified green. When the file is absent altogether — the run artefacts need not be committed — the
green run is skipped and named rather than trusted or refused.

`tasks/<story>/.rounds` counts the build/judge repeat rounds. It is a file rather than something
the orchestrator remembers, because an in-session run has no other honest way to count and a
resumed run must see the same number. At three the run stops.

A mapped test is run with the profile command that **covers the file it was found in** — the
end-user tests and the unit tests usually live in different projects or source sets, and a selector
run against the wrong one matches nothing. When no declared command covers that path, the gate says
so instead of guessing.

`tasks/` holds run artefacts. Whether they are committed is the project's choice; the pipeline
only requires that a stage finds its predecessor's file.

## The `gate:tests` table

`tasks/<story>/tests.md` carries one machine-readable table. The gate reads nothing else from
the file:

```markdown
<!-- gate:tests -->
| criterion | test |
| --- | --- |
| shows-empty-state | com.example.reporting.MonthlyReportPageTest#showsEmptyState |
| lists-entries | com.example.reporting.MonthlyReportPageTest#listsEntries |
```

- `criterion` is the key from the story's acceptance criteria.
- `test` is `<fully qualified class>#<method>`. The class part is a dotted name: a class in a
  file named after it (`com.example.WidgetTest`), or a module path with an optional class in it
  (`tests.test_widgets`, `tests.test_widgets.TestWidgets`). The stack profile decides how that
  becomes a filter argument for the runner (`filterFormat`, with `{class}`, `{method}` and the
  located `{file}`).
- Every criterion needs at least one row, and the gate looks the test up in the sources: a row
  without a test would look exactly like a red test at the runner, so the run would certify
  nothing. A criterion with no test at all is a criterion the build gate can never fail on.
- Never write a criterion key into a test name, a display name or a comment. The test names the
  behaviour; the table holds the link.

## Escalation

A stage that cannot finish writes its file anyway, with a `## needs-human` section, and the
orchestrator stops the run at that point. Two situations always escalate rather than being solved:

- the plan would need a new bounded context or a new relationship between contexts;
- three build/judge rounds in a row did not converge.

The section names the question as a **decision record** (below): `decision: <id>` on its own
line. A `## needs-human` without one has asked nobody, and the next gate refuses it.

## Decision records — `.agents/factory/decisions/<story>-<nn>.md`

The question a stage may not answer, kept as a file of its own so the answer has a place to land
and a second session — or the same one tomorrow, or another tool — finds it without any
transcript. Committed with the project. Markdown with front matter, from
`templates/decision.md.tmpl`:

```markdown
---
id: US-3-01
story: US-3
stage: plan
asked: 2026-09-22T20:40:00Z
---

# Does an archived entry count?

## Question
<what is asked, why this stage may not decide it, the evidence read>

## Options
- a: <one way>
- b: <another>

## Recommendation
<the stage's view — never an answer>

## Answer
answer: b
by: the-expert
at: 2026-09-22T21:00:00Z
rationale: <optional>
```

- `id` is `<story>-<nn>`, `nn` the next two-digit number among the story's records, and it is
  the file name — the gate finds a record by its name and refuses one whose `id:` disagrees.
- `stage` is the stage that asked. It is the stage that re-runs once the answer is there.
- The state is **read off the file, never stored in it**: no `## Answer` is *open*; an
  `## Answer` with `answer:`, `by:` and `at:` is *answered*; a gate-written `## Applied` is
  *applied*. An `## Answer` missing the name or the time is a draft, and a draft unblocks nothing.
- Only a human writes `## Answer`, or a skill writing the human's exact words on their explicit
  confirmation. A recommendation, a timeout, a preselected option or an unconfirmed draft is not
  an answer.
- The stage that asked **applies** the answer when it runs again: its new file no longer ends in
  `## needs-human` and cites the id where the answer landed (`Decision US-3-01 answered b: …`).
  The gate then stamps `## Applied` into the record. Applied means the plan carries the answer,
  not that the story is delivered.
- The gate checks the store on **every** stage: an open record blocks the story wherever it
  stands, and the runner does not start a stage while one is open.
- `python3 .agents/factory/story-gate.py --list-decisions [--story <id>]` prints the inbox — one
  line per record, open first — which is what the `factory-decisions` skill shows and works from.

What this does not do, on purpose: no leases, no revision numbers, no stale-answer detection when
the story changes underneath, no authorisation beyond `by:`. Files writable by the same user give
process guarantees, not security ones.

## The change policy — `required:` in the stack profile

`story-gate.py --change` checks a change outside a story; `--staged` checks the Git index and refuses
when the working tree differs from it. The profile's `required:` line lists the checks that must
hold: `compile`, `architecture`, `format`, and each test command by its own profile key (`test`,
`test.<name>`, `e2eTest`), so an end-user suite that needs a running system can be declared without
every commit waiting for one. A required check fails when its command is not declared, when it is
left out of the scope (`--checks`, reported as not run here), or — for a test command — when no
report written by the run shows an executed case. A test command that is not required and ran
nothing is named, not failed. Without `required:` the check is
report-only. An older gate would ignore the key and pass what the project declared mandatory,
which is why it raised the file contract to 3.

## Scenario contract — for `--parity`

Markdown, one scenario per `## <id>` heading, with two lines under it:

```markdown
## scenario.thing.shown
Title: The reader sees the thing
Runs: always
```

`Title:` is the binding: a test report names the scenario by carrying the title verbatim as the
test's name (JUnit XML `testcase/@name`, TRX `UnitTestResult/@testName` — a display name in both).
`Runs: always` is mandatory in every implementation; any other value names the configuration the
scenario is bound to, and a run that skips it is reported as *not proven here*, not as passed. The
parity config is flat `key: value`, paths relative to the config file:

```
scenarios: spec/scenarios.md
implementation.first: first/build/test-results/e2e/*.xml
implementation.second: second/tests/E2e/TestResults/*.trx
```

The check reads whatever reports match: delete stale ones, or point the glob at one run's output,
before trusting the verdict.
