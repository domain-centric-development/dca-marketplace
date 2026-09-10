---
name: stage-plan
description: Plan stage of a factory run — turns one backlog story into an implementation plan with numbered acceptance criteria and names the architecture elements that change. Use when a story is to be planned before any test or code is written, when the orchestrator hands over a story, or on "/stage-plan". Reads only the story and the project's own glossary and context map.
---

# Plan one story

Input: the story file, and the project's glossary and context map if it has them. Nothing else —
not the chat history, not an earlier run.
Output: `tasks/<story>/plan.md`, and nothing else. You write no test and no production code.

## Do

1. Read the story: its context, its acceptance criteria, its open assumptions.
2. Locate that bounded context in the code. If the project keeps a context map and the story's
   `context` is not in it, stop: write the plan file with a `## needs-human` section stating that
   the story needs a new context or a new relationship between contexts. That is a scoping
   decision. A project without a context map is not blocked by this — note the absence and go on.
3. Name the elements that change, in the project's own vocabulary: aggregates, value objects,
   domain events, use cases with their ports, adapters, read models. Say for each whether it is
   new or changed, and where it belongs — layer and package/namespace as this project lays them
   out, not as any sample does.
4. Respect the architecture the project has adopted: the domain free of framework types, ports
   declared inward and implemented in adapters, no raw cross-context imports, one aggregate
   changed per transaction. Ask the project's knowledge skill where one is
   installed (see below) rather than deciding a pattern question from memory.
5. Restate the acceptance criteria, keeping the story's **keys** verbatim — the later stages and
   the gate join on them. Add a criterion for every concrete detail the story specifies (wording,
   placement, ordering): a detail that is not a criterion is a detail no test will cover and no
   stage will build.
6. Decide the shape of the end-user test for each criterion and record it. Choose from what the
   project **already has**: read the stack profile and look at the existing tests. A browser test
   is the shape only where a browser runner is installed; otherwise the shape is the highest
   end-user level the project can run today — an HTTP-level test against the running application,
   a controller-slice test, an API test, a message- or scheduler-level test. Never pick a shape
   that would need a test framework the project does not have; adding one is a stack decision,
   not part of a story. Where the shape you would want is missing, name it under
   `## Open assumptions` and plan the next best shape.
7. Name business terms in the criteria that are not in the glossary yet, as proposals with a
   one-line definition. Do not silently invent domain language.
8. Back every statement about the code with evidence: the file, and the line or symbol you read
   it from. A statement without evidence is a guess and is marked as one.

## Ask, do not recall — but only a source the project named

Where the stack profile names a **knowledge skill** — `knowledge: <skill>`, one that answers
architecture questions from a catalog and cites the node it read — use it instead of your own
recollection whenever the answer would decide something: which pattern applies, why a rule exists,
whether a construct is a pitfall, what a recipe prescribes. Name the node you relied on in your
file, the way you name a file and line for a claim about the code.

**Never adopt a knowledge source the profile did not name.** A catalog that happens to be installed
may be a vendored copy of an older release: its rule ids, marker names and recipes can describe a
version the project does not use, and a citation makes that wrongness look verified. If you notice
such a skill, say so in your file — "`<skill>` is available but not named in the profile, so it was
not used" — and decide from the project's own rules, markers and documents instead. Those are the
source of truth; a catalog is a convenience the project has to vouch for.

Without a `knowledge:` entry, work from what the project itself carries: its rule catalog and the
report its architecture suite prints, its building blocks, its glossary, its documents. Nothing
here fails for the absence of a knowledge skill.

## Who carries this stage

The stack profile may name a carrier for this stage — `carrier.plan: <name>` — the skill or
agent that holds this project's craft for it. A review **skill** works in every tool; an **agent**
only where the tool has agents. Use the named carrier when this tool offers it; otherwise do the
stage as described here and say in your file which it was ("in-session; `<carrier>` not available
here"). A missing carrier is a missing preference, never a reason to skip the stage.

## The plan file

```markdown
# Plan — <story id>: <title>

## Context
<bounded context, and why this story belongs to it>

## Changes
| Element | Kind | Location | New or changed |

## Acceptance criteria
- <key>: <criterion>  →  test shape: <the shape, and the runner in this project that runs it>

## Glossary proposals
- <term>: <definition>            (omit the section when there are none)

## Open assumptions
- <assumption from the story that the plan rests on>

## needs-human                    (only when the run must stop)
```

## Do not

- Do not write code or tests, and do not run the build.
- Do not widen the story. A change you consider necessary but that no criterion asks for goes
  into `## Open assumptions`, not into the plan's change list.
- Do not renumber or rename the criterion keys; they are committed identifiers.
