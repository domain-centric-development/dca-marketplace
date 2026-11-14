---
type: Pitfall
title: A test named after an action it cannot prove
tags: [pitfall, testing, adapter]
review: draft
owner: DCA catalog maintainers
evidence: [/guide/testing-levels.md, /marker/port-in/usecase.md]
---

An incoming adapter's test stubs the input port. It is named after the scenario's action or after a value the use case computes — `showsOneOpenTaskLessAfterCompletingOne`, `showsATitleWithoutSurroundingSpaces` — but the stub answers with the outcome. The test performs the action against the stub and asserts what the stub returns; it stays green with the action, or the computation, deleted.

## Why it is wrong

- The stub's answer is the test's own arrangement. Asserting it proves the stub, not the code.
- The name claims a behaviour no code under test performs, so a reader takes the change, the trim or the count as covered by this test.
- The real proof — the port test, which runs the use case — exists beside it or is missing; either way this test adds nothing but a false claim.

## Do instead

- **An adapter test only where the adapter itself produces what the `Then` says:** a quoted text, a status, a redirect, a mark. A value the use case computes and the page merely shows gets the port test alone.
- **Name an adapter test after the state it shows** (`showsTwoOfThreeTasksOpen`): arrange the stub once with that state, make the one request, assert the element.
- **Test the change through the input port,** with the real use case and the real store.
- **The action's own translation is a test of its own:** the command the adapter hands the port, or that it does not call the use case for input that does not parse.

## Anchors

- Guide: [Test levels](/guide/testing-levels.md)
- Marker: [UseCase](/marker/port-in/usecase.md)
- Pitfall: [A green test that asserts nothing](/pitfall/a-green-test-that-asserts-nothing.md)
