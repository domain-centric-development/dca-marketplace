# Use Case Pattern Reference

The central reference for the DCA use-case structure. Read it before you write, review or restructure a
use case. It complements [checklist.md](checklist.md) (for the audit) and
[naming-conventions.md](naming-conventions.md) (for the naming tables).

---

## 1. Complete folder structure of a use case

```
{basePackage}/{boundedcontext}/application/{usecasename}/
├── {Name}InputPort.java       # interface: extends UseCase<{Input}, {Output}>
├── {Name}{ImplSuffix}.java    # impl:      @Service [@Transactional], implements *InputPort
├── {Name}Command.java         # input (writes)  -- Java record
│   OR
│   {Name}Query.java           # input (reads)   -- Java record
└── {Name}Result.java          # output          -- Java record
```

**Example** (`placeOrder` in the `orders` context, default convention):

```
com.example.shop/orders/application/placeorder/
├── PlaceOrderInputPort.java   # extends UseCase<PlaceOrderCommand, PlaceOrderResult>
├── PlaceOrderUseCase.java     # @Service @Transactional implements PlaceOrderInputPort
├── PlaceOrderCommand.java     # record(CustomerId customerId, List<LineItem> items)
└── PlaceOrderResult.java      # record(OrderId orderId, Instant placedAt)
```

### Flat or grouped by feature

A small context keeps `application/{usecasename}/`. Once the flat list has grown past a dozen entries and
cohesive groups have emerged, the optional **feature** level goes in between:
`application/{feature}/{usecasename}/` — a domain-named navigation frame below the layer (`session`,
`cartrecovery`, `checkoutcompletion`), not a module, not an aggregate owner. Within one context exactly one form
applies (`DCA-USE-014`); the feature packages must not form a cycle (`DCA-CYC-005`); `application/shared/` stays
context-wide — no `application/{feature}/shared/`. The domain is not mirrored per feature. A vertical slice
`{context}/{feature}/{domain,application,adapter}` is **not** a feature.

### Folder name (lowercase, no separator)

The folder name is **always lowercase without a separator**: `placeorder`, `getorderbyid`, `cancelorder`.
Not `placeOrder`, not `place-order`, not `PlaceOrder`.

**Why:** Java package names are lowercase by convention and may not contain `-`. Use-case folders *are* Java
packages, so package rules apply. `place-order` would not compile; `placeOrder` is legal but breaks the lowercase
convention.

**Loss of readability accepted:** `getorderbyid` reads worse than `get-order-by-id`, but consistency with the
package convention weighs more. The classes *inside* (PascalCase) are the primary anchor for readability anyway.

---

## 2. File roles in detail

### `{Name}InputPort.java` — the interface

```java
public interface PlaceOrderInputPort extends UseCase<PlaceOrderCommand, PlaceOrderResult> {
    // no additional methods -- execute(Input) comes from UseCase
}
```

- **Single-method interface.** `UseCase<I, O>` defines exactly `O execute(I input)`. Add no further methods —
  if a second operation is needed, it is a second use case.
- **Owned by the application layer.** The interface lives in `application/{usecasename}/`, not in `domain/`.
  Adapters (controllers, event consumers) depend on this interface.
- **Alternative suffixes.** Some projects use `*UseCase` as the interface name (Hombergs style) and
  `*ApplicationService` for the implementation. Both are DCA-compliant — pick **one** scheme per project and
  keep it.

### `{Name}{ImplSuffix}.java` — the implementation

```java
@Service
@Transactional
public class PlaceOrderUseCase implements PlaceOrderInputPort {

    private final OrderRepository orderRepository;
    private final CustomerDataPort customerData;
    private final DomainEventPublisher events;

    // constructor injection
    public PlaceOrderUseCase(OrderRepository r, CustomerDataPort c, DomainEventPublisher e) { ... }

    @Override
    public PlaceOrderResult execute(PlaceOrderCommand cmd) {
        // 1. load aggregates / data through output ports
        // 2. call domain methods (aggregate behaviour, never write fields directly)
        // 3. persist through the repository
        // 4. publish domain events
        // 5. map to the result
    }
}
```

