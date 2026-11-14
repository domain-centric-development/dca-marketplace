---
type: Pitfall
title: A shared fixture makes tests interact
tags: [pitfall, testing]
review: draft
owner: DCA catalog maintainers
evidence: [/guide/testing-levels.md, /guide/e2e-testing.md]
---

Several tests read the same data — a seeded record, a row an earlier test created, a list built once before all tests. Each passes alone. In the suite one changes the data and another fails later, in another order, without a reason it can show: "expected 2 rows, got 4", only on the build server, only in parallel. Gerard Meszaros calls the shared state a **Shared Fixture** and the symptom **Interacting Tests**; a precondition the reader cannot see in the test is a **Mystery Guest**.

## Why it is wrong

- A test's result then depends on which tests ran before it, so a red run says nothing about the behaviour.
- Seed data looks fixed and is shared all the same: a test that lowers a seeded count or uses up a seeded record breaks every test that reads it afterwards.
- A reset before every test hides the coupling only as long as the tests run one after another; it rules out parallel runs and a store that is not empty.
- The precondition sits in a seed file or a set-up method, so a reader cannot tell from the test why it is green.

## Do instead

- **A Fresh Fixture per test:** the test creates what it needs, with values of its own — a title from its name and a random part, a user of its own — and asserts only about that data.
- **A Minimal Fixture:** only what this behaviour needs, stated in the test; a builder gives defaults, the test states the values its outcome depends on.
- **Seeded data is read, never changed,** and never needed exact. A test that changes a seeded record or needs one of its values exact creates its own record.
- **Run the whole suite once,** not only the new test; a test that passes alone and fails in the suite is not done.

## Anchors

- Guide: [Test levels](/guide/testing-levels.md) · [E2E testing](/guide/e2e-testing.md)
- Recipe: [Isolate the data of integration tests](/recipe/isolate-the-data-of-integration-tests.md) · [Put an end-to-end test's preconditions in place through the input port](/recipe/seed-an-end-to-end-test-through-the-input-port.md)
