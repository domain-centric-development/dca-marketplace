---
type: Section
title: A test that holds
chapter: Test Levels in Domain-Centric Architecture
source: guide
tags: [guide, section]
---

**Rule: a test proves one behaviour, from preconditions it builds itself, and it can turn red.**

The levels say where a test runs. This section says how a test is written so that its result means something:
green when the behaviour is there, red when it is not, whatever ran before it. The rules hold at every level. The
names come from Gerard Meszaros, *xUnit Test Patterns* (2007); the properties from Robert C. Martin's F.I.R.S.T.
(fast, independent, repeatable, self-validating, timely) and Kent Beck's *Test Desiderata*.

### A fresh fixture, at every level

**Rule: a test creates what it needs, with values of its own, and reads no data another test can change.**

Meszaros calls the state a test runs against its *fixture*. A **Fresh Fixture** is built by the test itself; a
**Shared Fixture** is built once and read by many tests. A shared fixture saves setup and costs independence: one
test changes a record, and another fails later, in another order, without a reason it can show. Meszaros names
that smell **Interacting Tests**. It shows up as "expected 2 rows, got 4", only on the build server, only when the
tests run in parallel.

So a test gives its data values of its own — a title made from the test's name and a random part, a user of its
own — and asserts only about that data. Emptying the store before each test is allowed. Unique data is better,
because the tests can then run in parallel and against a store that is not empty. A test passes alone, first,
last, repeated and in parallel.

Seed data is a shared fixture too. A test that changes a seeded record, or needs one of its values to be exact,
creates its own record instead and reads only that one.

### The fixture is visible and minimal

**Rule: the preconditions a test depends on stand in the test, and the fixture holds no more than the behaviour
needs.**

A test whose outcome depends on a seed file, on a row someone inserted once or on a builder default its reader
cannot see has a **Mystery Guest** (Meszaros): to understand why it is green, the reader has to look somewhere
else. A **Minimal Fixture** holds what this one behaviour needs. A general fixture shared by tests that need
different parts of it makes every one of them depend on all of it.

Builders and helpers are welcome, under one condition: DAMP over DRY (*Software Engineering at Google*, 2020,
ch. 12). A builder gives defaults; the test states the values its outcome depends on.
`aTask().titled("Write report").completed()` before an assertion on "Write report" can be read in one place;
`aCompletedTask()` with the title hidden in the builder cannot.

### One behaviour, named after what it proves

**Rule: a test proves one behaviour, and its name says which. A test that stays green with the action deleted does
not name the action.**

One behaviour per test means one reason to fail: the name of a red test says what broke. The name describes what a
user or a caller observes — `refusesAnEmptyTitle`, `showsTwoOfThreeTasksOpen` — never the method under test and
never an id from the backlog.

The name is a claim, and the test has to keep it. An adapter test runs against a stubbed input port, and the
stub's answer is the test's own arrangement. Such a test cannot prove the change that led to the answer, so it is
named after the state it shows (`showsTwoOfThreeTasksOpen`), not after the change
(`showsOneOpenTaskLessAfterCompletingOne`). The change belongs to the port test, which runs the real use case. A
value the use case computes — trimmed, counted, sorted — gets no adapter test at all
([above](#the-use-case-once-each-adapter-its-translation)).

### A test can turn red

**Rule: a test is seen red before it is trusted. A test that asserts its own stub back proves nothing.**

A new test fails first, on its assertion — not on a missing class or a wiring error — and turns green when the
behaviour is built. A test that is green before the behaviour exists is green whatever the code does. The usual
causes are a stub that already returns the expected answer, an assertion inside a condition nothing meets, an
absence checked before the page has reacted, and an assertion on a mechanism the code does not use. For each
assertion, ask: with the behaviour absent, would it turn red?

Where the behaviour exists already, the test cannot be seen red first. Change the production code minimally so
that the behaviour is gone, watch the test turn red, and revert the change. That is mutation testing, done by hand
for one rule.

### No logic in a test

**Rule: a test reads top to bottom — no loop, no condition, no expected value built from parts.**

Logic in a test needs a test of its own (*Software Engineering at Google*, ch. 12). A loop over cases hides which
case failed. A condition skips its assertion when nothing meets it. An expected value built by the same
concatenation as the code repeats the code's mistake. Cases that can fail apart are tests of their own, and an
expected value is a literal or the very value the test put in.

The rule is about the expected value, not about the fixture. A helper call that makes a title unique belongs to the
fixture: the test keeps the value in a variable and asserts against that variable, never against a string rebuilt
from its parts.

### State over interaction

**Rule: a test asserts the outcome. It asserts an interaction only where the interaction is the outcome — a message
to a system the application does not own, an event published, the call an incoming adapter makes on its port. What
a stub returns is never the result a test asserts.**

This is the classical side of the debate Martin Fowler describes in *Mocks Aren't Stubs* (2004). Collaborators the
application owns are real in tests; only what it does not own is replaced, at its boundary (Vladimir Khorikov,
*When to Mock*, 2020). A test that verifies the code called `save` proves the call, not that anything was stored.
It breaks when the code is restructured and stays green when the stored value is wrong. The levels above follow
from the same choice: real outgoing adapters and the project's own database, an external system stubbed at the
protocol.

An adapter test stubs its input port and asserts what the adapter makes of the stub's answer, never the answer
itself. The adapter's translation goes both ways, and both are its outcome: the command it hands to the port for a
request, and — for input that does not parse — that it does not call the use case at all. Asserting that command,
or that the port was not called, is asserting the adapter. Asserting a value the stub was arranged to return is
asserting the stub.

### Time and randomness are injected

**Rule: the code under test reaches the time and chance only through what is injected. A test fixes the clock and
seeds the source.**

A test that reads the real clock passes in the morning and fails at midnight. One that draws from an unseeded
source fails once in a thousand runs. Domain and application code take a clock (`Clock` in Java, `TimeProvider` in
.NET) and a random source as dependencies and never call `now()` themselves; the test hands in a fixed clock and a
seeded source. In the browser the page's clock is faked and paused ([E2E Testing](/guide/e2e-testing/every-criterion-a-test-the-happy-path-end-to-end.md)).

### No fixed sleep

**Rule: a test waits for a condition, polling with a timeout — never for a fixed time.**

A sleep is too short on a loaded machine and too long everywhere else. A test waits for the state the action leads
to — the element, the row, the message — with a timeout that fails the test when the state never comes.

### A flaky test is fixed at once

**Rule: a test that fails without a change is fixed the day it is seen, never retried into green.**

A suite with even a small share of flaky tests stops being read: a red run is rerun instead of looked at
(*Software Engineering at Google*, ch. 11). An automatic retry hides the cause and keeps the cost. The causes are
usually the ones above: a shared fixture, the real clock, a sleep, a locator tied to the markup around an element.

### Select by a stable marker, never by position

**Rule: a test that reads a page locates an element by a stable marker of its own, never by its position among
siblings.**

`//*[@data-test='task-title'][2]` means the second title within one parent. When a later change gives each task an
entry of its own, every title is the first in its parent; the locator finds nothing, although the page is right. A
locator that breaks when the markup around the element changes is a test that changes without a change in
behaviour. Beck's *Test Desiderata* call the property it lacks *structure-insensitive*. The rule holds for an
adapter test that reads the rendered page as much as for a browser test; [E2E Testing](/guide/e2e-testing/data-test-attributes.md)
shows the locator that replaces it.
