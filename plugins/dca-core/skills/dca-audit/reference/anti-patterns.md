# Anti-patterns this review catches

Part of the `dca-audit` skill: what its *Phase 3* step points to beside `reference/checklist.md` — the findings
catalogue, each with its symptoms and the reason, so the user understands a finding. Where the checklist already
carries the symptom and the fix, the entry names the section instead of repeating it.

These are project-experience-derived. Document each so the user understands.

### Anemic aggregate
Symptoms: aggregate is mostly getters/setters; business logic lives in use case.
Why: aggregates should *protect invariants* — if they don't, they're just data containers.

### God use case
Review prompts, not numerical thresholds: a use case with more than five output ports, a long method, or multiple
nested if-blocks.
Why: a use case should be one cohesive operation. Big ones suggest missing domain service or
mis-bounded context.

### Leaky output port
Symptoms: an output port name reveals the implementation (`*JdbcRepository`, `*RestClient`,
`*KafkaPublisher`).
Why: ports are technology-agnostic by definition. Implementation details belong in the adapter.

### Port without an application-side caller
Symptoms: an `OutputPort` subtype that no use case depends on and that is not the identity port —
cookie or token handling, session logout (adapter mechanics); or a filter asking its own context
whether an account exists through an output port (an inbound question).
Why: an output port is a capability the application needs but does not own, fulfilled by an adapter
(in-memory or remote). Adapter mechanics stay in
the adapter without a marker; a question into the own context is a query use case or the
published API. The identity port is legitimate: the caller's identity comes from an identity system.

### Cookies of one exchange with different policies
Symptoms: the identity cookie is configured (`SameSite`, `Secure`) while the CSRF/antiforgery cookie keeps the
framework default; a cookie contract or test that names only the hand-written cookies.
Why: a request that needs both arrives incomplete wherever the policies diverge — an iframe, a cross-site redirect,
another scheme — and is refused as a *missing* token rather than a refused one, which points the reader at form
handling instead of at a cookie attribute. Framing belongs on its own switch: it is an origin question, the cookie
policy a site question.

