---
name: stage-tidy
description: Tidy stage of a factory run — the refactor step the build stage deliberately skips, taken with every test green and without changing behaviour. Use after the build gate passed for a story, when the orchestrator hands over a green build, or on "/stage-tidy". Touches only what this story touched. Internal stage of the pipeline — factory-run starts it; by hand only to redo this one stage of a story that has the ones before.
---

# Tidy one story's code

First read `factory-run/reference/stage-common.md` — the rules every stage holds to: a session the
runner started, one session that carries several stages, a repeat round, the shell, the gate. The
runner's prompt names its path and repeats none of it.

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

1. Read the plan and the build file, then the code they name. Work **only inside this story's
   footprint**: the files the build stage changed, and what it made demonstrably redundant — a
   helper nothing calls any more, a duplicate the new code introduced, and what the plan's `## Files`
   lists beyond the story's own code — an old wording, a last caller's target, a twin check. The
   story's test files and the test support they use are footprint too. A smell elsewhere is a note in
   your file, never an edit.
2. Keep every test green, and **change no test's claim**. The story's tests and the shared test support
   take moves that keep what each test asserts: a copy lifted into the shared support — the earlier
   copies too, at the third one —, a page object called instead of a raw locator, a test method named
   after its display name, a stale comment or a dead helper of the story's tests deleted. Never an
   assertion, an expected value, a selector of the `gate:tests` table or a test's scope — a test that
   asserts too little is a finding for the judge, and a change of what it expects is a human's
   decision. Each test file you change is a row under `## Moves`. The tidy gate runs every mapped
   test you moved on the tree the test stage left, with your test files laid over it (`red-reproof`):
   it must be red there as it was, so a move that renamed production code a test calls, or let a test
   pass without the code, is refused. A test that existed before the story keeps what it expects, as
   at every stage.
3. Change no behaviour. Nothing removed that a criterion needs, nothing added that meets a
   criterion the build stage did not meet, no error message a caller can see reworded unless a
   criterion names it. If a change would be visible to a caller, it is not tidying.
4. Take the ordinary moves and nothing exotic: a name that says what the thing is in the project's
   own vocabulary — in doc comments too, and a word the glossary lists under `Synonyms (avoid)` is
   always a move, replaced by its term — a function split where two levels of abstraction sit in one,
   a duplicate lifted once, a comment deleted where the code now says it, a comment or doc comment in
   a touched file that the change made wrong or too narrow rewritten to what holds now, a value object
   where a primitive was carrying meaning. A comment says what holds in this file, not what a source
   the reader cannot see says. Each move is small and each leaves the suite green — run the profile's
   test commands between them, not once at the end.
5. Respect the architecture as the build stage did: the domain free of framework types, ports
   declared inward, no raw cross-context imports. A tidy-up that moves a type across a layer is a
   design change and belongs in a plan, not here.
6. Stop early. Two or three moves that make the story's code plainly better is a good stage; a
   rewrite is a plan nobody approved. When you find yourself wanting one, write it down as a
   finding and leave the code alone.
7. The gate is your test run (`factory-run/reference/stage-common.md`): a single test while you move
   things, then the tidy gate, never the whole suite before it. Write nothing about the gate into
   your file: its report is the record.
8. `formatFix:` runs last, before you finish (`factory-run/reference/stage-common.md`).

## Who carries this stage

`carrier.tidy: <name>` in the stack profile names the skill or agent that holds this project's craft
for it; use it where this tool offers it, otherwise do the stage as described here and say so in
your file. `carrier.guard: <name>` names the skill that holds the architecture's invariants while
you edit — apply it to every file you write, the same way. The rule in full: `factory-
run/reference/stage-common.md`.

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

- Do not change what a test asserts, delete a test, or weaken an assertion; move only how it says it.
- Do not rename anything a criterion, a glossary entry or a document names — the story's words are
  the domain contact's. A better name for a domain term is a glossary question.
- Do not reformat files the story never touched; a formatter run across the repository buries this
  story's change in noise and makes the judge's diff unreadable.