- **Stereotype or registration** — both are valid. With the Spring preset, `@Service` on the implementation,
  never on the interface, never in `domain/`; with another preset or without a framework, a configuration
  registers the use case behind its input port. `DCA-NAM-002` reports missing stereotypes as information only;
  static references cannot prove runtime wiring.
- **`@Transactional`** only for **commands** (writes). Queries are read-only — `@Transactional(readOnly = true)`
  is optional but sensible when the project uses it consistently.
- **No remote port inside the transaction.** If the use case calls an output port that may leave the process
  (another context's API, a payment provider, a mail gateway), no class-level `@Transactional`: remote read
  first, then `transactionBoundary.inTransaction(() -> { load; mutate; save; publish; })` (`TransactionBoundary`
  from the building blocks — an execution abstraction of the application layer, not a port). Otherwise the
  transaction holds the database connection for the remote round trip (`DCA-USE-013`).
- **Constructor injection.** No `@Autowired` on fields. Records or `@RequiredArgsConstructor` (Lombok) are fine.
- **Output ports only.** Never direct access to `EntityManager`, `JdbcTemplate`, `KafkaTemplate` and the like —
  everything goes through ports.

### `{Name}Command.java` / `{Name}Query.java` — the input

```java
public record PlaceOrderCommand(
    CustomerId customerId,
    List<LineItem> items,
    Address shippingAddress
) {
    public PlaceOrderCommand {
        Objects.requireNonNull(customerId, "customerId required");
        if (items == null || items.isEmpty()) throw new IllegalArgumentException("items must not be empty");
        items = List.copyOf(items); // defensive copy for immutability
    }
}
```

- **`record`**, not `class`. Records guarantee immutability plus `equals`/`hashCode`.
- **Validation in the compact constructor.** Null checks, required fields, defensive copies of collections.
- **Domain types instead of primitives.** `CustomerId` instead of `String`, `Money` instead of `BigDecimal`.
- **Command versus Query** is a hard rule, not a style:
  - **Command:** changes state. Runs in a transaction. Usually ends with domain-event publication.
  - **Query:** reads only. No mutation, no events.
  - A use case that reads *and* writes is a command.
  - The split allows a later CQRS separation (read models on replicas, say) without refactoring the callers.

### `{Name}Result.java` — the output

```java
public record PlaceOrderResult(
    OrderId orderId,
    Instant placedAt,
    Money totalAmount
) {}
```

- **`record`**.
- **Lives in the same package** as the use case — not in a shared `dto/` folder.
- **Carries values, never identities.** Allowed: primitives, nested part records, value objects (shared kernel
  included: `Money`, `ProductId`), enriched domain models and read models (`Value` records from `domain/model` or
  `domain/readmodel`). Forbidden: anything that is an `AggregateRoot` or `Entity` — also transitively through part
  records and `List<T>`/`Optional<T>`/`Map<K,V>` (`DCA-USE-015`). Never `Order order` as a result field.
- **Part records are named by content** (`CartItemSummary`, `LineItemData`, `ProfileView`), never `*Result`;
  `*Result` is the top level only. Parts nest inside the result; a part shared by several use cases moves to
  `application/shared`.
- **Command results are small:** ids, status/outcome, what the caller needs for the next step. The view comes
  from a query or a read model. A command returning the whole read model is the documented exception (it saves a
  remote caller a round trip) — and then returns the read-model `Value`, not a parade of primitives.
- **Large aggregates hand out a snapshot** (`Value` in `domain/readmodel`, `Snapshot.from(aggregate)`); the
  snapshot *is* the result field, the use case does not flatten it a second time.
- **Who assembles the result:** the application layer, in order of effort — (a) a static factory `from(...)` on
  the result, parts with their own `from`; (b) when the projection needs several ports it is orchestration and
  belongs in the use-case body; (c) when it grows or several use cases need it, an `*Assembler` in the use-case
  folder or in `application/shared`. Never `*Mapper`, `*Converter` (`DCA-NAM-008`), never `*Helper`.
- **Anti-pattern:** the result has **the same fields as the aggregate** → questionable. Either the use case
  performs no meaningful transformation (then you may not need it), or the adapter should receive the aggregate's
  snapshot directly.
- Void use cases (`cancelOrder` without a return value) still return a `Result` record, possibly with a single
  confirmation field (`record CancelOrderResult(Instant cancelledAt) {}`). Avoids API breaks when fields are
  added later.

---

## 3. Decision guide: local versus shared output port

Output ports live either **in the use-case folder** (local) or in **`application/shared/`** (shared). This
decision is often made wrongly.

### Default: shared (`application/shared/`)

**Aggregate repositories and cross-use-case ports belong in `application/shared/`:**

- `OrderRepository` — used by `placeOrder`, `cancelOrder`, `getOrderById`, ...
- `CustomerDataPort` — cross-context read, used by several use cases
- `OrderEventPublisher` — event output, often used by several use cases
- `IdentityProvider`, `Clock`, `RandomGenerator` — generic infrastructure ports

```
application/
├── shared/
│   ├── OrderRepository.java       # extends Repository<Order, OrderId>
│   ├── CustomerDataPort.java      # extends OutputPort
│   └── OrderEventPublisher.java   # extends OutputPort
├── placeorder/
│   └── ...
└── cancelorder/
    └── ...
```

### Exception: a local port in the use-case folder

**Only in narrowly bounded cases:**

| Case | Example | Why local |
|---|---|---|
| Use-case-specific call to an external system | `placeorder/PaymentGatewayPort.java` | Only `placeOrder` needs payment authorisation; no other use case does |
| Specialised read projection | `getorderdashboard/OrderDashboardProjectionPort.java` | A specific query optimisation, not reusable |
| Use-case-local validator / external check | `registeruser/EmailDeliverabilityPort.java` | Only registration checks mailbox reachability |

```
application/
├── shared/
│   └── UserRepository.java
└── registeruser/
    ├── RegisterUserInputPort.java
    ├── RegisterUserUseCase.java
    ├── RegisterUserCommand.java
    ├── RegisterUserResult.java
    └── EmailDeliverabilityPort.java   # local -- used only here
```

### Decision rule

> **If a second caller is plausible → shared. Otherwise local.**

A wrong decision costs in both directions:

- **Wrongly shared:** `application/shared/` swells with unused ports → harder to navigate, unclear ownership.
- **Wrongly local:** a second use case duplicates the port (or imports across from a foreign use-case folder,
  which violates the rules). Refactoring is due as soon as it is shared.

**Tie-breaker:** when in doubt choose `shared/`. Moving shared → local is cheaper (only the one use case is
affected) than the other way round (several callers must be re-wired).

### Anti-pattern: per-use-case repository

When every use case has its own `*Repository` with only the methods *it* needs (`PlaceOrderOrderRepository` with
only `save`, `GetOrderByIdOrderRepository` with only `findById`), that is a smell. **Aggregate repositories are
per aggregate**, not per use case. Consolidate into one `OrderRepository` in `application/shared/`.

---

## 4. Adapter wiring: who calls what?

```
┌─────────────────────┐                  ┌──────────────────────┐
│ Incoming adapter    │                  │ Outgoing adapter     │
│ (controller,        │                  │ (repository impl,    │
│  event consumer)    │                  │  event publisher)    │
└──────────┬──────────┘                  └──────────▲───────────┘
           │ calls interface                        │ implements interface
           ▼                                        │
┌─────────────────────┐                  ┌──────────┴───────────┐
│ *InputPort          │ ─── uses ──────▶ │ OutputPort           │
│ (in application/    │                  │ (in application/     │
│  usecasename/)      │                  │  shared/ or local)   │
└──────────┬──────────┘                  └──────────────────────┘
           │ implements
           ▼
┌─────────────────────┐
│ *UseCase (impl)     │
│ calls output ports  │
└─────────────────────┘
```

**Concretely:**

- The controller injects **the interface** (`PlaceOrderInputPort`), not the implementation.
- The repository implementation implements **the interface** from `application/shared/`, never another one.
- The use-case implementation depends **on interfaces only** (input and output ports), never on concrete
  adapter classes.

See also [DTO Mapping Strategy](../../dca-scaffold/SKILL.md#dto-mapping-at-the-adapter-boundary) for how
request and response are mapped at the adapter edge.

---

## 5. Static rules

The rule suite (`dca-archunit` / `DomainCentric.ArchRules`, the same id in both languages; `/dca-bootstrap` wires
the test) checks the use-case pattern at these points. The review does not repeat them; it checks what they
cannot see.

| Rule | What it checks |
|---|---|
| `DCA-NAM-001`, `DCA-NAM-003` | Implementation ends with `UseCase` (or the configured suffix), interface with `InputPort` |
| `DCA-HEX-011` | Incoming adapters depend on the input-port interface, not on the use-case class |
| `DCA-USE-001` | The `InputPort`/`UseCase` base interface is not redeclared in the project |
| `DCA-USE-002`–`DCA-USE-007` | `*Command`/`*Query`/`*Result` are named so, live in `application/` and are immutable (`record`/`final`) |
| `DCA-USE-015` | No field, part record or generic argument of a `*Result` is an `AggregateRoot`/`Entity` (transitive) |
| `DCA-USE-009`, `DCA-USE-012` | Whoever saves an aggregate publishes its events and runs inside a transaction boundary |
| `DCA-USE-013` | No remote-capable output port inside a declaratively transactional use case (Java) |
| `DCA-USE-014`, `DCA-CYC-005` | One depth per context (flat or feature); no cycles between feature / use-case packages |
| `DCA-USE-016`, `DCA-USE-017` | No use case invokes another; the public surface is the input port |
| `DCA-HEX-002`, `DCA-LAY-*` | `application/` does not import from `adapter/`; no persistence or messaging frameworks in `application/` |
| `DCA-HEX-009`, `DCA-HEX-010`, `DCA-TAC-013/014/018/019` | Output ports are interfaces in `application/`, extend `Repository`/`Store`/`OutputPort`, never live in `domain/` |
| `DCA-HEX-012` | No `DomainService` in `adapter/incoming/` |
| `DCA-NAM-002` | Diagnostic only: a use case without an injectable stereotype |

Full list with selection and check: `dca-bootstrap/reference/archunit-rule-catalog.md`.

---

## 6. Common mistakes and their correction

| Mistake | Symptom | Correction |
|---|---|---|
| Use case has neither stereotype nor registration | `DCA-NAM-002` reports it, no adapter reaches it | `@Service` with the Spring preset; otherwise register it behind the input port in the configuration |
| Command mutates data | Setters, non-final fields, a plain class | Convert to a `record`, defensive copies in the compact constructor |
| Result contains an aggregate | `record PlaceOrderResult(Order order)` — also hidden in `List<Order>` or a part record | Reduce to values: `record PlaceOrderResult(OrderId orderId, Money total)`; for large aggregates deliver a snapshot (`Value` in `domain/readmodel`) |
| Command result carries the whole view | `SubmitDeliveryResult` with 14 string/decimal fields no controller reads | Shrink to `(sessionId, currentStep, status)`; the next page asks the query |
| Incoming adapter recalculates | `*PageViewModel` injects `TaxCalculator`/`CartTotalCalculator` to derive a value from the result | Put the value into the result or read model; the adapter reads and formats (`DCA-HEX-012`) |
| Use case has two public methods | `placeOrder()` + `placeOrderUrgent()` | Split into two use cases or parameterise through a command field |
| Folder is `place-order` or `placeOrder` | Compile error or convention drift | Rename to `placeorder` |
| Output port in the domain layer | `domain/port/OrderRepository.java` | Move to `application/shared/` (ports belong to the application layer) |
| `*UseCase` without a `*InputPort` interface | Adapter depends directly on the implementation | Introduce the `*InputPort` interface, re-wire the adapter |
| More than five output ports injected | "God use case" | Split the use case (different bounded use-case cuts) or introduce a domain service |
| Per-use-case repository | `PlaceOrderOrderRepository` with only `save` | Consolidate into `OrderRepository` in `application/shared/` |

---

## 6a. The same pattern in C# (.NET)

The use-case folder is built identically; only the spelling changes: `Application/PlaceOrder/` (or
`Application/{Feature}/PlaceOrder/`), ports with an `I` prefix and asynchronous, no framework attribute on the
implementation.

```csharp
public interface IPlaceOrderInputPort : IUseCase<PlaceOrderCommand, PlaceOrderResult> { }

public sealed record PlaceOrderCommand(Guid CustomerId, IReadOnlyList<LineItem> Items);

public sealed record PlaceOrderResult(Guid OrderId, DateTimeOffset PlacedAt)
{
    public static PlaceOrderResult From(Order order) => new(order.Id.Value, order.PlacedAt);
}

public sealed class PlaceOrderUseCase : IPlaceOrderInputPort
{
    private readonly IOrderRepository _orders;
    private readonly IDomainEventPublisher _events;
    private readonly ITransactionBoundary _transaction;

    public PlaceOrderUseCase(IOrderRepository orders, IDomainEventPublisher events, ITransactionBoundary transaction)
    { _orders = orders; _events = events; _transaction = transaction; }

    public Task<PlaceOrderResult> ExecuteAsync(PlaceOrderCommand cmd, CancellationToken ct = default) =>
        _transaction.InTransactionAsync(async innerCt =>
        {
            var order = Order.Place(new CustomerId(cmd.CustomerId), cmd.Items);
            await _orders.SaveAsync(order, innerCt);
            await _events.PublishAndClearEventsAsync(order, innerCt);
            return PlaceOrderResult.From(order);
        }, ct);
}
```

- **Registration** instead of component scan: `services.AddScoped<IPlaceOrderInputPort, PlaceOrderUseCase>()` in
  `Infrastructure/Add{Context}Context()`.
- **The transaction boundary** is a call (`ITransactionBoundary.InTransactionAsync`) or a decorator around
  `IUseCase<,>`, not an attribute; `DCA-NET-006` keeps EF Core / `System.Transactions` out of `Application/`.
  `DCA-USE-012` also checks in .NET that every entry path to `IRepository.SaveAsync`/`DeleteByIdAsync` or
  `IDomainEventPublisher` passes through an `InTransactionAsync` boundary (a static approximation) — the boundary
  is mandatory even without events, because a save may issue several statements; only `DCA-USE-013` is n/a in .NET.
- **Ports async, domain synchronous:** the aggregate call `order.Place(...)` does not block; `await` appears only
  at the ports.
- **Output ports** in `Application/Shared/` as `I*Repository : IRepository<T,TId>` or `I*Store : IStore`;
  `FindByIdAsync`/`SaveAsync` are inherited from the repository interface already.
- **Architecture tests** run against the Debug build (`dotnet test tests/*.ArchitectureTests`).

---

## 7. Related references

- [checklist.md](checklist.md) — per-layer audit checks (Application — Use Cases, Application — Output Ports)
- [naming-conventions.md](naming-conventions.md) — complete naming tables
- [archunit-rule-catalog.md](../../dca-bootstrap/reference/archunit-rule-catalog.md) — the static rules that enforce the pattern
- [DTO Mapping Strategy](../../dca-scaffold/SKILL.md#dto-mapping-at-the-adapter-boundary) — how adapters map to commands and results
- [Module Selection Guide](../../dca-bootstrap/reference/module-selection-guide.md) — which rule modules enforce the use-case pattern
