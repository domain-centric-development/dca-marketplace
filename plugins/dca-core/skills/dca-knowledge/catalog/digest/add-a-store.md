# Add a store — digest

Node: `/recipe/add-a-store.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Give a context a persistence port for operational data that has **no aggregate of its own** — login attempts, an audit trail, metric snapshots, an event log.

## Steps (first sentence each)

1. **Confirm it is a Store, not a Repository.** Run [Repository vs Store](/decision/repository-vs-store.md).
2. **Define the interface** `{Name}Store extends Store` in `application/shared/` — an output port, so interfaces only.
3. **Implement in an outgoing adapter** — e.g. `InMemory{Name}Store` or `Jdbc{Name}Store` in `adapter/outgoing/persistence/`, generated from the [store + in-memory adapter template](/template/store-with-in-memory-adapter.md).
4. **Wire by inversion** — use cases depend on the `{Name}Store` interface (constructor injection); only the adapter knows the store technology.
5. **Verify** — the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project).

## Templates

- `/template/store-with-in-memory-adapter.md` Store skeleton (output port + in-memory outgoing adapter): Domain-free skeleton for a **Store**: the output port for operational data that has **no aggregate lifecycle** — login attempts, an audit trail, metric snapshots, an event log. — code: `/template/store-with-in-memory-adapter/java.md`
