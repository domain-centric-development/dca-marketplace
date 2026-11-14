---
type: Recipe
title: Put an end-to-end test's preconditions in place through the input port
tags: [recipe, testing, use-case, port-in]
review: draft
owner: DCA catalog maintainers
evidence: [/guide/e2e-testing.md, /guide/testing-levels.md, /marker/port-in/usecase.md]
---

An end-to-end test is about one interaction: the click, the form, the page under test. Everything before it is precondition. The test puts that state in place through the same input ports the pages call — never by writing rows to the database, and not by clicking through pages it is not about. The test is one more incoming adapter: the domain's invariants hold for the data it creates, and a schema change does not break it.

## Steps

1. **Name the one interaction** the test is about; everything before it is precondition.
2. **Give the precondition data of its own** — a title with a random part, a user of its own — and keep each value in a variable the assertion uses ([Pitfall](/pitfall/a-shared-fixture-makes-tests-interact.md)).
3. **Call the use case for each precondition.** Where the test starts the application in its own process, take the input port from the wired application and call it; assert that it succeeded, so a refusal does not leave the test running on a state that never came about.
4. **Where the application runs beside the test,** put the seeding entry — an endpoint or a command — in the test source set or a test profile, never in production code. A seeding entry that ships is a way past every check the page makes.
5. **Get the session from an API or a token** and hand it to the browser context. Only the test of the login itself fills the login form.
6. **Check that each step put in place directly has a test through the surface** — the happy path of the story that delivered it. A step without one is a gap: write that test first, or click the step through here and say why. Only an epic's journey test walks the whole way.
7. **Perform the one interaction and assert the element it changes**, found by a stable marker and the data the test created.

## Anchors

- Guide: [E2E testing](/guide/e2e-testing.md) · [Test levels](/guide/testing-levels.md)
- Marker: [UseCase](/marker/port-in/usecase.md)
- Recipe: [Isolate the data of integration tests](/recipe/isolate-the-data-of-integration-tests.md)
