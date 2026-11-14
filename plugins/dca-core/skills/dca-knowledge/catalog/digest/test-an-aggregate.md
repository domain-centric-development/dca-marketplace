# Test an aggregate — digest

Node: `/recipe/test-an-aggregate.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Test an aggregate root as a pure domain unit test: no mocks, no Spring, no infrastructure.

## Steps (first sentence each)

1. **No test doubles** — the domain layer has zero output-port dependencies ([aggregates must not hold references to output ports](/rule/tactical/dca-tac-002.md)), so there is nothing to mock.
2. **Create through the factory** — `{Aggregate}.create(...)`, not a raw constructor, so creation invariants and the creation event are exercised.
3. **Assert state after a command** — call a domain method (e.g. `updatePrice(...)`) and assert the resulting state via public accessors.
4. **Assert invariants reject bad input** — use `assertThrows(IllegalArgumentException.class, () -> ...)` for each guarded rule (zero/negative amounts, illegal state transitions).
5. **Assert domain events** — after a state change, check `aggregate.domainEvents()` has the expected type and payload.
6. **One behaviour per test** — group with `@Nested` + `@DisplayName`; name each `@Test` in the ubiquitous language.
