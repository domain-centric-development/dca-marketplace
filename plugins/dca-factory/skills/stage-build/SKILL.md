---
name: stage-build
description: Build stage of a factory run — writes the production code that turns the story's red tests green, with the smallest change that works. Use after the test stage of a story, when the orchestrator hands over the failing tests or a gate report, or on "/stage-build". Keeps the domain framework-free and the architecture suite green.
---

# Build one story

Input: the story, `tasks/<story>/plan.md`, `tasks/<story>/tests.md`, and — in a repeat round —
the gate or judge report. Nothing else.
Output: the production code, plus `tasks/<story>/build.md`.

## Do

1. Read the plan and the failing tests. Implement the **smallest** change that makes them pass.
2. Follow the plan's change list. An element the plan did not name is a sign the plan was wrong:
   note it in the build file rather than quietly extending the design.
3. Keep the architecture intact — the same rules the plan worked under: no framework types in the
   domain, ports declared inward and implemented in adapters, no raw cross-context imports, one
   aggregate per transaction, domain events published and cleared where the plan says so.
4. Use the project's own building blocks and conventions: its markers, its base types, its
   package layout, its error handling. Where the project ships an architecture rule suite, run it
   and take it as binding.
5. Run what the stack profile declares — compile, unit tests, end-user tests, the architecture
   suite, the formatter. Do not finish while one of them is red. The build gate runs the
   architecture and format commands again afterwards, so a stage that skips them only delays its
   own failure.
6. In a repeat round, work only on what the gate or the judge confirmed. Do not take the
   opportunity to refactor elsewhere.

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

The stack profile may name a carrier for this stage — `carrier.build: <name>` — the skill or
agent that holds this project's craft for it. A review **skill** works in every tool; an **agent**
only where the tool has agents. Use the named carrier when this tool offers it; otherwise do the
stage as described here and say in your file which it was ("in-session; `<carrier>` not available
here"). A missing carrier is a missing preference, never a reason to skip the stage.

## The build file

```markdown
# Build — <story id>

## Changed
| File | Why |

## Criteria
- <criterion key>: met by <what the code now does>

## Deviations from the plan
- <element>: <what differed and why>        (omit when there were none)

## Checks
- <command>: <result>
```

## Do not

- Do not change a test to make it pass. A test that is wrong goes back to the test stage, with
  the reason, in `## Deviations from the plan`.
- Do not write a criterion key into code, documentation or a comment.
- Do not leave commented-out code, a `TODO` for the criterion you were asked to deliver, or a
  disabled test behind.
