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
- [ ] No Spring/JPA annotations (`@Entity`, `@Component`, `@Service`, `@Table`)
- [ ] No setters
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

- [ ] `@Service` (and `@Transactional` for write use cases)
- [ ] `@Transactional` only in the application layer — never on domain classes or incoming adapters (outgoing persistence adapters are the allowed exception)
- [ ] No remote-capable output port (another context's API, payment provider, mail gateway) called inside a `@Transactional` use case — such use cases fetch remote data first and wrap save + publish in `UnitOfWork.run(...)` (`DCA-USE-013`)
- [ ] Constructor injection only (no `@Autowired` field injection)
- [ ] Implements the input port
- [ ] **Anti-pattern flag — God use case:** more than 5 output ports → consider splitting
- [ ] **Anti-pattern flag — Leaking infrastructure:** depends on JDBC/JPA/Kafka classes directly (must go through ports)
- [ ] Uses domain methods, not raw field access (e.g. `order.cancel(reason)`, not `order.setStatus(CANCELLED)`)
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
- [ ] Doesn't expose domain entities directly (use IDs and primitives)
- [ ] **Anti-pattern flag:** if Result has same fields as the aggregate → consider whether the use case is doing meaningful transformation

---

## Application — Output Ports (`application/shared/` oder `application/{usecasename}/`)

### Basics

- [ ] Interfaces only (no implementations)
- [ ] Extends `Repository<T, ID>`, `Store`, `OutputPort`, or domain-specific marker (`EventPublisher`, `IdentityProvider`)
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

- [ ] **Anti-pattern flag — Anemic port:** generic, domain-meaningless name like `*DataAccessor`, `*PersistenceHandler`, `*Manager`, `*Gateway` (when not a real gateway pattern).
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

See [use-case-pattern.md §3](use-case-pattern.md#3-decision-guide-lokaler-vs-shared-output-port) for the full decision guide.

### Repository vs. Store correctness

DCA distinguishes Repository (for Aggregate Roots) from Store (for operational data). Common mistakes:

- [ ] **Anti-pattern flag — Repository for non-aggregate:** a `*Repository` whose stored type is a Value Object or record. Should be a `*Store` instead.
  - Symptom: the stored type doesn't implement `AggregateRoot` and has no own identity-based lifecycle.
  - Fix: rename to `*Store`, change marker from `Repository<T,ID>` to `Store`, replace `findById/save` with `record/count/exists`.

- [ ] **Anti-pattern flag — Store with `findById` or `save`:** a `*Store` interface using Repository semantics.
  - Symptom: methods named `findById`, `save`, `delete`.
  - Fix: if the stored type has identity → rename to `*Repository` and ensure stored type extends `AggregateRoot`. Otherwise rewrite methods to `record(...)`, `count(...)`, `exists(...)`, `reset(...)`.

- [ ] **Naming clarity:** the port name should tell the reader without opening the file whether it manages an aggregate (`*Repository`) or records operational data (`*Store`).

---

## Adapter — Incoming (`adapter/incoming/` or `adapter/in/`)

### REST resources / controllers

- [ ] Naming matches project convention (`*Resource` for REST, `*Controller` for MVC)
- [ ] Depends on the input port interface, not the implementation
- [ ] Maps `*Result` → `*Response` (separate adapter-layer DTO)
- [ ] No domain types in the public method signatures (no `Order` returned by REST)
- [ ] Per-use-case methods, not "kitchen sink" controllers

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

### Integration event publishers

- [ ] In `adapter/outgoing/event/`
- [ ] Translate domain events → integration events
- [ ] **Anti-pattern flag:** publishing the domain event directly to other contexts → use an IntegrationEvent record (with version field)

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

### Package structure

- [ ] Packages named by domain concept, not technical role
- [ ] **Anti-pattern flag:** technical bucket packages — `entities/`, `valueobjects/`, `helpers/`, `util/`

### DTOs

- [ ] Live only in `adapter/`
- [ ] **Anti-pattern flag:** `*Dto` found in `domain/` or `application/`

### Lombok usage

- [ ] If project uses Lombok: prefer `@Value`/`@RequiredArgsConstructor` over hand-written boilerplate
- [ ] Records are valid alternatives — both styles allowed
- [ ] **Anti-pattern flag:** `@Data` on domain classes (mutable, generates setters)
