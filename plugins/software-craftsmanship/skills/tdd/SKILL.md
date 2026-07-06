---
name: tdd
description: |
  Enforces Red-Green-Refactor when implementing new behavior. Claude writes a
  failing test first, confirms it fails for the right reason, implements the
  minimum to pass, then refactors. Use when adding new functionality —
  especially in domain or application layers of a DCA project.
disable-model-invocation: false
---

# /tdd — Test-First Workflow Guidance

This skill is a **workflow discipline**, not a generator. It changes the order
in which you write code: test before implementation, one tiny step at a time.

## The cycle

### 1. Red — write a failing test

- Pick the **smallest** observable behavior you want next.
- Express it as one focused test (one assertion or one tight scenario).
- Run the test.
- **Confirm it fails for the right reason** — not a compile error, not a typo.
  If the failure is mechanical, fix the mechanics first, then re-run.

### 2. Green — make it pass minimally

- Write the **smallest** amount of production code that makes the test green.
- Hard-coding a return value is fine if the next test will force generalization.
  Don't anticipate.
- No new features, no extra branches, no defensive programming.
- Run the test. Green.

### 3. Refactor — clean up with the safety net

- Test is green. The net is on.
- Improve naming, remove duplication, extract small functions, tighten types.
- Test stays green throughout. If it goes red, the refactor changed behavior —
  revert or fix.
- **No new tests during refactor.** That's the next Red.

### 4. Repeat

Cycle length: minutes, not hours. If a cycle takes >15 min, the step is too big.

## When to use TDD in a DCA project

| Layer | TDD applies? | Notes |
|---|---|---|
| `domain/` | **Yes, primary** | Pure Java, no Spring — fast feedback. Domain invariants and aggregate behavior. |
| `application/` (use cases) | **Yes** | Mock the output ports. Test orchestration logic. |
| `adapter/incoming/` (REST, MCP) | **Sometimes** | Thin adapters often don't justify TDD; cover with integration tests. |
| `adapter/outgoing/` (Repo impls) | **Integration tests, not TDD** | The interesting failure mode is the boundary with the real DB — Testcontainers, not mocks. |
| ArchUnit / Spring-Modulith verification | **No** | These are governance checks, not behavior. They run *after* code exists. |

## Anti-patterns this skill flags

- **Test-after.** Writing the production code first, then a test that mirrors it.
  This produces tests that can't fail in interesting ways.
- **Big-bang test.** A test that asserts the whole feature in one go. Split it
  into the smallest observable behaviors.
- **Refactoring during Red.** Mixing structural and behavioral changes — when
  it breaks, you don't know which one caused it.
- **Reading the implementation to write the test.** The test should be derivable
  from the requirement, not from the code.
- **Mocking the system under test.** Mock collaborators (output ports, external
  services), never the class you're testing.
- **Mocking value objects or records.** They have no behavior worth mocking.

## Conventions

Read `<project-root>/.claude/dca/conventions.md` (or fall back to
`<project-root>/CLAUDE.md`) for:

- Test source set paths (`src/test/`, `src/test-integration/`, etc.)
- Test framework choice (JUnit 5 vs. Spock)
- Project-specific naming for test classes

If no conventions file: default to JUnit 5 in `src/test/java/`, mirror the
production package structure, suffix test classes with `Test`.

## Commands the user might run

```bash
./gradlew test                            # all unit tests
./gradlew test --tests '*OrderTest*'      # one class
./gradlew test --tests '*.shouldPlace*'   # one method pattern
./gradlew test -Pfilter=Cart              # if project supports it
```

After Green, before Refactor, **run the relevant tests once** to confirm green.
After Refactor, **run again** to confirm still green.

## What Claude should output

Each cycle:

```
RED  — wrote test: <ClassName>.shouldXxx
       running ... FAIL (expected: <observation>, got: <state>)  ← right reason ✓
GREEN — implementing minimal:
       <short diff>
       running ... PASS
REFACTOR — <what improved, e.g. "extracted private validateLine method">
       running ... PASS
```

Brief. The user sees the diff in the editor; the skill is for cadence, not
narration.

## Not in scope

- **BDD / Gherkin** — separate skill (`/bdd`, if added later).
- **Integration / E2E tests** — these aren't TDD-driven; they cover wider
  scope after the unit-level design is settled.
- **Test data builders, fixtures, factories** — useful, but tangential. Use
  whatever pattern the project already has.
