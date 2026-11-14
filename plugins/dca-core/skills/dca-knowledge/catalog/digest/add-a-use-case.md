# Add a use case — digest

Node: `/recipe/add-a-use-case.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Add one application-layer use case (a single intention: place an order, add an item, get a product).

## Steps (first sentence each)

1. **Find the context's form, then create the folder.** Look at the packages directly below `application/` (ignore `shared`).
2. **Pick write or read** — a write takes a `{Name}Command`; a read takes a `{Name}Query`.
3. **Name it, then generate the four files.** `{Name}` is the glossary operation's code word plus the term ([Name an operation in the glossary](/decision/name-an-operation-in-the-glossary.md)): named after its effect, never its trigger or caller (`ArchiveEntry`, not `ArchiveEntryOnExpiry`), never after a field it writes (`RaiseLimit`, not `SetLimit`).
4. **Declare output ports** the use case needs (repositories, publishers) as constructor parameters — interfaces only, defined in `application/shared/` or the marker package; never reference adapters.
5. **Implement `execute`** — load aggregate(s) via ports, run business logic *on the aggregate* (not in the service), persist, then publish + clear domain events for writes (in that order — `save` first), then assemble `{Name}Result`: values only — ids, value objects, nested part records named by content, read models — never the aggregate or an entity, also no…
6. **Draw the transaction boundary** — class-level `@Transactional` when every port is local; when the use case also reads from a remote-capable port (another context's API, a payment provider), do the remote reads first and wrap load–mutate–save–publish in `transactionBoundary.inTransaction(...)` instead.
7. **Expose it** from an incoming adapter (`*Resource`/`*PageController`) that maps `{Name}Result` → a `*Response` DTO at the edge.
8. **Verify** — run the project's architecture suite (`./gradlew test-architecture`, or `dotnet test -c Debug` against the architecture-test project); the rules below are checked.

## Templates

- `/template/use-case.md` Use case skeleton (InputPort + UseCase + Command/Query + Result): Domain-free skeleton for one application-layer use case. — code: `/template/use-case/java.md`
- `/template/domain-exception.md` Domain exception skeleton: Domain-free skeleton for the failures the inner layers raise, each with the base class its layer owns. — code: `/template/domain-exception/java.md`
