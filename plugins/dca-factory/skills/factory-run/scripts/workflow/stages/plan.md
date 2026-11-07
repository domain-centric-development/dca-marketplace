---
name: plan
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

First read what every stage is told — a session the runner started, one session that carries
several stages, a repeat round, the shell, the gate. The runner's prompt names its file and this
brief repeats none of it.

Input: the story file, the project description — `product/overview.md`, `product/tech.md` and
`product/domain.md`, or where the profile's `product:`, `tech:` and `domain:` point — the method's
configuration `dca.profile.yaml` at the project root (the instruction file's ``- configuration: `dca.profile.yaml` ``
line points at it; the layout, the naming suffixes and the resolved configuration the architecture suite holds the
code to; where it is missing or a key is absent, the defaults), and the
glossary and the context map generated from the code (`contextMap:`) where the project has them.
Nothing else — not the chat history, not an earlier run.
Output: `.dca-factory/runs/<story>/plan.md`, and nothing else. You write no test and no production code.

## Do

<!-- rule: STAGE-PLAN-1 -->
<!-- rule: STAGE-PLAN-2 -->
<!-- rule: STAGE-PLAN-3 -->
<!-- rule: STAGE-PLAN-4 -->
<!-- rule: STAGE-PLAN-5 -->
<!-- rule: STAGE-PLAN-6 -->
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

## Task mode

<!-- rule: STAGE-PLAN-TASK -->

## Adopt mode

<!-- rule: STAGE-PLAN-ADOPT -->

## Ask, do not recall

Where the profile names `knowledge: <skill>`, ask it instead of your recollection whenever an
answer would decide something, and cite the node by its path inside the catalog; never adopt a
knowledge source the profile did not name. The rule in full: in what every stage is told.

## Who carries this stage

`carrier.plan: <name>` in the stack profile names the skill or agent that holds this project's craft
for it; use it where this tool offers it, otherwise do the stage as described here and say so in
your file. The rule in full: in what every stage is told.

## The plan file

```markdown
# Plan — <story id>: <title>

## Context
<bounded context, and why this story belongs to it — two lines>
refusals: thrown | returned — <where it was read>   (only where a criterion refuses something)

## Changes
| Element | Kind | Location | New or changed | Evidence |
(one row per element; Evidence is the file:line, or the catalog node by its path inside the catalog)

## Acceptance criteria
- <key>  →  level: e2e | integration (port) | integration (adapter: <Adapter>) | browser-only (<why>) — <the runner in this project>, happy path on the one the story marks
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

## Glossary proposals
- <term>: <definition>            (omit the section when there are none)

## Open assumptions
- <assumption from the story that the plan rests on>   (a known gap it defers stays a gap: the judge keeps it as a finding)

## needs-human                    (only when the run must stop — otherwise leave the heading out)
decision: <story>-<nn>
<one line saying what is asked>
```

A `## needs-human` names a **decision record** with `stage: plan` — the shape, and how an answered
record is cited when you plan again, in what every stage is told.

## Do not

<!-- rule: STAGE-PLAN-NOT1 -->
<!-- rule: STAGE-PLAN-NOT2 -->
<!-- rule: STAGE-PLAN-NOT3 -->
<!-- rule: STAGE-PLAN-NOT4 -->
