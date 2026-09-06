# DCA Naming Conventions Reference

Quick lookup for the review skill. Default DCA conventions; if a project consistently uses
different names (and the team has decided so), respect them — don't flag consistent
deviations as findings.

## Application layer

| Pattern | Purpose | Example |
|---|---|---|
| `*InputPort` | use-case interface (DCA original) | `PlaceOrderInputPort` |
| `*UseCase` | use-case interface (Hombergs-style) | `PlaceOrderUseCase` |
| `*UseCase` | use-case impl (DCA original) | `PlaceOrderUseCase` |
| `*ApplicationService` | use-case impl (Hombergs-style) | `PlaceOrderApplicationService` |
| `*Service` | use-case impl (Spring tradition) | `PlaceOrderService` |
| `*Command` | write input | `PlaceOrderCommand` |
| `*Query` | read input | `GetOrderByIdQuery` |
| `*Result` | use-case output (application layer) | `PlaceOrderResult` |
| `*Repository` | output port for aggregate persistence (Aggregate Roots) | `OrderRepository` |
| `*Store` | output port for operational data (Value Objects, events) | `LoginProtectionStore`, `AuditLogStore` |
| `*DataPort` | output port for cross-context data fetch | `ArticleDataPort` |
| `*EventPublisher` | output port for integration events | `OrderEventPublisher` |

**Use-case folder names:** lowercase, no separator (`placeorder`, `getorderbyid`, not `placeOrder` or `place-order`).

**Feature folder names** (optional group of use cases, `application/{feature}/{usecasename}/`): lowercase terms of
the ubiquitous language (`ordering`, `cartrecovery`, `checkoutcompletion`) — never technical buckets (`commands`,
`queries`, `handlers`, `services`, `utils`) and never delivery mechanisms (`web`, `api`). A context is flat or
grouped, never both.

## Domain layer

| Pattern | Purpose |
|---|---|
| `*` (PascalCase) | aggregate root, e.g. `Order`, `Cart` |
| `*Id` | strongly-typed identifier, e.g. `OrderId` |
| Past-tense | domain event, e.g. `OrderPlaced`, `CartCleared` |
| Past-tense + `Event` | integration event (optional convention), e.g. `OrderPlacedEvent` |
| `*Service` (in `domain/service/`) | domain service |
| `*Factory` | factory for complex aggregate creation |
| `*Specification` | business rule object |

**Avoid:** `*Manager`, `*Helper`, `*Util`, `*Handler` in the domain — these are vague names.

**Packages:** package by domain concept (`domain/model/`, `domain/event/`) — never technical buckets like `entities/`, `valueobjects/`, `helpers/`, `util/`.

## Adapter layer

| Pattern | Purpose | Location |
|---|---|---|
| `*Resource` | REST controller (DCA convention, ADR-020) | `adapter/incoming/api/` |
| `*Controller` | MVC view controller | `adapter/incoming/web/` |
| `*EventConsumer` | integration event listener | `adapter/incoming/event/` |
| `*Response` | adapter-layer DTO (e.g. JSON shape) | `adapter/incoming/...` |
| `*ViewModel` | MVC view model | `adapter/incoming/web/` |
| `*Dto` | data transfer object | `adapter/...` (NEVER in domain/application) |
| `*Converter` | mapping logic between adapter and application | `adapter/...` |
| `InMemory*Repository` | in-memory repository impl | `adapter/outgoing/persistence/` |
| `Jpa*Repository`, `Jdbc*Repository` | JPA/JDBC repository impl | `adapter/outgoing/persistence/` |
| `*EventPublisher` (impl) | integration event publisher impl | `adapter/outgoing/event/` |
| `*EventTranslator`, `*ACL` | anti-corruption layer | `adapter/.../acl/` |

## Markers (sharedkernel)

| Marker | Role |
|---|---|
| `AggregateRoot<T, ID>` | aggregate root marker |
| `BaseAggregateRoot<T, ID>` | optional base class with domain-events list |
| `Entity<T, ID>` | non-root entity marker |
| `Value` | value object marker |
| `Id` | identifier marker |
| `Repository<T, ID>` | aggregate repository output port |
| `Store` | operational-data output port (for Value Objects, events) |
| `OutputPort` | generic output port marker |
| `InputPort` | generic input port marker |
| `UseCase<I, O>` | use-case input port marker |
| `DomainEvent` | domain event marker |
| `IntegrationEvent` | cross-context event marker — separate hierarchy, does *not* extend `DomainEvent`; version via `@IntegrationEventType` |
| `DomainService` | domain service marker |
| `Factory` | factory marker |
| `Specification` | specification marker |
| `@BoundedContext("name")` | strategic marker on `package-info.java` |
| `@SharedKernel` | strategic marker on sharedkernel `package-info.java` |
| `@OpenHostService` | strategic marker for cross-context-callable service |

## Layer folders

| DCA default | Hombergs-style alternative |
|---|---|
| `adapter/incoming/` | `adapter/in/` |
| `adapter/outgoing/` | `adapter/out/` |
| `application/{usecasename}/` — or `application/{feature}/{usecasename}/` once grouped | `application/service/` (flat) + `application/port/in/` + `application/port/out/` |
| `sharedkernel/` | `shared/`, `common/`, `core/` |
