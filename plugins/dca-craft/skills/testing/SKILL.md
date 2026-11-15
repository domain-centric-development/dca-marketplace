---
name: testing
description: The craft of writing tests that hold — the level a criterion is tested at (unit, port, adapter, end to end), a fresh and visible fixture per test, one behaviour named after what it proves, a test seen red before it is trusted, no logic in a test, state over interaction, an injected clock, no sleeps, no flaky test left standing, locators by stable marker — and the two ways of writing one, test first (TDD) and scenario first (BDD, Given/When/Then from the criteria to the test). Answers with one table row per criterion, clause and invariant (the test as Class#method, its level, the clause it asserts; an adapter test's name says the state it shows). Use when writing, planning or reviewing tests, when a test is flaky or green too early, when implementing behaviour test first, when turning acceptance criteria into tests, or when a delivery stage needs the project's testing craft ("write the tests for this story", "TDD this", "why is this test flaky", "/testing"). Stack-neutral; Java and .NET examples.
---

# Tests that hold

Green when the behaviour is there, red when it is not, whatever ran before. Rules hold at every level; read the
level file you need.

| You are | Read |
|---|---|
| writing a test for a domain type's rule | `reference/unit.md` |
| testing a use case and the outgoing adapters it passes | `reference/port.md` |
| testing what an incoming adapter makes of a request and a result | `reference/adapter.md` |
| writing an end-to-end test, or its preconditions | `reference/e2e.md`, and the `e2e-testing` skill for the browser itself |
| implementing new behaviour test first | `reference/tdd.md` |
| turning a story's criteria (Given/When/Then) into tests | `reference/bdd.md` |

## 0. Read the project first

- Conventions, in this order: a path given to you, the configuration file `AGENTS.md` names
  (``- configuration: `<file>` ``), `AGENTS.md`, `CLAUDE.md`.
- Take from them and the existing tests: source sets and commands, frameworks, the external-system stub (WireMock,
  WireMock.Net), base classes, builders, page objects, store reset, class/method naming. Follow the local idiom;
  never a second convention beside it.
- **Find the existing helper before writing one**, and call it.
- A new dependency, source set or runner is the person's stack decision, never part of writing a test.
- Nothing said: JUnit 5 in `src/test/java/` (Java) or xUnit in `tests/<Root>.UnitTests/` (.NET), production package
  mirrored, classes suffixed `Test`/`Tests`.

## 1. The level: the lowest that observes the `Then` from outside

| Level | What it runs | What it proves |
|---|---|---|
| `unit` | one aggregate, entity, value object or domain service, no framework | an invariant the domain never breaks, its guards included |
| `port` | the use case through its input port in the wired application, real outgoing adapters, the store as the project runs it in tests, an external system stubbed at the protocol | a scenario's business outcome: what is stored, refused, published, returned |
| `adapter` | one incoming adapter against a stubbed input port | what only the adapter produces: a text on the page, a status, a redirect, a payload, the command it hands the port |
| `e2e` | the running application through its surface | that the surface is wired to the use case, and what only a browser observes |

- **One scenario per story — its happy path — gets the e2e test.** The rest below the surface; a `Then` only a
  browser observes is the exception, reason written down.
- **A use case is tested once, through its input port**, never once per adapter, never with output ports mocked.
  Real outgoing adapters and the project's own database; an external system stubbed at the protocol, never mocked
  at the port, never called for real.
- **Adapter test only where the adapter itself produces what the `Then` says** (quoted text, status, redirect,
  mark). A value the use case computes (trimmed, counted, sorted) and the page shows gets the port test alone.
- **A refusal the page shows needs both**: port test proves which refusal; adapter test proves the text, its stub
  answering with that same refusal — same returned case or the very failure type, never a parent or generic one.
- **A stored-state clause is never asserted in an adapter test.**
- **Every invariant of a domain type has its own unit test**, guards included; a guard nobody named is not written.
- **An adapter case no scenario names** (malformed body, timeout) gets its own test.
- Output port with several adapters: each passes one **contract test** of what the port promises.

## 2. The rules of a test that holds

1. **Fresh fixture, every level.** A test creates what it needs with its own values (title from the test name plus
   a random part, its own user) and reads no data another test can change. Store reset before each test is
   allowed; unique data is better (parallel runs). Seed data is shared: a test that changes a seeded record or
   needs one of its values exact creates its own.
2. **Visible, minimal fixture.** What the outcome depends on stands in the test — no seed row, no hidden builder
   default. No general fixture shared by tests needing different parts. Builders may default; the test states the
   values its outcome depends on (DAMP over DRY).
3. **One behaviour, named after what it proves.** `refusesAnEmptyTitle`, `showsTwoOfThreeTasksOpen` — what a
   caller observes; never the method under test, never a criterion's key or number. A test green with the action
   deleted does not name the action: an adapter test whose stub answers with the outcome is named after the state.
4. **A test can turn red.** Seen red on its assertion — not a missing class or wiring error — before trusted. Ask
   of every assertion: with the behaviour absent, would it turn red? A test still green if every function under it
   returned nothing is thrown out. Always green whatever the code does: a stub returning the expected answer, an
   assertion inside an `if`, an absence checked before the page reacted, an assertion on a mechanism the code does
   not use. Behaviour already there: break the production code minimally, see red, revert.
5. **No logic in a test.** No loop, condition, or expected value built from parts. Cases that fail apart are
   separate tests. A helper that makes a value unique is fixture: keep it in a variable, assert against it.
6. **State over interaction.** Assert an interaction only where it is the outcome: a message to a system the
   application does not own, an event published, an incoming adapter's translation (the command it hands its
   port, or not calling the use case for unparseable input). A stub's return is never the asserted result. Never
   mock what you test or a value object.
