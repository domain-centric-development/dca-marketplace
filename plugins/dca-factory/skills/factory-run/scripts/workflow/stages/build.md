---
name: build
role: builds
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

Read what every stage is told first (its file: in the prompt).

Input, nothing else: the story, `plan.md`, `tests.md` (in `.dca-factory/runs/<story>/`), `## Look and feel` and
`## Qualities` of `product/overview.md` (or `product:`), in a repeat round the gate or judge report. Open the plan's
and the tests' `## Files` first; search the tree only for the rest.
Output: the production code and `.dca-factory/runs/<story>/build.md`.

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
<!-- rule: STAGE-BUILD-9 -->

## Ask, do not recall

`knowledge: <skill>` in the profile: ask it, cite the node path; never a source the profile does not name.

## Who carries this stage

`carrier.build: <name>`: use that skill or agent; none in this tool → do the stage as written here and say so in your
file. `carrier.guard:` applies to every file you write; `carrier.frontend:` to every page, template, stylesheet and
client script.

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

## needs-human                    (only when the specification contradicts itself — otherwise leave it out)
decision: <story>-<nn>
contradiction: <the criterion, the plan line and the test that cannot all hold>
```

That is the whole file: no criteria restated, no gate outcome; no hand-over edited after the gate ran.

## Do not

<!-- rule: STAGE-BUILD-NOT1 -->
<!-- rule: STAGE-BUILD-NOT2 -->
<!-- rule: STAGE-BUILD-NOT3 -->
<!-- rule: STAGE-BUILD-NOT4 -->
<!-- rule: STAGE-BUILD-NOT5 -->
<!-- rule: STAGE-BUILD-NOT6 -->
