# DCA ArchUnit Rule Catalog

Every rule installed by `dca-bootstrap`, why it exists, and what it forbids.

Rules are grouped by the test class that hosts them. Test classes correspond to the
module-selection options in the bootstrap workflow.

---

## Module: PackageCyclesArchUnitTest (mandatory)

| # | Rule | Forbids | Why |
|---|---|---|---|
| 1 | Domain-model packages must be cycle-free | A→B→A dependencies between domain-model slices | Acyclic Dependencies Principle. Cycles signal accidental coupling. |
| 2 | Application packages must be cycle-free | A→B→A between use-case slices | Use cases should be independent vertical slices. |
| 3 | Outgoing-adapter packages must be cycle-free | A→B→A between persistence/external adapters | Adapters are leaves of the dependency graph. |
| 4 | Incoming-adapter packages must be cycle-free | A→B→A between controllers/event consumers | Same. |
| 5 | Feature (or use-case) packages inside one module's application layer must be cycle-free (`DCA-CYC-005`) | A→B→A between the packages directly below `application/` — features in a grouped context, use cases in a flat one; `application/shared` is not a slice | A cycle between two features means the grouping does not carry its weight; a one-directional dependency is fine. Features are optional and the rule infers nothing about contexts or aggregates. |

---

## Module: HexagonalArchitectureArchUnitTest (recommended)

| # | Rule | Forbids | Why |
|---|---|---|---|
| 1 | Domain must not access adapters | Any `domain.*` class referring to `adapter.*` | Ports & adapters: domain talks to ports, adapters implement ports. |
| 2 | Application must not access adapters | Any `application.*` referring to `adapter.*` | Same. |
| 3 | Incoming adapters must not depend on infrastructure impls | Controllers using JPA classes directly etc. | Adapters use ports, not concrete infra. |
| 4 | Outgoing adapters must not depend on infrastructure impls | (same) | (same) |
| 5 | Incoming adapters must not depend on outgoing adapters | A controller using a `JdbcRepository` directly | Both are adapters; communication goes through ports. Exception: event consumers may publish events. |
| 5a | Controllers/Resources must not access repositories | `*Controller`/`*Resource` depending on any `Repository` type | Incoming web adapters drive the application through input ports only — direct repository access bypasses transactions, authorization, orchestration. |
| 6 | Incoming adapters must only access their own bounded context | A `product.web` controller calling `cart` use cases directly | Cross-context calls go via Open Host Service or events. |
| 7 | Repository implementations must reside in `adapter.outgoing` | `*Repository` classes outside that package | Naming and location must match. |
| 8 | Output ports in `application.shared` must extend `OutputPort` | A `*Repository` interface that doesn't extend the marker | Architectural traceability — every output dependency is explicit. |
| 9 | Output ports must not reside in `domain.*` | A `Repository`/`Store`/`OutputPort`-assignable interface declared in `domain.model` next to the aggregate instead of `application/shared/` | Rule 8 only scopes `application.shared` and passes silently when the port isn't there at all — this rule closes that gap so a misplaced port fails loudly instead of being missed. |
| 10 | Incoming adapters must depend on input ports, not on use case classes | A controller or resource injecting `CreateOrderUseCase` instead of `CreateOrderInputPort` | The port is what the adapter is supposed to drive. Injecting the implementation couples the adapter to one realisation, defeats the Dependency Inversion Principle the port exists for, and makes the adapter untestable without the real use case and everything it depends on. Rule 5a stops an adapter at the repository; this one stops it one step earlier. |
| 11 | Incoming adapters must not depend on domain services (`DCA-HEX-012`) | A controller, view model or event consumer injecting or calling a `DomainService` (`CheckoutStepValidator`, `TaxCalculator`) | An incoming adapter translates external input, calls an input port and formats its result. Injecting or invoking a domain service bypasses the application boundary; the use case owns that collaboration and puts its outcome into the result. Outgoing adapters are outside this rule — repositories construct and reconstitute domain objects while implementing output ports. |

---

## Module: LayeredArchitectureArchUnitTest (recommended)

