# What every stage is told

<!-- frame: what the stage is told, each rule by its marker -->

The stage skills (`stage-plan`, `stage-test`, `stage-build`, `stage-tidy`, `stage-judge`,
`stage-document`, `stage-integrate`) share these rules. Each skill says to read this file first; a shared
builder that carries four stages reads it once, not four times. The stage-specific part — which
profile key names the carrier, which `stage:` a decision record carries — stays in the skill.

A line `<!-- rule: <id> -->` names the paragraph below it for the factory's rulebook (`factory.sh rules`); it
changes nothing a stage does.

The runner's prompt names the skill, the story and where things are — the paths, the commands, the
reports of an earlier round — and nothing else. What a session does with them is said here.

## A session the runner started

<!-- rule: STAGE-COMMON-1 -->

<!-- rule: STAGE-COMMON-2 -->
<!-- rule: STAGE-COMMON-3 -->
<!-- rule: STAGE-COMMON-4 -->
<!-- rule: STAGE-COMMON-5 -->
<!-- rule: STAGE-COMMON-6 -->
<!-- rule: STAGE-COMMON-7 -->

## A stage on its own

<!-- rule: STAGE-COMMON-8 -->

## One session, several stages

<!-- rule: STAGE-COMMON-9 -->

<!-- rule: STAGE-COMMON-10 -->
<!-- rule: STAGE-COMMON-11 -->
<!-- rule: STAGE-COMMON-12 -->
<!-- rule: STAGE-COMMON-13 -->
<!-- rule: STAGE-COMMON-14 -->
<!-- rule: STAGE-COMMON-15 -->
<!-- rule: STAGE-COMMON-16 -->

## A repeat round

<!-- rule: STAGE-COMMON-17 -->

<!-- rule: STAGE-COMMON-18 -->
<!-- rule: STAGE-COMMON-19 -->
<!-- rule: STAGE-COMMON-20 -->
<!-- rule: STAGE-COMMON-21 -->
<!-- rule: STAGE-COMMON-22 -->
<!-- rule: STAGE-COMMON-23 -->

## A review the runner started

<!-- rule: STAGE-COMMON-24 -->

## Ask, do not recall — but only a source the project named

<!-- rule: STAGE-COMMON-25 -->

<!-- rule: STAGE-COMMON-26 -->

<!-- rule: STAGE-COMMON-27 -->

## Who carries a stage

<!-- rule: STAGE-COMMON-28 -->

<!-- rule: STAGE-COMMON-29 -->

## A question is a decision record

<!-- rule: STAGE-COMMON-30 -->

```markdown
---
id: <story>-<nn>
story: <story>
stage: <the stage that will apply the answer>
asked: <now, UTC, ISO 8601>
---

# <the question in one line>

## Question
## Options
- a: <one way, and what it costs>
- b: <another>
## Recommendation
<a — why, in one or two sentences>
```

<!-- rule: STAGE-COMMON-31 -->

<!-- rule: STAGE-COMMON-32 -->

## The gate is your test run

<!-- rule: STAGE-COMMON-33 -->

## The shell a stage has

<!-- rule: STAGE-COMMON-34 -->

<!-- rule: STAGE-COMMON-35 -->

## The formatter runs last

<!-- rule: STAGE-COMMON-36 -->
