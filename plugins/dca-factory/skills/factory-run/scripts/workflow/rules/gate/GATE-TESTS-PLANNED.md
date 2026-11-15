---
id: GATE-TESTS-PLANNED
title: The adapter test stands where the plan put it
part: check
kinds:
- story
reports:
- tests-planned
pass: every adapter test the plan names is one of its criterion's tests
fail: the plan gives a criterion the adapter shape without naming its test, or the test it names is not mapped to that criterion
---

# GATE-TESTS-PLANNED

**When:** the test gate runs, for a plan that came about under contract 34 or later (a plan keeps the rules it was
written under: the stamp of the passing plan gate that saw it; a plan from before the stamps counts as contract 33)

**Why:** an adapter test answers from a stubbed input port, so it shows a state the stub hands it and cannot perform
the change its scenario describes; the plan names it after that state, and the test stage keeps the name

The plan writes the adapter's test inside the shape: `integration (adapter: <Adapter>, test: <Class>#<method>)`. The
gate matches it against the criterion's rows of `gate:tests` by the class's simple name and the method; whether the
method exists is `tests-exist`'s. What the name says is not checked — that it names the state shown and not the
scenario's action is the plan's craft.

A round may rename, split or drop a planned adapter test — a judge's finding asks for it. The test stage writes the
change where every later change of the plan stands, in its own file: tests.md's `## Plan changes`,
`- `<old Class#method>` → `<new Class#method>`[, `<new>`] — <why>` (`→ none` for one dropped); the criterion is then held
to the new names and the gate notes the change for the judge. plan.md stays as its gate passed it (`plan-kept`).
