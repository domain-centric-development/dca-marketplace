# Test first (TDD): red, green, refactor

Changes the order of work, not what a test must be.

## The cycle

1. **Red.** The smallest next observable behaviour, one test at the level that observes it (`SKILL.md`,
   section 1). Confirm it fails on its assertion, not a compile error; fix mechanics and rerun. A type needed to
   compile may be written whole if nothing a test observes lives in it; a method whose answer a test asserts
   throws until built — never a default value.
2. **Green.** The smallest production change. Hard-coding is fine when the next test forces the general form. No
   extra features, branches or defensive code — a guard is written when an invariant names it, test first.
3. **Refactor.** Names, duplication, extraction, types; tests green throughout — red means behaviour changed:
   revert or fix. **No new test during refactoring.**
4. **Repeat.** A cycle over fifteen minutes is a step too big: split.

## Where it fits, by level

| Level | Test first? | Note |
|---|---|---|
| `unit` | yes, the main place | pure domain code, no framework — the fastest feedback; invariants and aggregate behaviour |
| `port` | yes | the use case through its input port in the wired application, real outgoing adapters; slower cycle, same order |
| `adapter` | where the translation has branches | a thin adapter with one path is covered by its port and end-to-end tests |
| `e2e` | the happy path, before the build | red first like every criterion's test; a journey test is green when written and is no TDD step |
| architecture rules | no | governance over code that exists, not behaviour |

## Refuse

Test after; one big-bang test for a feature; refactoring during red; writing the test from the implementation
instead of the requirement; mocking the class under test or a value object.

## Commands

The project's own. Common forms:

```bash
./gradlew test --tests '*TitleTest*'                                   # Java: one class
dotnet test --filter "FullyQualifiedName~TitleTests"                    # .NET: one class
```

The single test while writing, the relevant tests after green and after refactoring.

## Output per cycle

```text
RED      — <fully.qualified.Class>#<method>: FAIL on assertion (expected <x>, got <y>)
GREEN    — <one line: what changed>; PASS
REFACTOR — <one line: what improved>; PASS
```

Then the tables of `SKILL.md`, section 4, for every test the cycles produced.
