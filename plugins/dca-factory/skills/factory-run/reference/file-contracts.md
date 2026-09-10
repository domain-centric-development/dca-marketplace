# File contracts between the stages

Every stage is a closed assignment: it reads the story and its predecessor's file, and it
writes exactly one file of its own. No stage relies on chat history, so a stage can run in a
fresh context, in a subagent or in a separate process without changing the result.

| Stage | Reads | Writes |
|---|---|---|
| `stage-plan` | the story, the project's glossary and context map if present | `tasks/<story>/plan.md` |
| `stage-test` | the story, `plan.md` | `tasks/<story>/tests.md` (with the `gate:tests` table) |
| `stage-build` | the story, `plan.md`, `tests.md` | `tasks/<story>/build.md` |
| `stage-judge` | the story and all three predecessors, the diff, and the profile's `reviews:`/`review.<perspective>:` lines | `tasks/<story>/judge.md` |

`tasks/<story>/.rounds` counts the build/judge repeat rounds. It is a file rather than something
the orchestrator remembers, because an in-session run has no other honest way to count and a
resumed run must see the same number. At three the run stops.

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
- `test` is `<fully qualified class>#<method>`. The stack profile decides how that becomes a
  filter argument for the runner (`filterFormat`).
- Every criterion needs at least one row, and the gate looks the test up in the sources: a row
  without a test would look exactly like a red test at the runner, so the run would certify
  nothing. A criterion with no test at all is a criterion the build gate can never fail on.
- Never write a criterion key into a test name, a display name or a comment. The test names the
  behaviour; the table holds the link.

## Escalation

A stage that cannot finish writes its file anyway, with a `## needs-human` section naming the
open decision. The orchestrator stops the run at that point. Two situations always escalate
rather than being solved:

- the plan would need a new bounded context or a new relationship between contexts;
- three build/judge rounds in a row did not converge.
