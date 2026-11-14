---
name: testing
description: The craft of writing tests that hold — the level a criterion is tested at (unit, port, adapter, end to end), a fresh and visible fixture per test, one behaviour named after what it proves, a test seen red before it is trusted, no logic in a test, state over interaction, an injected clock, no sleeps, no flaky test left standing, locators by stable marker — and the two ways of writing one, test first (TDD) and scenario first (BDD, Given/When/Then from the criteria to the test). Answers with one table row per criterion, clause and invariant (the test as Class#method, its level, the clause it asserts; an adapter test's name says the state it shows). Use when writing, planning or reviewing tests, when a test is flaky or green too early, when implementing behaviour test first, when turning acceptance criteria into tests, or when a delivery stage needs the project's testing craft ("write the tests for this story", "TDD this", "why is this test flaky", "/testing"). Stack-neutral; Java and .NET examples.
---

# Tests that hold

A test is worth its cost when its result means something: green when the behaviour is there, red when it is not,
whatever ran before it. Everything below serves that sentence. The rules hold at every level; the level files in
`reference/` add what one level needs, and the two ways of writing a test have a file each.

| You are | Read |
|---|---|
| writing a test for a domain type's rule | `reference/unit.md` |
| testing a use case and the outgoing adapters it passes | `reference/port.md` |
| testing what an incoming adapter makes of a request and a result | `reference/adapter.md` |
| writing an end-to-end test, or its preconditions | `reference/e2e.md`, and the `e2e-testing` skill for the browser itself |
| implementing new behaviour test first | `reference/tdd.md` |
| turning a story's criteria (Given/When/Then) into tests | `reference/bdd.md` |

## 0. Read the project first

Read the project's conventions, searched in this order: an explicit path given to you, the configuration file the
project instructions name (a ``- configuration: `<file>` `` line in `AGENTS.md`), `AGENTS.md`, `CLAUDE.md`. Take
from them, and from the tests that exist: the test source sets and their commands, the test frameworks, the stub
for external systems (WireMock, WireMock.Net), the base classes, builders and page objects, how the store is reset,
how test classes and methods are named. Follow the local idiom; never add a second convention beside it. **Before
you write a helper, find the existing one** and call it. Adding a dependency, a source set or a runner is a stack
decision for the person, never part of writing a test.

Where nothing is said: JUnit 5 in `src/test/java/` (Java) or xUnit in `tests/<Root>.UnitTests/` (.NET), the
production package mirrored, test classes suffixed `Test`/`Tests`.

## 1. The level: the lowest that observes the `Then` from outside

| Level | What it runs | What it proves |
|---|---|---|
| `unit` | one aggregate, entity, value object or domain service, no framework | an invariant the domain never breaks, its guards included |
| `port` | the use case through its input port in the wired application, real outgoing adapters, the store as the project runs it in tests, an external system stubbed at the protocol | a scenario's business outcome: what is stored, refused, published, returned |
| `adapter` | one incoming adapter against a stubbed input port | what only the adapter produces: a text on the page, a status, a redirect, a payload, the command it hands the port |
| `e2e` | the running application through its surface | that the surface is wired to the use case, and what only a browser observes |

- **One scenario per story — its happy path — gets the end-to-end test.** Every other scenario is tested below the
  surface. A scenario whose `Then` only a browser observes is the exception, with the reason written down.
- **A use case is tested once, through its input port**, whichever adapter calls it — never once per adapter, and
  never with its output ports mocked: a mocked output port proves the mock, and the adapter behind it is the thing
  most likely to be wrong. Real outgoing adapters and the project's own database; an external system stubbed at the
  protocol, never mocked at the port and never called for real.
- **An adapter test only where the adapter itself produces what the `Then` says** — a quoted text, a status, a
  redirect, a mark. A value the use case computes (trimmed, counted, sorted) and the page merely shows gets the port
  test alone: an adapter test of it either repeats the port test or claims a computation its stub never ran.
- **A refusal the page shows needs both**: the port test proves the use case refuses, with which refusal; the
  adapter test proves the text, its stub answering with that same refusal — the same returned case, or the very
  failure type thrown, never a parent or a generic one.
- **A clause about what is stored is never asserted in an adapter test.** The stub answers what you told it.
- **Every invariant of a domain type has its own unit test**, its guards included; a guard nobody named is not written.
- **An adapter's case no scenario names** (a malformed body, a timeout) gets a test of its own beside the scenarios'.
- Where an output port has several adapters, each passes one **contract test** of what the port promises.

## 2. The rules of a test that holds

The names are Gerard Meszaros' (*xUnit Test Patterns*, 2007); the properties Robert C. Martin's F.I.R.S.T. and Kent
Beck's *Test Desiderata*.

1. **Fresh fixture, at every level.** A test creates what it needs, with values of its own — a title from the test's
   name and a random part, a user of its own — and reads no data another test can change. Resetting the store before
   each test is allowed; unique data is better, because the tests can then run in parallel. Seed data is shared: a
   test that changes a seeded record, or needs one of its values exact, creates its own. Meszaros' smell for the
   opposite is **Interacting Tests** — "expected 2 rows, got 4", only on the build server.
2. **The fixture is visible and minimal.** What the outcome depends on stands in the test — no seed row, no hidden
   builder default the reader has to look up (**Mystery Guest**). A **Minimal Fixture** holds what this behaviour
   needs; no general fixture shared by tests that need different parts of it. A builder may give defaults; the test
   states the values its outcome depends on (DAMP over DRY).
3. **One behaviour, named after what it proves.** `refusesAnEmptyTitle`, `showsTwoOfThreeTasksOpen` — what a user or
   caller observes, never the method under test, never a criterion's key or number. A test that stays green with the
   action deleted does not name the action: an adapter test whose stub answers with the outcome is named after the
   state it shows, never after the change that led there.
4. **A test can turn red.** Seen red before it is trusted, on its assertion — not on a missing class or a wiring
   error. Ask of every assertion: with the behaviour absent, would it turn red? A stub returning the expected answer,
   an assertion inside an `if`, an absence checked before the page reacted, an assertion on a mechanism the code does
   not use — each is green whatever the code does. Where the behaviour exists already, break the production code
   minimally, see red, revert: mutation testing by hand.
5. **No logic in a test.** No loop, no condition, no expected value built from parts; a test reads top to bottom.
   Cases that can fail apart are tests of their own. The rule is about the expected value: a helper call that makes a
   value unique belongs to the fixture — keep the value in a variable and assert against the variable.
6. **State over interaction.** Assert the outcome; assert an interaction only where it is the outcome — a message to
   a system the application does not own, an event published, an incoming adapter's translation: the command it hands
   its port, or that it does not call the use case for input that does not parse. What a stub returns is never the
   result a test asserts. Never mock what you are testing or a value object.
7. **Time and randomness are injected.** The code under test reaches the time only through an injected clock
   (`Clock`, `TimeProvider`) and chance only through an injected source; the test fixes the clock and seeds the
   source. Never `now()` in the code under test.
8. **No fixed sleep.** Wait for the state the action leads to, polling with a timeout.
9. **A flaky test is fixed at once**, never retried into green and never left for later. Its cause is usually one of
   the rules above.
10. **Select by a stable marker, never by position among siblings.** `//*[@data-test='task-title'][2]` breaks when the
    markup around the titles changes, although the page is right. Find the element by its own marker and the data the
    test created. This holds for every level that reads a page, the adapter test included.
11. **Test data a swap would turn red.** Two quantities, two names alike let the code mix them up and stay green;
    give each its own value.
12. **A test that held before is not rewritten to match new code.** Add a case; change an old expectation only where
    the requirement itself changed, and say so. Rearranging around the assertions — a new constructor argument, a
    locator that names the same markers on a new path — keeps every assertion, expected value and matcher as it was.

## 3. Refuse

- An output port mocked in a use case's test; an external system mocked at its port or called for real.
- A use case tested once per adapter, or a scenario tested end to end that is not the happy path, without a reason.
- A stored-state clause asserted in an adapter test; an adapter test named after the action it cannot perform.
- Rows written with SQL as an end-to-end test's precondition; a seeding entry in production code.
- A loop, a condition or a sleep in a test; `now()` in the code under test.
- A test green before the behaviour exists, a test never seen red, a retry that turns a flaky test green.
- A criterion's key in a test name, display name or comment.
- A spike or scratch test left behind.

## 4. Answer in rows

What this skill decides ends in tables with fixed columns, so a script can read and check it and a session leaves
the same trace as an automated stage. Write them into the file the caller names, or into your answer. One row per
item; no prose in a cell beyond the clause's own words.

```markdown
## Tests
| criterion | test |
| --- | --- |
| <criterion key> | <fully.qualified.Class>#<method> |

## Clauses
| criterion | n | clause | assertion | level |
| --- | --- | --- | --- | --- |
| <criterion key> | <n> | <the clause, verbatim from the criterion> | <path/to/TestFile>:<line> | unit / port / adapter / e2e |

## Invariants
| element | rule | invariant | test |
| --- | --- | --- | --- |
| <DomainType> | <n> | <the rule> | <fully.qualified.Class>#<method> |
```

- `criterion` is the key the story gives the criterion; without a story, a short kebab-case name of the behaviour.
- `test` is the fully qualified class and the method — a dotted module path in languages without classes.
- `clauses`: one row per `Then` and each `And` after it, `n` counting from 1; `assertion` is the line that asserts
  that clause, `level` one of the four words — never `adapter` for a clause about what is stored.
- `invariants`: one row per rule of every domain type the change touches, each with its own unit test — never a
  criterion's test. A type without a rule gets one row with `none — <why>` in place of the test.
- An adapter test carries the state it shows in its method name (`showsTwoOfThreeTasksOpen`) — what the stub was
  arranged with, never a change; no column of its own.
- A criterion with no test possible gets a line `- uncovered: <key> — <why>` under the tables. Nothing else.

## Boundaries

This skill writes and judges tests; it does not decide the stack. A missing runner, a missing stub library or a
missing source set is a question for the person — never installed while writing a test, and never replaced by a
lower-level test that asserts less. End-to-end tests drive a browser through the `e2e-testing` skill.
