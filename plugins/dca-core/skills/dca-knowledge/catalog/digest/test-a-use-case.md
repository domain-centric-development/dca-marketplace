# Test a use case — digest

Node: `/recipe/test-a-use-case.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Test a use case as an application-layer unit test: construct the `*UseCase`, feed it a `Command` (write) or `Query` (read), assert on the returned `Result` and on observable state.

## Steps (first sentence each)

1. **Instantiate the use case directly** — no Spring context.
2. **Fake the output ports, not the domain** — implement each output-port interface with a small `Test{Aggregate}Repository` backed by a `ConcurrentHashMap`, and a `TestDomainEventPublisher` that records events.
3. **Arrange through the port** — seed state by calling `fakeRepo.save(aggregate)` with genuine domain objects, so the test round-trips real data.
4. **Act once** — call `useCase.execute(command)` exactly once per test.
5. **Assert on the contract, not internals** — check the `Result` fields and observable side effects (e.g. `fakeRepo.findById(...)` present/absent).
6. **Verify event hygiene** — if the use case publishes, assert the fake publisher recorded the expected event and that `publishAndClearEvents` left the aggregate's `domainEvents()` empty.
7. **One behaviour per test** — group scenarios with `@Nested` + `@DisplayName`; each `@Test` covers a single behaviour named in the ubiquitous language.

## Templates

- `/template/use-case-test.md` Use-case test skeleton (JUnit 5 + hand-written fake ports): Domain-free skeleton for a use-case unit test. — code: `/template/use-case-test/java.md`
