---
name: build
order: 3
hand_over: build.md
window: builder
kinds:
- story
- task
traits:
- gated
- post_gated
- tested
- lists
- guarded
- suite
- in_order
commands:
- architecture
- format
sizes:
- build.md
---

# build

Writes the production code that turns the story's red tests green, with the smallest change that works.

<!-- frame: what the stage is told, each rule by its marker -->

First read what every stage is told — a session the runner started, one session that carries
several stages, a repeat round, the shell, the gate. The runner's prompt names its file and this
brief repeats none of it.

Input: the story, `.dca-factory/runs/<story>/plan.md`, `.dca-factory/runs/<story>/tests.md`, the product
description's `## Look and feel` and `## Qualities` (`product/overview.md`, or where the profile's
`product:` points), and — in a repeat round — the gate or judge report. Nothing
else. Open the files the plan's and the tests' `## Files` name first; search the tree only for what
they do not answer.
Output: the production code, plus `.dca-factory/runs/<story>/build.md`.

## Do

<!-- rule: STAGE-BUILD-1 -->
<!-- rule: STAGE-BUILD-1A -->
<!-- rule: STAGE-BUILD-2 -->
<!-- rule: STAGE-BUILD-3 -->
<!-- rule: STAGE-BUILD-4 -->
<!-- rule: STAGE-BUILD-4A -->
<!-- rule: STAGE-BUILD-5 -->
<!-- rule: STAGE-BUILD-6 -->
<!-- rule: STAGE-BUILD-7 -->
<!-- rule: STAGE-BUILD-8 -->

## Ask, do not recall

Where the profile names `knowledge: <skill>`, ask it instead of your recollection whenever an
answer would decide something, and cite the node by its path inside the catalog; never adopt a
knowledge source the profile did not name. The rule in full: in what every stage is told.

## Who carries this stage

`carrier.build: <name>` in the stack profile names the skill or agent that holds this project's
craft for it; use it where this tool offers it, otherwise do the stage as described here and say so
in your file. `carrier.guard: <name>` names the skill that holds the architecture's invariants while
you edit — apply it to every file you write, the same way. The rule in full: in what every stage is told.

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

<!-- rule: STAGE-BUILD-NOT1 -->
<!-- rule: STAGE-BUILD-NOT2 -->
<!-- rule: STAGE-BUILD-NOT3 -->
<!-- rule: STAGE-BUILD-NOT4 -->
