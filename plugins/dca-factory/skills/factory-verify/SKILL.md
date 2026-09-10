---
name: factory-verify
description: Checks that the delivery pipeline itself works — the gate's every check against throwaway fixtures, the runner's stage order, verdict handling and install shapes, and optionally one tiny story delivered end to end in this project. Use before trusting a run in a new project, after changing a stage, a gate check or the runner, when a run behaved oddly and it is unclear whether the pipeline or the story is at fault, or on "/factory-verify".
---

# Verify the factory

Output: a report, and nothing else. You change no stage, no gate and no project file — a check
that repairs what it measures has measured nothing.

The pipeline exists so that an agent's word is never the evidence. That applies to the pipeline
itself, so **you do not judge whether it works: a script does.** Your job is to run it, to read
what it says, and to add the one thing a script cannot do — put a real story through a real tool.

## 1. The deterministic part

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

## 2. What the script cannot check

A script cannot tell whether a *stage* does its work: that needs a model, a project and a story.
Where the human asked for a full check, and only then, deliver one deliberately tiny story in a
scratch copy of this project (or a scratch project of its own — never in a working tree someone
depends on) and report:

1. Which tier ran (the runner outside the session, a subagent per stage, or in-session) and why.
2. For each stage: does its file exist, and does it carry the sections the file contract names?
3. The gate's red→green transition: were the mapped tests red before the build stage and green
   after — read from the gate's own output, not from a stage's claim?
4. Whether the judge separated the story's criteria from the epic's outcome event, and which
   verdict it returned.
5. Which carriers and which knowledge source the stages actually used, and which they reported as
   unavailable — a profile that names a carrier no tool here offers is a finding worth having.

Delete the scratch copy afterwards, and say that you did.

## 3. What the report says

```markdown
# Factory verification — <date>, <tool and version>

## Deterministic
- gate: <n>/<n> cases as specified            (name every failing case and what it did instead)
- runner: <n>/<n> cases as specified
- install: <the shapes it left behind>

## Live run                                    (omit when it was not asked for)
- story, tier, and the six files with what each carried
- red→green as the gate reported it
- verdict, and what the judge separated
- carriers and knowledge: used / not available here

## Findings
- <what is broken, in the pipeline or in a case, with the file and line>

## Not checked
- <what neither part covered — say it, so the report is not read as more than it is>
```

The last section is not decoration. The deterministic part cannot see whether a stage reasons
well, and a single live story cannot see a stack this project does not have. A verification that
does not name its own blind spots invites exactly the trust it has not earned.

## Do not

- Do not repair a failing case, a stage or a gate check while verifying. Report it; fixing it is
  another task, with its own review.
- Do not run a live story in a working tree someone depends on, and never on a story that is not
  yours to build.
- Do not report "everything works" when a case was skipped — a skipped check is not a passing one,
  and the script names what it skipped.