### Domain event without identity or timestamp
Symptoms: a `DomainEvent` record without `eventId()` / `occurredOn()` (C#: `EventId` / `OccurredOn`).
Why: events are causal records; without an id they cannot be deduplicated, without time you can't
reason about ordering. Both members are the marker's contract, not a project convention — do not
suggest other spellings (`occurredAt`, `timestamp`).

### Domain event with mutable field
Why: events are facts about the past — facts don't change.

### Setter on value object
Why: value objects are immutable by definition.

### Public setter on entity or aggregate
Symptoms: `setX(...)` on a domain model class, even when it validates internally.
Why: state changes go through intention-revealing methods from the ubiquitous language
(`adjustStockTo`, not `setAvailableQuantity`). A setter name hides the business operation.

### Injected dependency in aggregate
Symptoms: an aggregate holds a `*Repository`, output port, or service as a field (`DCA-TAC-002`).
Why: aggregates are persistence-ignorant — dependencies are loaded by the use case and
passed as method parameters. Moving the lookup behind a callback or resolver parameter does not change
who owns the calculation; review such parameters manually.

### Business rule as an argument exception
Symptoms: a state transition or a cross-field invariant refuses with `IllegalStateException` /
`InvalidOperationException` or `IllegalArgumentException` / `ArgumentException`.
Why: the adapter cannot tell the case apart from a defect of this application, and answers both the same way.
`DCA-ERR-001` sees only the types that *are* declared, so this one is the review's: would a domain expert have
a word for the failure? If yes, it is a `DomainException` subtype with that word in it. A null or range check
is not — that stays an argument guard.

### Blanket catch around a use-case call
Symptoms: `catch (Exception)` / `catch (RuntimeException)` in an incoming adapter, or in a use case that
converts a rule into a result variant.
Why: a defect of this application is reported as the caller's mistake and disappears from anything watching
for server faults. Name the types the call can produce. `DCA-ERR-006` lists the packages worth looking at and
cannot decide this.

### Failure translated in more than one place
Symptoms: a `try`/`catch` in a resource for a failure the context's exception handler already maps, a
handler in global infrastructure naming one context's failure, or the same `catch` of a refusal in every
handler of a page adapter, each building its own redirect with a notice.
Why: two sites decide the same answer and drift apart. One translation site per context, and infrastructure
keeps only the last-resort handler for an exception nobody named. A page adapter has one method that turns
the refusal and its notice into the redirect, and every handler calls it.

### Status derived from the base type
Symptoms: every `DomainException` mapped to one status, every `UseCaseException` to another.
Why: the base type says which layer owns the failure, not what the caller should do next. A position missing
from a cart is a rule of the model and still answers `404`.

### Domain gateway without a rationale
Symptoms: a `DomainGateway` interface in `domain/gateway/` — or a domain service holding one — where the
facts could have been supplied by the use case as an immutable snapshot; or a gateway that writes.
Why: the default is *domain services over supplied facts*: the use case fetches through output ports and hands
snapshots in. A `DomainGateway` is the explicit exception — a narrow, read-only interface in the ubiquitous
language, owned by the domain, implemented in an outgoing adapter — and needs a recorded effect-and-dependency
rationale. It is legitimate; it is not a finding by itself. A pure algorithmic strategy passed in is not a gateway.
The aggregate never holds a gateway; the domain service or the use case passes it in.

### Transaction outside the application layer
Symptoms: `@Transactional` on a domain class or incoming adapter.
Why: the use case owns the unit of work. (Outgoing persistence adapters may use it for
multi-statement atomicity — joins the caller's transaction.)

### Controller reaching past the use case
Symptoms: a `*Controller`/`*Resource` injects a `*Repository`.
Why: incoming adapters drive the application through input ports only — direct repository
access bypasses transactions, authorization, and orchestration.

### Technical names in the domain
Symptoms: `*Helper`/`*Util`/`*Impl`/`*Implementation` classes in `domain/` (`DCA-NAM-010`), or bucket packages
like `entities/`, `valueobjects/`, `helpers/`, `util/` (`DCA-NAM-009`). A term the ubiquitous language uses
(`PortfolioManager`, `PriceCalculator`) is not a technical name, whatever its suffix looks like.
Why: technical names signal a missing domain concept; packages are named by domain concept.

### Spring annotation on domain class
Why: domain stays framework-free (DCA invariant). The C# twin: an ASP.NET, EF Core (`[Table]`, `DbContext`)
or `System.Text.Json` attribute on a class in `Domain/`, or an `async` member on an aggregate — the .NET
catalog keeps the domain synchronous and framework-free (`DCA-NET-00x`).

### Cross-context import not via the published packages
Symptoms: file in `contextA/...` imports from `contextB/domain/...` or `contextB/application/...` directly.
Why: contexts communicate through the other context's published packages only — `api/` (the synchronous
contract, Open Host Service) and `events/` (its integration events) — never raw domain or application types.
The consuming use case sees its own output port (`*DataPort`); the outgoing adapter calls the `api/` contract.

### Use-case naming mismatch
Symptoms: class name doesn't match the action it performs (`OrderHandler` instead of
`PlaceOrderUseCase`; or use case named for the output, not the verb).
Why: use cases are named for user intent, not technical mechanism.

### DTO in domain or application
Why: DTOs are an adapter concern. If domain or application has a `*Dto`, a transformation
boundary is misplaced.

### Mutable Result/Command/Query
Why: messages are immutable. Java records make this trivial.

### Repository for non-aggregate
Symptoms: a `*Repository` exists for an Entity that isn't an AggregateRoot.
Why: only aggregate roots have repositories — non-root entities are loaded through their
aggregate.

### Repository vs. Store mismatch
Symptoms and fix: `reference/checklist.md` § *Repository vs. Store correctness* (a `*Store` exposing `save`/`delete`,
or a `*Repository` whose stored type is a Value Object / record without aggregate lifecycle).
Why: DCA distinguishes Repository (for Aggregate Roots — collection-like, identity-based) from
Store (for operational data — record/count/exists). Confusing them breaks the Ubiquitous
Language: a reader can no longer tell from the port name what kind of data it manages. The difference is
lifecycle, not lookup.
Note: the Store half is now mechanical — ArchUnit checks the marker, both placements, and the
forbidden `save`/`delete` method names (`DCA-TAC-021`). What remains for review is the direction
ArchUnit cannot see: a `*Repository` whose stored type has no aggregate lifecycle.
