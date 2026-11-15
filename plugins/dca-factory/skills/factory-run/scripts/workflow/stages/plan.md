---
name: plan
role: plans
order: 1
hand_over: plan.md
window: builder
kinds:
- story
- journey
- adopt
- task
traits:
- gated
- in_order
---

# plan

Turns the story into an implementation plan — each acceptance criterion by its key, with its test level — and names the architecture elements that change.

<!-- frame: what the stage is told, each rule by its marker -->

Read what every stage is told first (its file: in the prompt).

Input, nothing else (no chat history, no earlier run): the story; `product/overview.md`, `product/tech.md`,
`product/domain.md` (or the profile's `product:`, `tech:`, `domain:`); `dca.profile.yaml` at the root — layout,
naming suffixes, the configuration the architecture suite holds code to (missing key → default); the glossary and the
generated context map (`contextMap:`) where present.
Output: `.dca-factory/runs/<story>/plan.md` only. No test, no production code, no build run.

## Do

<!-- rule: STAGE-PLAN-1 -->
<!-- rule: STAGE-PLAN-2 -->
<!-- rule: STAGE-PLAN-3 -->
<!-- rule: STAGE-PLAN-4 -->
<!-- rule: STAGE-PLAN-5 -->
<!-- rule: STAGE-PLAN-6 -->
<!-- rule: STAGE-PLAN-6A -->
<!-- rule: STAGE-PLAN-7 -->
<!-- rule: STAGE-PLAN-8 -->
<!-- rule: STAGE-PLAN-8A -->
<!-- rule: STAGE-PLAN-8B -->
<!-- rule: STAGE-PLAN-9 -->
<!-- rule: STAGE-PLAN-9A -->
<!-- rule: STAGE-PLAN-9B -->
<!-- rule: STAGE-PLAN-9C -->
<!-- rule: STAGE-PLAN-10 -->
<!-- rule: STAGE-PLAN-11 -->
<!-- rule: STAGE-PLAN-12 -->
<!-- rule: STAGE-PLAN-13 -->

## Task mode

<!-- rule: STAGE-PLAN-TASK -->

## Adopt mode

<!-- rule: STAGE-PLAN-ADOPT -->

## Ask, do not recall

`knowledge: <skill>` in the profile: ask it, cite the node path; never a source the profile does not name.

## Who carries this stage

`carrier.plan: <name>`: use that skill or agent; none in this tool → do the stage as written here and say so in your file.

## The plan file

```markdown
# Plan — <story id>: <title> · source: <the story's `source:` — person where it names none>

## Context
<bounded context, and why this story belongs to it — two lines>
refusals: thrown | returned — <where it was read>   (only where a criterion refuses something)

## Changes
| Element | Kind | Location | New or changed | Evidence |
(one row per element; Evidence is the file:line, or the catalog node by its path inside the catalog)

## Acceptance criteria
- <key>  →  level: e2e | integration (port) | integration (adapter: <Adapter>, test: <Class>#<method>) | browser-only (<why>) — <the runner in this project>, happy path on the one the story marks
                                  (the key alone; the criterion's text stays in the story)

## Invariants
- <Element>: <rule>; <rule>           (one line per domain type in `## Changes`, its guards included; `;` separates rules)
- <Element>: none — <why>

## Changed tests                  (omit the section when the story contradicts no existing test)
| Test file | Backed by |
| --- | --- |
| <path from the project root> | <the story's changed-expectation line, or the decision id> |

## Files
- `<path>` — changes: <what>          (every file the plan expects to change, from the project root;
                                       `changes: new — <what>` for a file that does not exist yet,
                                       `changes: removed — <why>` for one that goes — the build gate
                                       holds both, `plan-files`)
- `<path>` — read: <why>              (the pattern to mirror, the fixture to reuse — what a later
                                       stage must read to understand the change; one line each)

## Guarded changes                (omit the section when the story changes no guarded path)
- `<path>` — <why the story changes what judges it>   (a path of the guarded set: the stack profile or a
                                       glob of its `guarded:`; the gate checks both, `guarded`)

## Glossary proposals
- <term>: <definition>            (omit the section when there are none)

## Open assumptions
- <assumption from the story that the plan rests on>   (a known gap it defers stays a gap: the judge keeps it as a finding)

## needs-human                    (only when the run must stop — otherwise leave the heading out)
decision: <story>-<nn>
<one line saying what is asked>
```

`## needs-human` names a decision record with `stage: plan` (shape: what every stage is told).

## Do not

<!-- rule: STAGE-PLAN-NOT1 -->
<!-- rule: STAGE-PLAN-NOT2 -->
<!-- rule: STAGE-PLAN-NOT3 -->
<!-- rule: STAGE-PLAN-NOT4 -->