| # | Rule | Forbids | Why |
|---|---|---|---|
| 1 | Domain must not depend on infrastructure | `domain.*` referring to Spring/JPA/etc. | Domain stays framework-independent. |
| 2 | Application must not depend on infrastructure impls | (same for application layer) | DIP. |
| 3 | `sharedkernel.marker.port.out` must contain only interfaces | A class in that package | Ports are contracts, not implementations. |
| 4 | `@Transactional` only in the application layer | `@Transactional` on domain classes or incoming adapters | The use case owns the unit of work. Documented exception: outgoing persistence adapters (multi-statement atomicity; joins the caller's transaction via REQUIRED propagation). |

---

## Module: OnionArchitectureArchUnitTest (recommended)

| # | Rule | Forbids | Why |
|---|---|---|---|
| 1 | Domain must not access application services | `domain.*` referring to `application.*` | Domain is the innermost layer. |
| 2 | Domain stays framework-independent | Domain depending on anything outside the allowlist (`java..`, `lombok..`, `org.apache.commons.lang3..`, `org.apache.commons.collections4`, `org.jspecify.annotations..`, plus other domain packages) | DIP — dependencies point inward. |
| 3 | Domain models must not have Spring/JPA annotations | `@Component`, `@Service`, `@Entity`, `@Table` on domain classes | Same. |

---

## Module: NamingConventionsArchUnitTest (recommended)

| # | Rule | Forbids |
|---|---|---|
| 1 | Use case impls must end with `UseCase` | `BlaService` implementing UseCase marker |
| 2 | `*UseCase` classes must be `@Service`-annotated | Plain classes claiming use-case status |
| 3 | InputPort interfaces must end with `InputPort` | Misnamed input contracts |
| 4 | Repository interfaces must end with `Repository` in `application.*` | `BlaStore` interfaces |
| 5 | `@Controller` classes must end with `Controller` | Misnamed view controllers |
| 6 | `@RestController` classes must end with `Resource` | Conflating REST and view controllers (ADR-020) |
| 7 | DTOs must reside in adapter packages | `*Dto` in domain or application |
| 8 | Converters must reside in adapter packages | (same) |
| 9 | ViewModels must reside in `adapter.incoming.web` | (same) |
| 10 | No technical bucket packages | Classes in `..entities..`, `..valueobjects..`, `..helpers..`, `..util..`, `..utils..` — package by domain concept (screaming architecture) |
| 11 | No technical suffixes in domain | `*Manager`/`*Helper`/`*Util`/`*Utils`/`*Impl` classes in `domain/` — name by specialty from the ubiquitous language |

---

## Module: DddTacticalPatternsArchUnitTest (DDD-specific)

Aggregate-level rules — if you don't use DDD aggregates, skip this module.

| # | Rule | Why |
|---|---|---|
| 1 | `*AggregateRoot` classes implement the AggregateRoot marker | Tactical traceability |
| 2 | Aggregates reference other aggregates by ID, not direct field | Vernon's Aggregate Design Rule #2 |
| 2a | Aggregates don't hold Repository/OutputPort fields | Aggregates are persistence-ignorant — dependencies are passed as method parameters |
| 2b | Domain model classes have no public setters | State changes go through intention-revealing methods from the ubiquitous language |
| 3 | Entities must hold a field whose **type** implements the `Id` marker | Identity is part of being an entity. Matched by type, not by name: a name check for a field ending in `id` accepts `valid`, `paid` and `uuid`, so an entity with no identity passes it |
| 4 | Non-root entities must not be public-constructible | Encapsulation: only the aggregate creates them |
| 5 | Entities don't hold AggregateRoot references | Same as #2 but for entities |
| 6 | Value Objects don't contain AggregateRoot or Entity types | Value Objects are pure data |
| 7 | Value Object classes are `final` | Immutability |
| 8 | Value Object fields are `final` | Deep immutability |
| 9 | Value Objects have no setters | Same |
| 9a | Value Objects are records or immutable classes with their own `equals`/`hashCode` (enums and interfaces excluded) | Records are preferred — the compiler grants immutability and attribute equality for free. A hand-written class is allowed: rules 7–9 already force its immutability, so this rule checks the one thing they cannot — attribute equality |
| 10 | Repository interfaces extend the Repository marker | Traceability |
| 11 | Repository interfaces live in `application.shared` | Locational rule |
| 12 | Repository implementations live in `adapter.outgoing` | (same) |
| 13 | Repositories exist only for AggregateRoots | One repository per aggregate root |
| 14 | Repository methods must not **expose** an Entity that is not an AggregateRoot — checked recursively through type arguments (`Optional<X>`, `List<? extends X>`, `X[]`, `Map<K,List<X>>`) | Aggregate boundary: a caller holding a non-root entity can mutate part of an aggregate without passing its root, so the root's invariants never run. Framed as a prohibition, not as "must return an AggregateRoot" — a boolean, a count, a page wrapper or a use-case-optimal Value Object are all legitimate returns |
| 15 | `*Store` interfaces extend `Store` marker, not `Repository` | Repository is reserved for Aggregate Roots; Stores serve operational data (Value Objects, events) |
| 16 | Store interfaces live in `application.shared` | Locational rule — same placement as Repository |
| 16a | Store implementations live in `adapter.outgoing` | (same) |
| 17 | Store interfaces don't have `findById` / `save` / `delete` methods | Those are Repository semantics — if a Store has them, the stored object is actually an Aggregate Root and the port should be a Repository |

---

## Module: DddStrategicPatternsArchUnitTest (DDD-specific)

Bounded-context rules.

| # | Rule | Why |
|---|---|---|
| 1 | Shared Kernel doesn't depend on bounded contexts | Otherwise it isn't shared |
| 2 | Application layer of context A doesn't reach context B directly | Boundary integrity |
| 2a | Domain layer of context A doesn't reach context B at all — not even its `api/` | Stricter than rule 2 and without exceptions: translating an Open Host Service is the application layer's or an adapter's job. The shared kernel is not a foreign context (different marker), so it needs no allow-list |
| 3 | `@OpenHostService` classes live in the context's published `api/` package or anywhere under `adapter.incoming` | An Open Host Service is the published relationship, not a transport: in-process it is `api/`, over the network an incoming adapter (REST, gRPC, MCP) — the adapter's sub-package is irrelevant |
| 4 | Outgoing adapters of context A access context B only via `api/` packages | Same boundary, different direction |
| 5 | Integration Events live in `events/` or `adapter.outgoing.event` | Spring Modulith `@NamedInterface` convention |
| 6 | Integration Events are immutable records | Wire-format stability |
| 7 | Anti-Corruption Layer classes (`*EventTranslator`, `*ACL`) live in `acl/` | Pattern visibility |

> **All isolation rules use `dependOnClassesThat`, never `accessClassesThat`.** ArchUnit counts an
> access as a method call or field access, so a field, parameter or record component of a forbidden
> type is a dependency and not an access. An isolation rule written with `accessClassesThat` reports
> success while a class holds the forbidden type outright.

---


## Module: ContextMapArchUnitTest (DDD-specific)

Executable context map: `@Upstream`, `@ExternalUpstream` and `@Partnership` on `package-info.java`
are the single source of truth for context relationships; these rules keep declarations and code in
agreement. `ContextMapDocumentationTest` renders `docs/context-map.md` from the same annotations.

| # | Rule | Why |
|---|---|---|
| 1 | `@Upstream`, `@ExternalUpstream`, `@Partnership` only on `@BoundedContext` packages | Relationships belong to contexts, not to arbitrary packages |
| 2 | `@ExternalUpstream` well-formed and unique per name + interaction | One declaration per external channel |
| 3 | Distinct external system names must not collide after Mermaid id normalization | Rendered diagram stays unambiguous |
| 4 | `@Upstream.context` names an existing context, never the declaring one | Dead or self-referential declarations |
| 5 | `@Upstream` unique per context + channel; `via` not empty | One declaration per channel |
| 6 | `@Upstream` declarations and Spring Modulith `allowedDependencies` agree | Two sources of truth would drift |
| 7 | `status = IMPLEMENTED` upstreams are backed by an actual code dependency | No aspirational declarations — use `PLANNED` |
| 8 | ACL: upstream contract types stay inside the matching adapter | Translation happens at the edge |
| 9 | Conformist: upstream contract types never reach the domain layer | Conformism does not suspend domain purity |
| 10 | External contract types respect declared translation + interaction | Same as 8/9 for external systems |
| 11 | Cross-context dependencies on published interfaces require an `@Upstream` declaration | No undeclared coupling |
| 12 | `@Partnership` names an existing context, never itself, and is symmetric | Partnership is mutual by definition |
| 13 | Diagnostic: display declared context map | Human-readable dump, never fails |

## Module: DddAdvancedPatternsArchUnitTest (DDD-specific)

| # | Rule | Why |
|---|---|---|
| 1 | Domain Events are records implementing the marker | Immutability + traceability |
| 2 | Domain Events live in `domain/` packages | Locational rule |
| 3 | Non-record Domain Events are `final` | Immutability |
| 4 | Domain Events have no Spring annotations | Domain stays framework-free |
| 5 | Integration Events have a `int version` field | Schema evolution |
| 6 | Plain Domain Events DON'T have a version field | Avoid premature versioning of internal events |
| 7 | Domain Events have a timestamp field (`Instant`/`LocalDateTime`/`ZonedDateTime`) | Eventual consistency requires causal order |
| 8 | Domain Services live in `domain.service` | Locational rule |
| 9 | Domain Services don't have Spring annotations | DIP |
| 10 | Domain Services are stateless (final fields only) | Concurrency safety |
| 11 | Factories implement the Factory marker | Traceability |
| 12 | Factories live in `domain/` | Locational rule |
| 13 | Factories don't have Spring annotations | DIP |
| 14 | Factories are stateless | Concurrency safety |
| 15 | `*Specification` classes live in `domain/` | Pattern visibility |
| 16 | `*Specification` classes don't have Spring annotations | DIP |

---

## Module: UseCasePatternsArchUnitTest (DCA-specific)

| # | Rule | Why |
|---|---|---|
| 1 | Base `InputPort` interface is in sharedkernel | Universal contract |
| 2 | `*Command` classes live in application layer | Naming → location |
| 3 | `*Query` classes live in application layer | (same) |
| 4 | `*Command` is immutable (final or record) | Inputs don't mutate |
| 5 | `*Query` is immutable | (same) |
| 6 | `*Result` lives in application layer | ADR-020 — application returns *Result |
| 7 | `*Result` is immutable | Outputs don't mutate |
| 8 | `*Response` lives in adapter.incoming | ADR-020 — adapters return *Response (e.g. JSON-shaped) |
| 9 | DTOs not used in domain layer | Pure model |
| 10 | DTOs not used in application layer | (same) — DTOs are an adapter concern |
| 11 | A use case that saves an aggregate publishes its domain events | Unpublished events are lost, and events stored on the instance may later be published out of context |
| 12 | A use case that publishes domain events runs inside a transaction boundary (`@Transactional` or `TransactionBoundary.inTransaction`) | After-commit listeners are skipped silently without an active transaction |
| 13 | A `@Transactional` use case calls no remote-capable output port (only `Repository`, `Store`, event publishers, `TransactionBoundary`) | A remote round trip inside the transaction holds the connection; a rollback cannot undo it |
| 14 | Use-case packages within one module use one consistent depth — all `application.<usecase>` or all `application.<feature>.<usecase>` (`DCA-USE-014`) | A *feature* is an optional, domain-named group of use cases below the layer. Mixing both forms, a use case directly in `application`, or one nested deeper than a feature makes the tree unreadable. Legibility only — nothing is inferred about bounded contexts or aggregate ownership |
| 15 | `*Result` must not expose aggregate roots or entities (`DCA-USE-015`) | A result is the use case's answer, not a handle on the model: identity and behaviour stay behind the port; values, enriched models and read models may cross. Checked transitively through nested records, part records anywhere in the application layer (`application.shared` included) and generic type arguments (`List<T>`, `Optional<T>`, `Map<K,V>`) |

---

## Module: SpringModulithVerificationTest (conditional)

Single rule: `ApplicationModules.of(BASE_PACKAGE).verify()`. Only install if Spring Modulith is on the classpath.
