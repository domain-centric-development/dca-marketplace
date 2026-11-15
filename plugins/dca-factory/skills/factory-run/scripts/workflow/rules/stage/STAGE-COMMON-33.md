---
id: STAGE-COMMON-33
part: told
why: stages ran the whole suite before the gate ran the same commands, paying twice for one answer
section: The gate is your test run
order: 33
---

# STAGE-COMMON-33

Test, build, tidy: run single tests while working, as often as you like. Done → run the stage's gate
(`story-gate.py --story <id> --stage <stage> --brief`): it compiles, runs every mapped test, the required suites, the
architecture suite and the formatter, and quotes the failing output, assertion included.
- Never run the whole suite yourself first — the gate runs the same commands; you pay twice for one answer.
- Never finish while the gate names something red.
- Write nothing about the gate into your file; edit no hand-over after the gate ran.
- A `gate:note` (a size, an older contract) is for the pipeline's maintainer — never a reason to edit or re-run.
