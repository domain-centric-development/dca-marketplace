# Test first (TDD): red, green, refactor

Test-driven development is one way of writing the tests the rest of this skill describes: the test comes before the
code, one small step at a time. It changes the order of work, not what a test must be.

## The cycle

### 1. Red — a failing test

- Pick the **smallest** observable behaviour you want next.
- Express it as one focused test at the level that observes it (`SKILL.md`, section 1).
- Run it. **Confirm it fails for the right reason** — on its assertion, not on a compile error or a typo. If the
  failure is mechanical, fix the mechanics and run again. Where a type is needed to compile, write it whole if
  nothing a test observes lives in it; a method whose answer a test asserts throws until it is built — never a
  default value, which can make the test green before any code exists.

### 2. Green — make it pass, minimally

- Write the **smallest** production change that makes the test green. Hard-coding a value is fine when the next
  test will force the general form; do not anticipate.
- No new features, no extra branches, no defensive code nobody asked for — a guard is written when an invariant
  names it, test first.
- Run the test: green.

### 3. Refactor — with the net on

- Improve names, remove duplication, extract small functions, tighten types.
- The tests stay green throughout. Red means the refactoring changed behaviour: revert or fix.
- **No new test during refactoring.** That is the next red.

### 4. Repeat

A cycle takes minutes. One that takes more than fifteen is a step too big: split the behaviour.

## Where it fits, by level

| Level | Test first? | Note |
|---|---|---|
| `unit` | yes, the main place | pure domain code, no framework — the fastest feedback; invariants and aggregate behaviour |
| `port` | yes | the use case through its input port in the wired application, real outgoing adapters; slower cycle, same order |
| `adapter` | where the translation has branches | a thin adapter with one path is covered by its port and end-to-end tests |
| `e2e` | the happy path, before the build | red first like every criterion's test; a journey test is green when written and is no TDD step |
| architecture rules | no | governance over code that exists, not behaviour |

## Anti-patterns

- **Test after.** Code first, then a test that mirrors it — a test that cannot fail in an interesting way.
- **Big-bang test.** The whole feature in one test. Split it into the smallest observable behaviours.
- **Refactoring during red.** Structure and behaviour changed together; when it breaks, nobody knows which did it.
- **Reading the implementation to write the test.** The test follows from the requirement, not from the code.
- **Mocking the class under test, or a value object.** Neither has anything worth replacing.

## Commands

Use the project's own commands. Common forms:

```bash
./gradlew test --tests '*TitleTest*'                                   # Java: one class
dotnet test --filter "FullyQualifiedName~TitleTests"                    # .NET: one class
```

Run the single test while writing it, the relevant tests after green and again after refactoring.

## Output per cycle

```text
RED      — <fully.qualified.Class>#<method>: FAIL on assertion (expected <x>, got <y>)
GREEN    — <one line: what changed>; PASS
REFACTOR — <one line: what improved>; PASS
```

Then the tables of `SKILL.md`, section 4, for every test the cycles produced.
