---
name: tidy
role: tidies
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

Read what every stage is told first (its file: in the prompt).

Input, nothing else: the story, `plan.md`, `build.md`, and the green code the build left — the files
`.dca-factory/evidence/<story>/changed.txt` lists. Every file you change is a row under `## Moves` (the gate checks).
Output: the tidied code and `.dca-factory/runs/<story>/tidy.md`.

The refactor half of red–green–refactor: the only stage that improves code no criterion asks for — and it may not
change what the code *does*.

## Do

<!-- rule: STAGE-TIDY-1 -->
<!-- rule: STAGE-TIDY-2 -->
<!-- rule: STAGE-TIDY-3 -->
<!-- rule: STAGE-TIDY-4 -->
<!-- rule: STAGE-TIDY-5 -->
<!-- rule: STAGE-TIDY-6 -->
<!-- rule: STAGE-TIDY-7 -->
<!-- rule: STAGE-TIDY-8 -->
<!-- rule: STAGE-TIDY-9 -->

## Who carries this stage

`carrier.tidy: <name>`: use that skill or agent; none in this tool → do the stage as written here and say so in your
file. `carrier.guard:` applies to every file you write; `carrier.frontend:` to every page, template, stylesheet and
client script.

## The tidy file

```markdown
# Tidy — <story id>

## Moves
| File | Move | Why it reads better |
(the first column is the pipeline's: run `factory-cli.py --files-skeleton <story> tidy` when your moves are
done — it creates the file with every changed file as a row, or adds the missing rows — and fill in the rest)

## Left alone
- <what you saw and did not change>: <why — outside the footprint, or a design question>

## needs-human                    (only when the specification contradicts itself — otherwise leave it out)
decision: <story>-<nn>
contradiction: <what cannot all hold>
```

No gate outcome here; no hand-over edited after the gate ran. Nothing to improve → empty `## Moves` with the reason:
a finished stage, better than a move made to have made one.

## Do not

<!-- rule: STAGE-TIDY-NOT1 -->
<!-- rule: STAGE-TIDY-NOT2 -->
<!-- rule: STAGE-TIDY-NOT3 -->
