---
type: Recipe
title: Test a use case
tags: [recipe, testing, use-case]
review: draft
owner: DCA catalog maintainers
evidence: [/guide/testing-levels.md, /marker/port-in/usecase.md, /marker/port-out/repository.md, /marker/port-out/domaineventpublisher.md]
---

Test a use case once, through its input port, in the wired application: real outgoing adapters, the store as the project runs it in tests (its own database engine in a container), an external system stubbed at the protocol. Feed it a `Command` (write) or `Query` (read) and assert the scenario's business outcome — what it returns, stores, refuses or publishes. This **port test** is the test of the use case, whichever incoming adapter calls it. No output port is replaced: a faked or mocked output port proves the double, and the adapter behind it — the part most likely to be wrong — would need a test of its own anyway. Real domain objects are used directly, never mocked.

## Steps

1. **Take the input port from the wired application** — the test starts the application as it runs in tests (a Spring Boot test, a `WebApplicationFactory`) and asks it for `{Name}InputPort`. Never `new` the use case with doubles.
2. **Give the test data of its own** — values from the test's name and a random part, kept in variables the assertions use; no seeded record the test changes or needs exact ([A shared fixture makes tests interact](/pitfall/a-shared-fixture-makes-tests-interact.md)). Isolate the store between tests by one of the shapes in [Isolate the data of integration tests](/recipe/isolate-the-data-of-integration-tests.md).
3. **Arrange the `Given` through the input ports** — call the use cases that create the state, and assert that each succeeded; an ignored result swallows a refusal. An external system's answer is the stub's arrangement (WireMock, WireMock.Net).
4. **Act once** — call `execute(command)` exactly once.
5. **Assert the outcome** — the `Result`, and what is stored, read back through the repository or a query the use case uses. A refusal is asserted in the form the context carries it: the exact thrown type, or the exact returned case, with its values.
6. **Assert an event where it is the outcome** — the published event, observed where the project observes events in tests; and, for a request to an unmanaged system, the request the stub received. Never a call on a double.
7. **One behaviour per test**, named after what it proves in the ubiquitous language; the scenario's key never appears in the name.

## Test-quality checklist

- The use case through its input port, once per scenario — never once per incoming adapter that calls it.
- Real outgoing adapters and the real store; an external system stubbed at the protocol, never mocked at its port and never called for real.
- Where an output port has several adapters, one contract test of what the port promises runs against each.
- Real aggregates and value objects; no double of a domain type.
- State over interaction: the outcome, not the calls.

## Anchors

- Guide: [Test levels](/guide/testing-levels.md)
- Template: [Use-case port test skeleton](/template/use-case-test.md)
- Markers: [UseCase<INPUT, OUTPUT>](/marker/port-in/usecase.md) · [Repository<T, ID>](/marker/port-out/repository.md) · [DomainEventPublisher](/marker/port-out/domaineventpublisher.md)
- The use case under test: [Add a use case](/recipe/add-a-use-case.md) · its ports: [Add a repository with adapter](/recipe/add-a-repository-with-adapter.md)
- An external system in the same test: [Test a scenario integrated](/recipe/test-a-scenario-integrated.md)
- The invariants it relies on: [Test an aggregate](/recipe/test-an-aggregate.md)
