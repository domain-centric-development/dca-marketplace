---
name: tidy
order: 4
hand_over: tidy.md
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
- tidy.md
---

# tidy

The refactor step the build stage skips, taken with every test green and without changing behaviour — so its whole claim is that everything still holds: its gate runs the build's commands again after the refactor.

<!-- frame: what the stage is told, each rule by its marker -->

First read what every stage is told — a session the runner started, one session that carries
several stages, a repeat round, the shell, the gate. The runner's prompt names its file and this
brief repeats none of it.

Input: the story, `.dca-factory/runs/<story>/plan.md`, `.dca-factory/runs/<story>/build.md`, and the code as the build
stage left it — green: the files `.dca-factory/evidence/<story>/changed.txt` lists, which the pipeline
recorded from the working tree. Nothing else. Every file you change is a row under `## Moves`; the
gate checks the table against what changed.
Output: the tidied code, plus `.dca-factory/runs/<story>/tidy.md`.

The build stage answers the criteria with the smallest change that works, which is the right thing
for it to do and leaves the second half of red–green–refactor undone. This stage is that half. It
is the only stage that may improve code without a criterion asking for it, and the price of that
freedom is that it may not change what the code *does*.

## Do

<!-- rule: STAGE-TIDY-1 -->
<!-- rule: STAGE-TIDY-2 -->
<!-- rule: STAGE-TIDY-3 -->
<!-- rule: STAGE-TIDY-4 -->
<!-- rule: STAGE-TIDY-5 -->
<!-- rule: STAGE-TIDY-6 -->
<!-- rule: STAGE-TIDY-7 -->
<!-- rule: STAGE-TIDY-8 -->

## Who carries this stage

`carrier.tidy: <name>` in the stack profile names the skill or agent that holds this project's craft
for it; use it where this tool offers it, otherwise do the stage as described here and say so in
your file. `carrier.guard: <name>` names the skill that holds the architecture's invariants while
you edit — apply it to every file you write, the same way. The rule in full: in what every stage is told.

## The tidy file

```markdown
# Tidy — <story id>

## Moves
| File | Move | Why it reads better |
(the first column is the pipeline's: run `factory-cli.py --files-skeleton <story> tidy` when your moves are
done — it creates the file with every changed file as a row, or adds the missing rows — and fill in the rest)

## Left alone
- <what you saw and did not change>: <why — outside the footprint, or a design question>
```

The gate's outcome is not recorded here: its report is the evidence, and a stage edits no hand-over
after the gate ran.

Where you changed nothing, say so and why: a green build that was already clean is a finished
stage, not a skipped one. An empty `## Moves` with a reason is a better outcome than a move made
to have made one.

## Do not

<!-- rule: STAGE-TIDY-NOT1 -->
<!-- rule: STAGE-TIDY-NOT2 -->
<!-- rule: STAGE-TIDY-NOT3 -->
