---
name: stage-tidy
description: Tidy stage of a factory run — the refactor step the build stage deliberately skips, taken with every test green and without changing behaviour. Use after the build gate passed for a story, when the orchestrator hands over a green build, or on "/stage-tidy". Touches only what this story touched.
---

# Tidy one story's code

Input: the story, `tasks/<story>/plan.md`, `tasks/<story>/build.md`, and the code as the build
stage left it — green. Nothing else.
Output: the tidied code, plus `tasks/<story>/tidy.md`.

The build stage answers the criteria with the smallest change that works, which is the right thing
for it to do and leaves the second half of red–green–refactor undone. This stage is that half. It
is the only stage that may improve code without a criterion asking for it, and the price of that
freedom is that it may not change what the code *does*.

## Do

1. Read the plan and the build file, then the code they name. Work **only inside this story's
   footprint**: the files the build stage changed, and what it made demonstrably redundant — a
   helper nothing calls any more, a duplicate the new code introduced. A smell elsewhere is a note
   in your file, never an edit.
2. Keep every test green, and **change no test**. A test that now reads wrongly is a finding for
   the judge; a test you may not touch is what keeps this stage honest, because a refactor that
   edits its own check proves nothing.
3. Change no behaviour. Nothing removed that a criterion needs, nothing added that meets a
   criterion the build stage did not meet, no error message a caller can see reworded unless a
   criterion names it. If a change would be visible to a caller, it is not tidying.
4. Take the ordinary moves and nothing exotic: a name that says what the thing is in the project's
   own vocabulary, a function split where two levels of abstraction sit in one, a duplicate lifted
   once, a comment deleted where the code now says it, a value object where a primitive was
   carrying meaning. Each move is small and each leaves the suite green — run the profile's test
   commands between them, not once at the end.
5. Respect the architecture as the build stage did: the domain free of framework types, ports
   declared inward, no raw cross-context imports. A tidy-up that moves a type across a layer is a
   design change and belongs in a plan, not here.
6. Stop early. Two or three moves that make the story's code plainly better is a good stage; a
   rewrite is a plan nobody approved. When you find yourself wanting one, write it down as a
   finding and leave the code alone.
7. Run what the stack profile declares — compile, the tests, the architecture suite, the formatter.
   The gate runs them again afterwards, so a stage that skips them only delays its own failure.

## Who carries this stage

The stack profile may name a carrier — `carrier.tidy: <name>` — the skill or agent that holds this
project's craft for readable code. A review **skill** works in every tool; an **agent** only where
the tool has agents. Use the named carrier where this tool offers it; otherwise do the stage as
described here and say in your file which it was ("in-session; `<carrier>` not available here").

## The tidy file

```markdown
# Tidy — <story id>

## Moves
| File | Move | Why it reads better |

## Left alone
- <what you saw and did not change>: <why — outside the footprint, or a design question>

## Checks
- <command>: <result>
```

Where you changed nothing, say so and why: a green build that was already clean is a finished
stage, not a skipped one. An empty `## Moves` with a reason is a better outcome than a move made
to have made one.

## Do not

- Do not change a test, delete a test, or weaken an assertion.
- Do not rename anything a criterion, a glossary entry or a document names — the story's words are
  the domain contact's. A better name for a domain term is a glossary question.
- Do not reformat files the story never touched; a formatter run across the repository buries this
  story's change in noise and makes the judge's diff unreadable.
