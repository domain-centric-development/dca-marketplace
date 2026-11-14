# Add a bulk operation — digest

Node: `/recipe/add-a-bulk-operation.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Perform one operation over many aggregates at once — delete all, archive everything completed before a date, purge expired sessions.

## Steps (first sentence each)

1. **Name it in the ubiquitous language** — `ArchiveCompletedTasks`, `PurgeExpiredSessions`, not `BulkDelete` or `Cleanup`.
2. **Add the method to the repository port** — `deleteAll()`, `archiveAllBefore(Instant cutoff)`, `deleteExpiredBefore(Instant now)` on `{Name}Repository` in `application/shared/`.
3. **Write a command use case that calls it** — the use case builds the cutoff from the command, calls the port method once, and returns the count in the `{Name}Result`.
4. **Register no domain event** — nothing was loaded, so no aggregate registered anything, and inventing events per row would fake N facts for one action.
5. **Draw the boundary declaratively** — class-level `@Transactional` is the right form: the port method is the whole unit of work, and only local ports are called ([Declarative or explicit transaction boundary](/decision/declarative-vs-explicit-transaction-boundary.md)).
6. **Implement the method in every adapter** — the in-memory adapter filters its map, the JDBC adapter runs one `DELETE … WHERE` or `UPDATE … WHERE`, the JPA adapter a bulk query.
7. **Verify** — the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project).

## Templates

- `/template/use-case.md` Use case skeleton (InputPort + UseCase + Command/Query + Result): Domain-free skeleton for one application-layer use case. — code: `/template/use-case/java.md`