7. **Time and randomness injected** (`Clock`, `TimeProvider`, a seeded source); the test fixes them. Never `now()`
   in the code under test.
8. **No fixed sleep.** Poll for the resulting state with a timeout.
9. **A flaky test is fixed at once** — never retried green, never deferred.
10. **Select by a stable marker, never by position among siblings** (`//*[@data-test='task-title'][2]` breaks on
    unrelated markup changes). Use the element's own marker and the data the test created. Holds for every level
    that reads a page, adapter tests included.
11. **Test data a swap would turn red.** Two quantities or names never share a value.
12. **A test that held before is not rewritten to match new code.** Add a case; change an old expectation only
    where the requirement changed, and say so. Rearranging (a new constructor argument, a locator naming the same
    markers on a new path) keeps every assertion, expected value and matcher.

## 3. Refuse

- An output port mocked in a use case's test; an external system mocked at its port or called for real.
- A use case tested once per adapter, or a non-happy-path scenario tested end to end without a reason.
- A stored-state clause asserted in an adapter test; an adapter test named after the action it cannot perform.
- SQL rows as an e2e precondition; a test seeding entry in production code (a product's demo data is a feature —
  no test reads its exact values).
- A loop, condition or sleep in a test; `now()` in the code under test.
- A test green before the behaviour exists, never seen red, or retried green.
- A criterion's key in a test name, display name or comment.
- A spike or scratch test left behind.

## 4. Answer in rows

Write into the file the caller names, or the answer. One row per item; no prose in a cell beyond the clause's own
words.

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

- `criterion`: the story's key; without a story, a short kebab-case name of the behaviour.
- `test`: fully qualified class and method — a dotted module path in languages without classes.
- `clauses`: one row per `Then` and each `And` after it, `n` from 1; `assertion` the line asserting that clause;
  `level` one of the four words — never `adapter` for a stored-state clause.
- `invariants`: one row per rule of every domain type the change touches, each with its own unit test — never a
  criterion's test. A type without a rule: one row with `none — <why>` in place of the test.
- An adapter test carries the state it shows in its method name (`showsTwoOfThreeTasksOpen`) — what the stub was
  arranged with, never a change; no column of its own.
- A criterion with no test possible: a line `- uncovered: <key> — <why>` under the tables. Nothing else.

## Boundaries

Writes and judges tests; does not decide the stack. A missing runner, stub library or source set is a question for
the person — never installed while writing a test, never replaced by a lower-level test that asserts less. Browser
tests: the `e2e-testing` skill.
