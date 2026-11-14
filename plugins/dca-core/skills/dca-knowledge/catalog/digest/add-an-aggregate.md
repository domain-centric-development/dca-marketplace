# Add an aggregate — digest

Node: `/recipe/add-an-aggregate.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Add an aggregate root: the transactional consistency boundary that owns its invariants and emits domain events.

## Steps (first sentence each)

1. **Model the boundary** — one aggregate = one consistency boundary.
2. **Generate from the [aggregate template](/template/aggregate-root.md)**: `{Name}Id` (typed identity) and `{Name}` (root extends `BaseAggregateRoot`) in the domain model package `domain/model/`, `{Name}Created` (domain event) in `domain/event/`.
3. **Enforce invariants in a factory** — `static {Name} create(...)` validates and registers the creation event.
4. **Register domain events** on every meaningful state change; the use case publishes + clears them after save.
5. **Add the repository** — interface `{Name}Repository extends Repository<{Name}, {Name}Id>` in `application/shared/` (output port), implementation in `adapter/outgoing/` ([Deviations from the literature](/guide/readme/deviations-from-the-literature.md)).
6. **Verify** — the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project).

## Templates

- `/template/aggregate-root.md` Aggregate root skeleton (BaseAggregateRoot + Id + domain event): Domain-free skeleton for an aggregate root: the consistency boundary that enforces invariants and registers domain events. — code: `/template/aggregate-root/java.md`
