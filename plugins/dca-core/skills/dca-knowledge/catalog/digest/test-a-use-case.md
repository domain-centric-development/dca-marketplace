# Test a use case — digest

Node: `/recipe/test-a-use-case.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Test a use case once, through its input port, in the wired application: real outgoing adapters, the store as the project runs it in tests (its own database engine in a container), an external system stubbed at the protocol.

## Steps (first sentence each)

1. **Take the input port from the wired application** — the test starts the application as it runs in tests (a Spring Boot test, a `WebApplicationFactory`) and asks it for `{Name}InputPort`.
2. **Give the test data of its own** — values from the test's name and a random part, kept in variables the assertions use; no seeded record the test changes or needs exact ([A shared fixture makes tests interact](/pitfall/a-shared-fixture-makes-tests-interact.md)).
3. **Arrange the `Given` through the input ports** — call the use cases that create the state, and assert that each succeeded; an ignored result swallows a refusal.
4. **Act once** — call `execute(command)` exactly once.
5. **Assert the outcome** — the `Result`, and what is stored, read back through the repository or a query the use case uses.
6. **Assert an event where it is the outcome** — the published event, observed where the project observes events in tests; and, for a request to an unmanaged system, the request the stub received.
7. **One behaviour per test**, named after what it proves in the ubiquitous language; the scenario's key never appears in the name.

## Templates

- `/template/use-case-test.md` Use-case port test skeleton (the input port in the wired application): Domain-free skeleton for a use case's port test. — code: `/template/use-case-test/java.md`
