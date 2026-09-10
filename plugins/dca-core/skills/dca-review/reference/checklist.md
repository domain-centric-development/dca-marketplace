# DCA Review Checklist (per layer)

Apply only the checks for each file's layer.

---

## Domain — Model (`domain/model/`)

### Aggregate Roots

- [ ] Implements `AggregateRoot<T, ID>` (or `extends BaseAggregateRoot`)
- [ ] Has a private constructor + static factory method (`create(...)`, `from(...)`)
- [ ] Factory method emits a `*Created` domain event
- [ ] Mutators are intent-revealing methods, not setters (`markCompleted()`, not `setStatus(COMPLETED)`)
- [ ] Each mutator validates invariants OR delegates to a Specification
- [ ] Aggregate references other aggregates by ID, not direct field
- [ ] No Spring/JPA annotations (`@Entity`, `@Component`, `@Service`, `@Table`); C#: no EF Core/ASP.NET attributes, no `async` member (the domain stays synchronous)
- [ ] No setters (C#: no public `set`/`init` on state that carries an invariant)
- [ ] `domainEvents()` and `clearDomainEvents()` exposed
- [ ] **Anti-pattern flag:** if aggregate has only getters/setters → anemic

### Entities (non-root)

- [ ] Implements `Entity<T, ID>`
- [ ] Has an `id()` accessor
- [ ] Constructor is package-private or protected (only the aggregate creates it)
- [ ] No public mutators except via the aggregate
- [ ] No Spring/JPA annotations on the domain class

### Value Objects

- [ ] Implements `Value` (or is a record — both are valid DCA forms)
- [ ] All fields are `final`
- [ ] No setters
- [ ] No mutating methods (every "change" returns a new instance)
- [ ] Correct `equals`/`hashCode` (records do this automatically)
- [ ] Validates input in the constructor (records: in compact canonical constructor)
- [ ] **Anti-pattern flag:** if value object has only data and no behavior → consider whether it should just be a record without the marker

### IDs

- [ ] Records (recommended) or final classes
- [ ] Implements `Id`
- [ ] Has `value()` accessor
- [ ] Validates non-null in compact constructor
- [ ] Strongly-typed wrapper — prevents accidentally passing a `CustomerId` where an `OrderId` is expected

---

## Domain — Events (`domain/event/`)

- [ ] Past-tense name (`OrderPlaced`, not `PlaceOrder`)
- [ ] Is a `record`
- [ ] Implements `DomainEvent`
- [ ] Has a timestamp field (`Instant occurredAt` or similar)
- [ ] Has the aggregate ID (`OrderId aggregateId` or similar)
- [ ] If it's an `IntegrationEvent`, also has a `version` field
- [ ] No Spring annotations (`@Component`, `@EventListener`)
- [ ] In `domain/event/` (or its sub-package)

---

## Domain — Services (`domain/service/`)

- [ ] Implements `DomainService`
- [ ] Stateless (only `final` fields)
- [ ] Operates on multiple aggregates that no single aggregate owns
- [ ] No Spring annotations
- [ ] **Anti-pattern flag:** if domain service does CRUD orchestration → likely belongs in application layer instead

---

## Application — Use Cases (`application/{usecasename}/`)

### Input port interface

- [ ] Extends `UseCase<INPUT, OUTPUT>`
- [ ] Single method `execute(INPUT)` returning `OUTPUT`
- [ ] Naming matches project convention (e.g. `PlaceOrderInputPort` or `PlaceOrderUseCase`)

### Implementation class

- [ ] `@Service` (and `@Transactional` for write use cases); C#: plain class registered behind its input port in `Add{Context}Context()`, no framework attribute
- [ ] `@Transactional` only in the application layer — never on domain classes or incoming adapters (outgoing persistence adapters are the allowed exception); C#: the boundary is `ITransactionBoundary.InTransactionAsync` or a decorator — EF Core, `System.Data`, `System.Transactions` stay out of `Application/` (`DCA-NET-006`)
- [ ] No remote-capable output port (another context's API, payment provider, mail gateway) called inside a `@Transactional` use case — such use cases fetch remote data first and wrap save + publish in `TransactionBoundary.inTransaction(...)` (`DCA-USE-013`); C#: remote reads before `InTransactionAsync`, never inside
- [ ] C#: ports are async (`Task<TOut> ExecuteAsync(TIn, CancellationToken)`), the domain they call is not — no `.Result`/`.Wait()` bridging
- [ ] Constructor injection only (no `@Autowired` field injection)
- [ ] Implements the input port
- [ ] **Cohesion review prompt:** more than five output ports prompts a responsibility review; it is not a numerical violation threshold
- [ ] **Anti-pattern flag — Leaking infrastructure:** depends on JDBC/JPA/Kafka classes directly (must go through ports)
- [ ] Uses domain methods, not raw field access (e.g. `order.cancel(reason)`, not `order.setStatus(CANCELLED)`)
- [ ] Order inside the use case: `save`, then `publishAndClearEvents` — never publish before the save; the publisher dispatches first and clears afterwards (clear = acknowledgement)
- [ ] Integration events go through a transactional outbox registered *inside* the transaction and released after commit; consumers idempotent
- [ ] Publishes domain events after persistence
- [ ] Maps domain output to a `*Result` record

### Command / Query

- [ ] Records, not classes
- [ ] All fields immutable
- [ ] Validates required fields in compact constructor
- [ ] Command for writes, Query for reads
- [ ] Lives in the same package as the use case

### Result

- [ ] Record
- [ ] Lives in the same package as the use case
- [ ] Carries values, never identities: primitives, nested part records, value objects (shared kernel included), enriched domain models and read models (`Value`) — no field, part record or generic argument (`List<T>`, `Optional<T>`, `Map<K,V>`) assignable to `AggregateRoot` or `Entity` (`DCA-USE-015`, checked transitively)
- [ ] Part records are named by content (`CartItemSummary`, `LineItemData`, `ProfileView`) and nested in the result; `*Result` is the top level only; a part shared by several use cases lives in `application/shared`
- [ ] Command results are small — ids, status/outcome, what the caller needs next; the view comes from a query or read model. A command returning a whole read model is the documented round-trip exception and then returns the read-model `Value`, never a parade of primitives
- [ ] Large aggregates hand out a snapshot (`Value` in `domain/readmodel`, `Snapshot.from(aggregate)`) that *is* the result field — no second flattening in the use case
- [ ] Assembled in the application layer, in order of effort: static `from(...)` on the result → use-case body when several ports feed the projection → `*Assembler` in the use-case folder or `application/shared` when it grows or is shared. Never `*Mapper`/`*Converter`/`*Helper` in `application/`
- [ ] **Anti-pattern flag:** if Result has same fields as the aggregate → consider whether the use case is doing meaningful transformation

---

## Application — Output Ports (`application/shared/` oder `application/{usecasename}/`)

### Basics

- [ ] Interfaces only (no implementations)
- [ ] Extends `Repository<T, ID>`, `Store`, `DomainEventPublisher`/`IntegrationEventPublisher`, or plain `OutputPort` for a project-specific port (`IdentityProvider`, `Clock`) — these are ports, not markers
- [ ] Lives in the application layer — never in `domain/`
- [ ] **Anti-pattern flag — Leaky port (technology in name):** name reveals technology (`OrderJpaRepository`, `KafkaOrderEventPublisher` as the *port* — not the impl). The port should be technology-agnostic; the *implementation* in `adapter/outgoing/` carries the tech prefix.
- [ ] **Anti-pattern flag — Per-use-case repository:** if every use case has its own bespoke `*Repository` instead of reusing one per aggregate, consolidate into a shared `*Repository` in `application/shared/`.

### Output Port Granularity

The shape of the port is as important as its existence. Run these checks on every port:

- [ ] **Cohesion check:** all methods on the port serve the same use case or aggregate concern. A port mixing `findById`, `sendNotification`, and `calculateTax` is three ports masquerading as one.

- [ ] **Anti-pattern flag — God port:** more than ~5 methods on a single port, or methods used by disjoint sets of use cases.
  - Symptom: `OrderPort` has `findById`, `save`, `delete`, `findByCustomer`, `searchByDateRange`, `exportToCsv`, `archive`, `restore`.
  - Fix: split by responsibility — `OrderRepository` (findById, save), `OrderSearchPort` (findByCustomer, searchByDateRange), `OrderArchivePort` (archive, restore, exportToCsv).
  - Why it matters: forces every adapter impl to implement methods it doesn't need; couples unrelated use cases together.

- [ ] **Anti-pattern flag — Anemic port:** generic, domain-meaningless name like `*DataAccessor`, `*PersistenceHandler`, `*Gateway` (when not a real gateway pattern).
  - Symptom: `OrderDataAccessor` instead of `OrderRepository`; `CustomerPersistenceHandler` instead of `CustomerRepository`.
  - Fix: rename using DCA vocabulary — `*Repository` (aggregates), `*Store` (operational data), `*DataPort` (cross-context read), `*EventPublisher` (events).
  - Why it matters: anemic names erase intent — a reader can't tell if it manages an aggregate, records events, or fetches from another context.

- [ ] **Anti-pattern flag — Leaky port (technology in signature):** method signatures expose adapter-side types.
  - Symptom: `List<ResultSet> query(String sql)`, `KafkaRecord publish(...)`, `JpaSpecification<Order> buildSpec(...)`, `void save(OrderEntity entity)`.
  - Fix: signatures use domain types only — `List<Order> findActiveOrders(CustomerId id)`, `void publish(OrderPlacedEvent event)`, `void save(Order order)`.
  - Why it matters: a leaky signature couples the application layer to the persistence/messaging technology and defeats the purpose of the port.

- [ ] **Anti-pattern flag — Bidirectional port confusion:** a port serving both input (called by adapter) and output (called by use case) roles.
  - Symptom: a single `OrderPort` interface with both `placeOrder(cmd)` (input) and `findById(id)` (output).
  - Fix: split into `PlaceOrderInputPort` (in `application/{usecasename}/`) and `OrderRepository` (in `application/shared/`).
  - Why it matters: input and output ports have opposite dependency directions; mixing them breaks the dependency rule.

### Port Location (shared vs local)

- [ ] **Aggregate repositories** (`*Repository extends Repository<Aggregate, Id>`) live in `application/shared/`. Always.
- [ ] **Cross-cutting infrastructure ports** (`Clock`, `IdentityProvider`, `EventPublisher` for a context's events) live in `application/shared/`.
- [ ] **Use-case-specific external calls** with no plausible second caller may live in `application/{usecasename}/` (e.g. `placeorder/PaymentGatewayPort.java`).
- [ ] **Anti-pattern flag — Premature local port:** a port lives in `{usecasename}/` but is imported by another use case → must move to `application/shared/` (cross-use-case imports inside `application/` are a smell).
- [ ] **Anti-pattern flag — Over-shared port:** a port lives in `application/shared/` but only one use case imports it AND no plausible second caller exists → consider moving to the use case's folder.
- [ ] **Tie-breaker rule:** when uncertain, default to `application/shared/` — moving shared→local is cheap, moving local→shared is costly.

### Identity and authorization (the identity port)

- [ ] The identity port (`IdentityProvider`) is an `OutputPort` in `application/shared/` (shared kernel or one context), implemented in the authenticating context's `adapter/outgoing/security/`. Never a domain type, never a marker.
- [ ] A use case acting on a caller's resource takes the caller **as a command/query field** (`GetCartByIdQuery(cartId, customerId)`). The incoming adapter fills it from the port; the use case does not call the identity port to learn on whose behalf it runs.
  - Symptom: `identityProvider.getCurrentIdentity()` inside a `*UseCase`; or a command that names a resource id but not whose it is while sibling use cases in the same context carry the caller.
- [ ] The repository is asked a **scoped question** (`findByIdForCustomer`) — not `findById` followed by an ownership `if`.
- [ ] A **claims-only gate** (role on the token) may sit in the incoming adapter. Anything that needs the loaded resource must not.
- [ ] The **domain never sees the caller**: no `User`/identity parameter on aggregate methods, no role check in domain code, no security-framework type in `domain/`.
- [ ] The authentication filter **enriches, never gates** — no blanket `authenticated()` rule guards a use case.
- [ ] A use case with no caller (event consumer, scheduled job) is unscoped **and says so** in a comment.
- [ ] Refusals are rendered in the adapter (`403` vs `404` is a protocol decision); the use case returns "nothing here for you".

See [use-case-pattern.md §3](use-case-pattern.md#3-decision-guide-lokaler-vs-shared-output-port) for the full decision guide.

### Repository vs. Store correctness

DCA distinguishes Repository (for Aggregate Roots) from Store (for operational data). Common mistakes:

- [ ] **Anti-pattern flag — Repository for non-aggregate:** a `*Repository` whose stored type is a Value Object or record. Should be a `*Store` instead.
  - Symptom: the stored type doesn't implement `AggregateRoot` and has no own identity-based lifecycle.
  - Fix: rename to `*Store`, change marker from `Repository<T,ID>` to `Store`, choose operational methods such as `record/count/exists`; a lookup named `findById` is allowed.

- [ ] **Anti-pattern flag — Store with aggregate persistence methods (`save`/`delete`):** a `*Store` interface using Repository semantics.
  - Symptom: methods named `save`, `delete`, `deleteById`; `findById` alone is valid for a Store.
  - Fix: if the stored type has identity → rename to `*Repository` and ensure stored type extends `AggregateRoot`. Otherwise rewrite methods to `record(...)`, `count(...)`, `exists(...)`, `reset(...)`.

- [ ] **Naming clarity:** the port name should tell the reader without opening the file whether it manages an aggregate (`*Repository`) or records operational data (`*Store`).

---

## Adapter — Incoming (`adapter/incoming/` or `adapter/in/`)

### REST resources / controllers

- [ ] Naming matches project convention (`*Resource` for REST, `*Controller` for MVC)
- [ ] Depends on the input port interface, not the implementation
- [ ] Maps `*Result` → `*Response` (separate adapter-layer DTO)
- [ ] No domain types in the public method signatures (no `Order` returned by REST)
- [ ] Derives no business facts: reads and formats what the `*Result` delivers. Calling the own, parameterless queries of a delivered value or read model (`lineTotal()`, `isValidForCheckout()`) is reading; combining values from several sources into a new fact, or needing a domain service to derive one, means the result is too poor — move the value into the result or read model
- [ ] Obtains no domain collaborator: no `DomainService` injected or invoked (`DCA-HEX-012`); the use case owns that collaboration and puts its outcome into the result
- [ ] Constructs no domain object (aggregate, entity, domain value) and triggers no behaviour with side effects — raw request data goes into the `Command`/`Query`, the use case builds the domain types
- [ ] Per-use-case methods, not "kitchen sink" controllers
- [ ] No state-changing use case behind `@GetMapping` — writes use `POST`/`PUT`/`DELETE`; links never create sessions, carts or orders
- [ ] Every state-changing browser form carries the CSRF token; an API exempt from CSRF authenticates by `Authorization: Bearer` only and never reads or sets cookies

### Event consumers

- [ ] Live in `adapter/incoming/event/` (DCA convention)
- [ ] Listen to integration events from other contexts
- [ ] Translate via Anti-Corruption Layer (`*EventTranslator` or `*ACL`) when needed

---

## Adapter — Outgoing (`adapter/outgoing/` or `adapter/out/`)

### Repository implementations

- [ ] Class name is implementation-revealing (`InMemoryOrderRepository`, `JpaOrderRepository`)
- [ ] In `adapter/outgoing/persistence/`
- [ ] Implements the output port from `application/shared/`
- [ ] No business logic — only persistence
- [ ] Mapping, construction and reconstitution of domain objects is allowed and expected here (`reconstitute` factories, row → aggregate); it restores state and makes no new business decision

### Integration event publishers

- [ ] In `adapter/outgoing/event/`
- [ ] Translate domain events → integration events
- [ ] **Anti-pattern flag:** publishing the domain event directly to other contexts → use an IntegrationEvent contract (schema version in IntegrationEventType metadata, business version allowed)

---

## Cross-cutting

### Cross-context imports

- [ ] No file in `contextA/...` imports `contextB/domain/...`
- [ ] No file in `contextA/application/...` imports `contextB/application/...`
- [ ] Cross-context calls go via `contextB/api/` (Open Host Service) or events
- [ ] **Anti-pattern flag:** finding a `contextB.domain.*` import in `contextA/...`

### Spring placement

- [ ] `@Service`, `@Component`, `@Repository`, `@RestController`, `@Controller` only in `adapter/` or `application/`
- [ ] **Never** on `domain/` classes
- [ ] **Never** on `*Command`, `*Query`, `*Result`, `*DomainEvent`, `*IntegrationEvent`

### Framework placement (.NET)

- [ ] `[ApiController]`, `Controller`, `[Route]`, EF Core types only in `Adapter/` or `Infrastructure/`; DI registration in `Infrastructure/`
- [ ] **Never** in `Domain/` or on `*Command`, `*Query`, `*Result`, events
- [ ] Architecture tests run against a **Debug** build — an optimized build hides async state machines from ArchUnitNET, so a green Release run proves nothing

### Package structure

- [ ] Packages named by domain concept, not technical role
- [ ] **Anti-pattern flag:** technical bucket packages — `entities/`, `valueobjects/`, `helpers/`, `util/`
- [ ] Use cases of one context are either all flat (`application/{usecase}/`) or all grouped into features
      (`application/{feature}/{usecase}/`) — never both (`DCA-USE-014`); no use case directly in `application/`,
      none nested deeper than a feature
- [ ] Feature names are lowercase terms of the ubiquitous language (`cartrecovery`, `checkoutcompletion`)
- [ ] **Anti-pattern flag — technical bucket as feature:** `commands/`, `queries/`, `handlers/`, `services/`,
      `web/`, `api/` directly below `application/`
- [ ] **Anti-pattern flag — vertical slice disguised as feature:** `{context}/{feature}/{domain,application,adapter}`
      — a layer below the feature makes it a module; either it is a bounded context or the slice must go
- [ ] No `application/{feature}/shared/` — repositories and stores stay in the context-wide `application/shared/`
- [ ] The domain is not mirrored by feature (no `domain/{feature}/`); a feature owns no aggregate
- [ ] Feature (or, in a flat context, use-case) packages form no dependency cycle (`DCA-CYC-005`); a
      one-directional dependency between two features is acceptable
- [ ] Incoming adapters that mirror features keep the protocol first: `adapter/incoming/web/{feature}/`, never
      `adapter/incoming/{feature}/web/`

### DTOs

- [ ] Live only in `adapter/`
- [ ] **Anti-pattern flag:** `*Dto` found in `domain/` or `application/`

### Lombok usage (Java)

- [ ] If project uses Lombok: prefer `@Value`/`@RequiredArgsConstructor` over hand-written boilerplate
- [ ] Records are valid alternatives — both styles allowed
- [ ] **Anti-pattern flag:** `@Data` on domain classes (mutable, generates setters)

### Records (C#)

- [ ] `sealed record` for commands, queries, results, events; `readonly record struct` for ids and small values
- [ ] **Anti-pattern flag:** a `record` with `{ get; set; }` or `init` on domain state that carries an invariant — a record spelled mutable is a class with setters

### Operation boundaries and ACL evidence

Ordinary use cases do not invoke other use cases, whether directly, through an
input port, or through an application helper. Shared collaborators that do not call
operations remain valid. `DCA-USE-016` follows dependencies within the module's
application layer and reports `Caller -> Target [via Helper]`. Explicit coordination
uses a caller-side exception, for example
`dca.rule.DCA-USE-016.ignore=^com\.example\.module\.application\.coordinate\.CoordinatorUseCase -> `.
This permits the coordinator to invoke operations; it does not permit an operation
to invoke the coordinator, and `DCA-CYC-005` still detects coordination cycles,
including two operations inside the same feature. No coordinator marker is implied.
When a reliable exception cannot be expressed, use WARN with a recorded reason and
review the coordinator's transaction boundaries and partial-failure semantics manually.
Reflection, container lookups and calls through interfaces outside the InputPort
hierarchy also require manual review.

The input port describes the complete effective public instance surface (`DCA-USE-017`).
Declared and inherited business methods, unrelated-interface methods and public
properties/getters/setters must be in the input-port contract. Constructors, Object
members and compiler-generated members are exempt; a property accessor is not exempt
merely because it has a special runtime name. Ordinary, inherited and explicit
input-port implementations are valid. In .NET, `DCA-NET-003` separately validates
`IUseCase<TIn,TOut>.ExecuteAsync(input, CancellationToken)` returning `Task<T>` through
the interface map; it does not count declared public methods.

For every declared ACL interaction, the matching adapter must contain a class that
uses that upstream's channel contract and the declaring context's own domain or
application model (`DCA-MAP-008`). Two translators for different upstreams may share
an adapter package. Evidence for one upstream does not satisfy another interaction.
This identifies a structural translation site, without proving translation quality.

- [ ] D08: shared behavior changes include counterpart implementation and specification revision/scenarios; event JSON stays compatible.
- [ ] Past-tense names are reviewed as language (`Sent` is valid), never enforced by an `ed` suffix.
