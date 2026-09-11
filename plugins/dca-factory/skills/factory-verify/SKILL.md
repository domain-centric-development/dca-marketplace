---
name: factory-verify
description: Checks that the delivery pipeline works. Two modes — observe one real story that was just delivered and report the facts about whatever did not hold (the stages' claims against the repository, the gate and the run journal), or check the pipeline's own machinery against throwaway fixtures. Use after a run to see whether it really did what it says, before trusting the pipeline in a new project, after changing a stage, a gate check or the runner, or on "/factory-verify".
---

# Verify the factory

Output: a report, and nothing else. You change no stage, no gate and no project file — a check
that repairs what it measures has measured nothing.

The pipeline exists so that an agent's word is never the evidence. That applies to the pipeline
itself, so **you do not judge whether it worked: two scripts do.** Your job is to run the right
one, read what it says, and add only the parts a script cannot reach.

Which mode:

| The question | Mode |
|---|---|
| "a story just ran — did it really do what the files say?" | **1. Observe a real run** |
| "can I trust this pipeline here at all?" / a stage, a gate check or the runner changed | **2. Check the machinery** |

## 1. Observe a real run

```bash
python3 <this skill>/scripts/observe.py --story <id>        # add --json for a machine-readable form
```

It reads the story, the six hand-over files, the gate reports and snapshots the runner journalled,
and the repository itself — then reports **what did not hold**, what held, and what it could not
see. It cross-checks claims against evidence, which is the whole point:

- the **file contract** — every stage's file exists and carries the sections it owes;
- **criterion keys** — the story's keys and the test table's, verbatim, in both directions: a
  renamed key silently drops a criterion;
- **red then green** — from the test stage's own record and the gate's reports, never from a
  stage's sentence about its tests;
- **no test was edited later** — the mapped test files' digests after the test stage against their
  digests now. The code changes until the test passes; the test does not;
- **the build's account against the diff** — a source file that changed and is not named in
  `build.md` is a change nobody reviewed, and a file named there that does not exist is a claim
  about nothing;
- **the plan's coverage** — a changed file whose name never appears in the plan was not designed,
  not reviewed and not asked for. This is what catches an invented page, endpoint or guard;
- **commands** — a check a stage reports running that the stack profile does not declare;
- **carriers and knowledge** — everything the profile names, against whether any stage reports
  using it. A named carrier nothing mentions was silently not used;
- **escalations** — a `needs-human` section, extra build/judge rounds, a verdict that is not
  `pass`, and every place a stage recorded a fall-back.

Report its three sections as they stand. The third one matters as much as the first: a run the
runner did not drive has no journal, so the diff-based checks cannot run, and the report says so
rather than passing them.

What only you can add, when the human asks for it: whether the stage files *reason* well — whether
the plan's design actually follows from the story, whether the judge's findings are real. Say
plainly that this part is a reading and not a measurement.

## 2. Check the machinery

```bash
python3 <this skill>/scripts/verify.py            # add -v for the gate output of a failing case
```

It builds a throwaway project per case and calls the project's own `story-gate.py` and
`factory.sh`, so it checks the code a run would actually use, not a description of it. Three groups:

- **the gate's checks** — an incomplete epic, a draft story, a context that is not on the map, an
  unmapped criterion, a selector with no test behind it, a test that is green too early, a green
  test with and without the test stage's record, a source set no command covers, a documented path
  that does not resolve, a glossary row without a source, a `needs-human` section;
- **the runner's shape** — that the plan gate runs *before* its stage and every other gate after
  it, that the test stage's artefact is `tests.md` and not `test.md`, that the judge's verdict is
  read from the file, that the round counter is a file and counts up;
- **install** — that the skills arrive as a live link rather than a copy, that the gate is copied
  into the project where CI can call it, that a tool without a plugin mechanism also gets the
  craft a profile may name as a carrier, and that `--copy` still produces a copy.

Report its verdict as it stands. A failing case is a defect in the pipeline or in the case, and
which of the two is exactly what the report has to say — do not "fix" either while verifying.

### What this mode cannot check

A fixture is not a project, and it holds no domain. This mode proves that the gate refuses what it
should refuse and that the runner is shaped as specified — never that a *stage* does its work,
which needs a model, a real project and a real story. That is mode 1's question, and the honest
sequence is: check the machinery when it changed, observe the next real run either way.

## What a report says

```markdown
# Factory verification — <date>, <tool and version>

## Observation of <story>                      (mode 1)
- did not hold: <each fact, with the file or the gate report behind it>
- held: <the claims that were cross-checked and stood>
- not observed: <what had no evidence here, and why>

## Machinery                                   (mode 2)
- gate: <n>/<n> cases as specified             (name every failing case and what it did instead)
- runner: <n>/<n> cases as specified
- install: <the shapes it left behind>

## Reading                                     (only where the human asked)
- whether the plan follows from the story, whether the judge's findings are real — stated as a
  reading, not as a measurement
```

The "not observed" line is not decoration. A run the runner did not drive has no journal, so the
diff-based checks cannot run at all; a fixture cannot see a stack this project does not have. A
verification that does not name its own blind spots invites exactly the trust it has not earned.

## Do not

- Do not repair a failing case, a stage or a gate check while verifying. Report it; fixing it is
  another task, with its own review.
- Do not run a live story in a working tree someone depends on, and never on a story that is not
  yours to build.
- Do not report "everything works" when a case was skipped — a skipped check is not a passing one,
  and the script names what it skipped.
