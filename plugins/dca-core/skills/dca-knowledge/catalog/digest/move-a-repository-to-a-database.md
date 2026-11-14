# Move a repository from memory to a database — digest

Node: `/recipe/move-a-repository-to-a-database.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Put an aggregate into a relational database **without touching the output port or the domain**.

## Steps (first sentence each)

1. **Leave the port and the domain alone** — `{Name}Repository` in `application/shared/` and the `{Name}` aggregate do not change.
2. **Write the schema as a migration** — one versioned script per change (Flyway, Liquibase, EF Core migrations, DbUp — whatever the stack has), applied when the application starts or before it deploys.
3. **State the rules the store holds as constraints** — an identifier that names one thing is a unique column; "at most one *active* one per owner" is a partial unique index.
4. **Write the adapter** — `Jdbc{Name}Repository` ([template](/template/jdbc-repository-adapter.md)), a JPA adapter with its own entity ([template](/template/jpa-repository-adapter.md)), or the stack's equivalent (Dapper, EF Core).
5. **Take the row lock where a check precedes a change** — a read that a use case checks and then changes on (a quantity reserved, a state advanced) is read `FOR UPDATE` inside the transaction, so a second caller waits instead of deciding on the same row.
6. **Make the transaction boundary real** — the boundary opens the database transaction, every repository and store of the use case writes in it, and an outbox that records the use case's events writes in it too ([outbox entry written after commit](/pitfall/outbox-entry-written-after-commit.md)).
7. **Move the in-memory adapter to the test sources, or delete it** — the use cases' port tests now run against the database adapter; an in-memory adapter that stays (for a contract test, or a fast local run) stores copies, on write and on read ([an in-memory store hands out live aggregates](/pitfall/an-in-memory-store-hands-out-live-aggregates.md)).
8. **Test the adapter against the real database** — an integration test per adapter against the engine production runs, started in a container; the database's own behaviour (constraints, locks, the type mapping) is what the test is for.
9. **Verify nothing above the port changed** — the existing port and domain tests pass untouched, now against the database; then the project's architecture suite.

## Templates

- `/template/jdbc-repository-adapter.md` JDBC repository adapter skeleton (JdbcClient): Domain-free skeleton for a **JDBC outgoing adapter** that implements the *same* `{Name}Repository` output port as the [in-memory adapter](/template/repository-with-in-memory-adapter.md) and the [JPA adapter](/template/jpa-repository-adapter.md). — code: `/template/jdbc-repository-adapter/java.md`
- `/template/jpa-repository-adapter.md` JPA repository adapter (same output port, Spring Data + entity + mapper): Domain-free skeleton for a **JPA outgoing adapter** that implements the *same* `{Name}Repository` output port as the [in-memory adapter](/template/repository-with-in-memory-adapter.md). — code: `/template/jpa-repository-adapter/java.md`
- `/template/repository-with-in-memory-adapter.md` Repository skeleton (output port + in-memory outgoing adapter): Domain-free skeleton for a repository: the collection-like output port for one aggregate root. — code: `/template/repository-with-in-memory-adapter/java.md`
- `/template/aggregate-root.md` Aggregate root skeleton (BaseAggregateRoot + Id + domain event): Domain-free skeleton for an aggregate root: the consistency boundary that enforces invariants and registers domain events. — code: `/template/aggregate-root/java.md`
