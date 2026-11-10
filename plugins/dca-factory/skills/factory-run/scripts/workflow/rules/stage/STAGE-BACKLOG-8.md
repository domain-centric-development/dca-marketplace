---
id: STAGE-BACKLOG-8
part: told
why: what holds today was scattered across stories, so nobody could read current behaviour without replaying them
section: The living spec
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/backlog-contract.md
---

# STAGE-BACKLOG-8

A story is a change; `product/spec/` (the configuration's `spec:`) holds what is true today, per bounded context
and feature: `<spec>/<context>/<feature>/scenarios.md` for each feature — a term of the context's language with a
glossary entry of `**Type:** Feature`, named as the code's package would spell it (`productdetails`) — and
`<spec>/<context>/scenarios.md` for what belongs to no feature. `<context>` is the story's `context:`, lowercase,
words joined by `-`; `<feature>` its `feature:` (none: the context's own file). A story names at most one feature —
criteria of several are several stories. Every file carries the criteria that hold, in the story's own shape: a scenario under its `### Rule:`, or a
line; criteria without a rule before the first rule. No status, no ticks, no happy-path mark, no story id.
Under each criterion one `Test: <selector>` line, written by the gate alone from the story's `tests.md`; a
criterion without one, or with a red test, is unproven, readable without the factory. Journeys stand in
`<spec>/journeys.md`, keyed by the flow; a `kind: journey` item merges there. `glossary.md` beside a
context's scenarios is its language, kept by the glossary skill and the document stage — the one file under
`spec/` a skill writes.
