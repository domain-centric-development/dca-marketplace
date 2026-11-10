---
id: STAGE-BACKLOG-6
part: told
why: behaviour the code already had could not enter the backlog without being built again or taken on trust
section: Adopted story
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/backlog-contract.md
---

# STAGE-BACKLOG-6

`status: adopted` describes behaviour the project already has. The factory never builds it; it adopts it:
plan, test and judge map every scenario to a test that exists and is **green**, a test the adoption writes
itself (a *characterization* test, listed under `## Characterization` in `tests.md`) comes with a break —
`.dca-factory/runs/<story>/breaks/<Class>--<method>.patch`, a minimal change to the production code that turns exactly
this test red — and the adopt gate applies each break to a scratch copy, requires red, and delivers the
story (`status: delivered`, `delivered:` and `delivered_by: gate` go into the story — `adopted` was its input,
"the code exists: check it, build nothing", and a delivered story reads the same, built or adopted). The working tree is never touched. `adopt.breakProof: all` in the
profile asks for a break for every mapped test, not only the written ones. A story is adopted whole or not
at all: the adoption writes the tests that are missing. A `depends_on` on an adopted story is met once it
is delivered; afterwards its tests are guarded like any delivered story's.
