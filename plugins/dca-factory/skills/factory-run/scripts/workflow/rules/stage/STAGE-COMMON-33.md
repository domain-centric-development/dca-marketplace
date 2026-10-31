---
id: STAGE-COMMON-33
part: told
section: The gate is your test run
order: 33
---

# STAGE-COMMON-33

For the stages that write code — test, build, tidy: run a single test while you work, as often as
you like; when you believe the stage is done, run the stage's gate (`story-gate.py --story <id>
--stage <stage> --brief`). It compiles the sources and runs every mapped test and the required
suites once per command, the architecture suite and the formatter, and fails on exactly what is
red. Its refusal quotes the failing test's own output, the assertion included — there is nothing a
suite run of your own would show you that the gate's report does not. Do not run the whole suite
yourself before it: the gate runs the same commands, and a stage that runs them first pays twice for
one answer. Do not finish while the gate names something red — and write nothing about the gate into
your file: its report is the record, and a stage edits no hand-over after the gate ran. A `gate:note`
(a size, an older contract) is information for whoever maintains the pipeline; it is never a reason
to edit your file after the gate ran, and never a reason to run the gate again.
