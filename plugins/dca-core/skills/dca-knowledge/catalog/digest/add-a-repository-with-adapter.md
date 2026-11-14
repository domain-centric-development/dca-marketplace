# Add a repository with adapter — digest

Node: `/recipe/add-a-repository-with-adapter.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Give an aggregate root a persistence port: an interface in the application layer, an implementation in an outgoing adapter.

## Steps (first sentence each)

1. **Define the interface** `{Name}Repository extends Repository<{Name}, {Name}Id>` in `application/shared/` — this is an output port, so it holds only interfaces.
2. **Only for aggregate roots** — no repositories for entities or value objects inside the aggregate; reach them through the root.
3. **Choose the persistence technique** — the port does not change with it; the adapter does: - **In-memory** ([repository + in-memory adapter](/template/repository-with-in-memory-adapter.md)) — start here: a `ConcurrentHashMap` behind the port, copying on write *and* on read, plus a contract test on the port that every later implementation runs.
4. **Implement in an outgoing adapter** — e.g. `InMemory{Name}Repository` in `adapter/outgoing/`.
5. **Wire by inversion** — use cases depend on the interface (constructor injection); the adapter is the only thing that knows the store.
6. **Use explicit `save()`** — persistence-oriented style, not a live collection illusion ([Layer rules](/guide/rules.md)).
7. **Verify** — the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project).

## Templates

- `/template/repository-with-in-memory-adapter.md` Repository skeleton (output port + in-memory outgoing adapter): Domain-free skeleton for a repository: the collection-like output port for one aggregate root. — code: `/template/repository-with-in-memory-adapter/java.md`
- `/template/jdbc-repository-adapter.md` JDBC repository adapter skeleton (JdbcClient): Domain-free skeleton for a **JDBC outgoing adapter** that implements the *same* `{Name}Repository` output port as the [in-memory adapter](/template/repository-with-in-memory-adapter.md) and the [JPA adapter](/template/jpa-repository-adapter.md). — code: `/template/jdbc-repository-adapter/java.md`
- `/template/jpa-repository-adapter.md` JPA repository adapter (same output port, Spring Data + entity + mapper): Domain-free skeleton for a **JPA outgoing adapter** that implements the *same* `{Name}Repository` output port as the [in-memory adapter](/template/repository-with-in-memory-adapter.md). — code: `/template/jpa-repository-adapter/java.md`
