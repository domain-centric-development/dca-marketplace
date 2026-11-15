# Anti-patterns this review catches

`dca-audit` Phase 3, beside `reference/checklist.md`: symptoms and the reason, to explain each finding. Where the
checklist carries symptom and fix, the entry names its section.

### Anemic aggregate
Symptoms: aggregate is mostly getters/setters; business logic lives in use case.
Why: aggregates protect invariants.

### God use case
Review prompts, not numerical thresholds: a use case with more than five output ports, a long method, or multiple
nested if-blocks.
Why: one cohesive operation; big ones suggest a missing domain service or a mis-bounded context.

### Leaky output port
Symptoms: an output port name reveals the implementation (`*JdbcRepository`, `*RestClient`,
`*KafkaPublisher`).
Why: ports are technology-agnostic.

### Port without an application-side caller
Symptoms: an `OutputPort` subtype that no use case depends on and that is not the identity port —
cookie or token handling, session logout (adapter mechanics); or a filter asking its own context
whether an account exists through an output port (an inbound question).
Why: an output port is a capability the application needs but does not own. Adapter mechanics stay in the
adapter without a marker; a question into the own context is a query use case or the published API. The identity
port is legitimate: identity comes from an identity system.

### Cookies of one exchange with different policies
Symptoms: the identity cookie is configured (`SameSite`, `Secure`) while the CSRF/antiforgery cookie keeps the
framework default; a cookie contract or test that names only the hand-written cookies.
Why: a request that needs both arrives incomplete wherever the policies diverge — an iframe, a cross-site redirect,
another scheme — and is refused as a *missing* token rather than a refused one, which points the reader at form
handling instead of at a cookie attribute. Framing belongs on its own switch: it is an origin question, the cookie
policy a site question.

### Domain event without identity or timestamp
Symptoms: a `DomainEvent` record without `eventId()` / `occurredOn()` (C#: `EventId` / `OccurredOn`).
Why: dedup and ordering. Both members are the marker's contract — never suggest other spellings (`occurredAt`,
`timestamp`).

### Domain event with mutable field

### Setter on value object

### Public setter on entity or aggregate
Symptoms: `setX(...)` on a domain model class, even when it validates internally.
Why: state changes go through intention-revealing methods of the ubiquitous language (`adjustStockTo`, not
`setAvailableQuantity`).

### Injected dependency in aggregate
Symptoms: an aggregate holds a `*Repository`, output port, or service as a field (`DCA-TAC-002`).
Why: the use case loads dependencies and passes them as method parameters. A callback or resolver parameter does
not change who owns the calculation; review such parameters manually.

### Business rule as an argument exception
Symptoms: a state transition or a cross-field invariant refuses with `IllegalStateException` /
`InvalidOperationException` or `IllegalArgumentException` / `ArgumentException`.
Why: the adapter cannot tell the case apart from a defect of this application, and answers both the same way.
`DCA-ERR-001` sees only the types that *are* declared, so this one is the review's: would a domain expert have
a word for the failure? If yes, it is a `DomainException` subtype with that word in it. A null or range check
on a value only code passes is not — that stays an argument guard. On a value built from input it is the rule:
the value object refuses null with the rule's named failure.

### A rule checked at the edge and again in the value object
Symptoms: a request or form record carries `@NotBlank`/`@Size` (`[Required]`/`[MaxLength]`) for a field whose
value object checks the same; or `@RequestParam(defaultValue = "")` turns a missing field into an empty one so
the value object never sees null — and has no refusal for it.
Why: two copies drift, two mechanisms answer one rule, and a change of the rule changes the adapter too. The
adapter checks shape only; the value object refuses everything its rule refuses, null included.

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
Why: two sites decide the same answer and drift apart. Each refusal is answered once per context — one
exception handler where the context throws, one adapter class every switch calls where it returns — and
infrastructure keeps only the last-resort handler for an exception nobody named. A page adapter has one method that turns
the refusal and its notice into the redirect, and every handler calls it.

### Refusals thrown and returned in one context
Symptoms: one use case of a context returns a sealed result with refusal cases, the next throws a
`UseCaseException` for the same kind of refusal; or a switch over a result with a `default` branch.
Why: the context's adapters answer one kind of failure two ways, and a new use case has no shape to follow; a
`default` compiles every new case into one answer — the defect the result was meant to remove. One style per
context, as the project records it; a switch names every case.

### A foreign system's failure thrown as the unexpected, the own infrastructure's returned as a refusal
Symptoms: an output port to an external system the context map declares (`@ExternalUpstream`) lets the client's
timeout or connection failure escape as the platform's exception, or the use case throws a `UseCaseException` for it
that no port declared; the other way round, a refusal case or an `OutputPortException` for the own database or
broker failing.
Why: a foreign system refusing, timing out or being unreachable is expected behaviour of the integration, and a
caller has an answer for it — its port declares it as an `OutputPortException`, the adapter throws it, the use case
answers it as a refusal. The own database and broker have to be there; their failure is unexpected and stays an
exception. Which systems are foreign is read from the context map, so two people judge it the same way.

### "None" refused on a "which one, if any" query
Symptoms: a query that asks whether there is one (the caller's active session, an open draft) returns a
`…NotFound` case or throws a `…NotFoundException` when there is none.
Why: "none" is a normal answer to that question; an empty value carries it, and the caller shows the empty state.
"Not found" is a refusal only where the caller names a specific thing by its id.

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
Why: incoming adapters drive the application through input ports only.

### Technical names in the domain
Symptoms: `*Helper`/`*Util`/`*Impl`/`*Implementation` classes in `domain/` (`DCA-NAM-010`), or bucket packages
like `entities/`, `valueobjects/`, `helpers/`, `util/` (`DCA-NAM-009`). A term the ubiquitous language uses
(`PortfolioManager`, `PriceCalculator`) is not a technical name, whatever its suffix looks like.
Why: a missing domain concept; packages are named by domain concept.

### Spring annotation on domain class
Why: framework-free domain. C# twin: an ASP.NET, EF Core (`[Table]`, `DbContext`)
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
Why: named for user intent, not mechanism.

### DTO in domain or application
Why: DTOs are an adapter concern; the transformation boundary is misplaced.

### Mutable Result/Command/Query

### Repository for non-aggregate
Symptoms: a `*Repository` exists for an Entity that isn't an AggregateRoot.
Why: non-root entities load through their aggregate.

### Repository vs. Store mismatch
Symptoms and fix: `reference/checklist.md` § *Repository vs. Store correctness* (a `*Store` exposing `save`/`delete`,
or a `*Repository` whose stored type is a Value Object / record without aggregate lifecycle).
Why: Repository = aggregate roots (collection-like, identity); Store = operational data (record/count/exists). The
difference is lifecycle, not lookup.
The Store half is `DCA-TAC-021` (marker, placements, no `save`/`delete`); review only the other direction: a
`*Repository` whose stored type has no aggregate lifecycle.
