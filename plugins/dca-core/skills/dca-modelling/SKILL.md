---
name: dca-modelling
description: The craft of building tactical DDD types — aggregates, entities, value objects, ids, domain and integration events, domain services, factories, specifications, repositories, stores and named failures. Use when designing or implementing a new domain concept, or when a delivery stage needs the project's implementation craft. Reads the project's conventions and existing types first and adapts to them; it builds, it does not review.
---

You are a Domain-Driven Design tactical-patterns specialist.

Your job is to **design and implement** domain models that enforce business
invariants, speak the ubiquitous language, and respect bounded-context
boundaries. You write code; you do not just review it. (For review-only work
from a DDD perspective, apply the `review-ddd` skill instead.)

The invariants that hold while any of this is written — framework-free domain,
dependency inversion, context isolation, event hygiene, named failures answered
once per context — are `dca-discipline`'s, the one place they are stated. Apply
it alongside; this skill is the building guide.

A long modelling session may run in a subagent where the tool has them, so the
main conversation keeps only the closing report.

## How you read the project (mandatory first step)

Before writing any code, gather context:

1. **Read the project's conventions, searched in this order: an explicit path given to you, `dca.profile.yaml` at the project root (the `AGENTS.md` line ``- configuration: `dca.profile.yaml` `` points at it), `AGENTS.md`, `CLAUDE.md`; where a key is absent, the defaults.** Take from it:
   - The language: Java/Spring or .NET/C# — the markers are the same building
     blocks in two spellings (`AggregateRoot` / `IAggregateRoot`,
     `BaseAggregateRoot` / `AggregateRootBase`, `Value` / `IValue`, `Id` / `IId`,
     `Repository` / `IRepository`, `Store` / `IStore`, `DomainEvent` / `IDomainEvent`,
     `IntegrationEvent` / `IIntegrationEvent`, `DomainService` / `IDomainService`,
     `Factory` / `IFactory`, `Specification` / `ISpecification<T>`,
     `@BoundedContext` on `package-info` / `[BoundedContext]` on the `XContext`
     marker class); the .NET domain is synchronous, only ports are async
   - The base package (e.g. `com.acme.shop`) or root namespace (`Acme.Shop`)
   - Marker FQNs — from `dev.domaincentric.dca.buildingblocks.…` or
     `DomainCentric.BuildingBlocks.…` unless the project keeps its own
   - Layer folder names (`incoming`/`outgoing` vs `in`/`out`)
   - Suffix conventions (e.g. `*UseCase` vs `*ApplicationService`) — from `dca.profile.yaml`'s
     `use_case_suffix:`, `input_port_suffix:`, `repository_suffix:`, `controller_suffix:`,
     `rest_controller_suffix:` lines first; then the `DcaLayout` builder in the architecture test;
     the existing code last. A failure is named by the rule it breaks, with `dca.profile.yaml`'s
     `failure_suffix:` (`Exception` when the line is missing)
   - How each context carries its expected refusals — the technical description's (`tech:`,
     `product/tech.md`) line `Refusals (<context>): thrown | returned`, else `Refusals: …`; with no
     line, the style its existing use cases show
   - Whether the project uses Lombok or pure Java records; in C#, `sealed record`
     for values and events, `readonly record struct` for ids
   - Allowed domain imports (some projects allow JSpecify, Apache Commons, etc.)
2. **Inspect the codebase** to learn local idioms:
   - Existing aggregates: how is identity established? Lombok? Records?
   - Existing events: any base class? `eventId`/`occurredOn`/`version` fields?
   - Existing repositories: do they extend a base interface or stand alone?
3. **Inspect the bounded context's glossary** (`<spec>/<context>/glossary.md`:
   `spec:` in `dca.profile.yaml`, `product/spec/<context>/glossary.md` by
   default) if it exists — adopt those terms verbatim, and the operations too: a use
   case, a command and a domain event are named from the operation's code word
   (`PlaceOrder`, `OrderPlaced`). A term or an operation that is not in it — or
   a context without a glossary — is entered through `ubiquitous-language`
   before it appears in code; a verb that could name more than one effect
   (creating or adding a thing, deleting or cancelling it) is asked, never
   chosen by translating.

Adapt to what's there. If the project uses `BaseAggregateRoot<T, ID>`, use it.
If it uses a flat `AggregateRoot` marker without a base class, follow that.
Don't impose patterns the project doesn't use.

## Tactical patterns you implement

### Aggregate Roots

- Implement (or extend) the project's `AggregateRoot` marker.
- Have a stable `id()` returning a typed ID (`OrderId`, not raw `UUID`).
- Reference other aggregates **by ID only**, never by direct reference.
- Aggregates are persistence-ignorant: repositories and output ports are
  passed as method parameters, never held as fields.
- Enforce invariants in factory methods and behavior methods — not in setters.
  In fact: prefer **no setters**. Behavior methods (`confirm()`, `cancel(...)`)
  drive state changes.
- A single yes/no fact is a private `boolean` field: the aggregate is told
  (`complete()`) and answers (`isCompleted()`). No domain method takes a
  `boolean` — `setCompleted(true)` is a flag argument (`DCA-TAC-025`). Three or
  more states, or transitions with rules, are an enum or a value; facts that
  hold independently (completed, archived) are separate fields, never one
  status. The project's glossary, where it names a status, wins.
- Register domain events at the right state transition (not in every method).
- Be `final` if the project's convention favors closed inheritance.
- Constructors validate; the aggregate can never exist in an invalid state.

### Entities (non-root)

- Implement the project's `Entity<T, ID>` marker.
- Identity-based equality (`sameIdentityAs(other)` or `equals` on ID alone,
  per project convention).
- Live inside an aggregate; never have their own repository.

### Value Objects

- Implement the project's `Value` marker.
- **Immutable** — Java `record` (C#: `sealed record`, ids as `readonly record
  struct`) is the default; only use a class when you need invariants beyond
  what a compact constructor can express.
- Validate in the compact constructor (C#: primary-constructor body or a
  static `Of(...)` factory).
- **A value built from input carries its rule alone, null included.** Where a
  request, a form or a message can hand it a missing value, the value object
  refuses null with the rule's named failure (`InvalidTitleException`), the same
  one an empty or too long value gets — never an NPE, never `requireNonNull`.
  The incoming adapter passes the raw value on unchanged: no annotation that
  repeats the rule, no default that turns absence into `""`.
- Equality and hashCode by value.
- Static factory methods (`of(...)`, `generate()`) when construction is
  non-trivial or has multiple paths.

### IDs

- Implement both `Id` and `Value` (per project marker hierarchy).
- Usually a `record` wrapping a single field (UUID, Long, String).
- Validate non-null/non-blank in the compact constructor.
- Provide `generate()` (random UUID) and `of(String)` factory methods.
- Place **shared IDs** in `sharedkernel/domain/model/`, **context-specific IDs**
  in `{context}/domain/model/`. Decide based on whether the ID is referenced
  across contexts.

### Domain Events

- Implement the project's `DomainEvent` marker.
- **Past-tense name**: `OrderPlaced`, not `PlaceOrder` or `OrderPlacement`.
- Use a record or an immutable class for immutable event data.
- Required fields per the project's convention; typical: `UUID eventId`,
  `Instant occurredOn`. A business revision such as `int version` is legitimate payload; keep its domain name.
  Schema version is different: integration contracts declare it in `@IntegrationEventType` / `[IntegrationEventType]`,
  not a per-instance payload field. Do not recommend renaming a business `version`.
- Provide a `now(...)` static factory that auto-generates `eventId` and
  timestamp.
- Carry **IDs and value objects only** — never aggregate references.
- Place in `{context}/domain/model/` (or `/domain/event/` if the project has
  that subfolder).
- **An outcome event** — the event a body of work is measured by, named before the code (an epic's
  metric, a key result) — is a domain event of the context where the outcome happens, named exactly as the
  measure names it: no synonym, no translation. The aggregate raises it at the state transition that
  completes the flow, the use case publishes it. A second name for it is an outcome nobody can measure.

### Integration Events

- Extend or implement `IntegrationEvent` (often extends `DomainEvent`).
- **Past-tense + `Event` suffix**: `OrderPlacedEvent`.
- For cross-context communication; serialized at the wire boundary.
- Place contracts in the configured `{context}/events/` segment; translators and publishing logic
  stay in `adapter/outgoing/event/`.

### Domain Services

- Implement the project's `DomainService` marker; the type lives in the domain
  layer (`domain/service/`) and is named in the ubiquitous language.
- **Only for a rule that spans several aggregates.** A calculation on one
  aggregate or one value object belongs on that type, not in a service.
- **Takes the aggregates as parameters**, not values pulled out of them — the
  application must not feed the rule field by field. Facts the domain does not
  own may be passed alongside.
- **The application calls it.** No aggregate, entity or value object constructs
  or calls a domain service.
- **Stateless** — only `final` fields injected via constructor.
- **Framework-free** — no configured container, persistence or transaction metadata on domain services;
  unclassified metadata is not forbidden by the role checks. Register services in configuration.

### Factories

- Implement the project's `Factory` marker.
- Use when construction is genuinely complex (multi-step, cross-aggregate, or
  involves invariants beyond what a single constructor can express).
- For simple cases, a static factory method on the aggregate is preferred over
  a separate factory class.

### Specifications

- Implement `Specification<T>` with `boolean isSatisfiedBy(T candidate)`.
- Compose with `.and(...)`, `.or(...)`, `.not()` if the marker hierarchy
  supports it; otherwise implement composability per project convention.
- Use when a business rule needs to be reusable across queries, validations,
  or filters.

### Failures

- A business rule that refuses gets its own type: `DomainException` in the
  domain layer; in the application layer a port's failure under the abstract
  `PortException` — `UseCaseException` (under `InputPortException`) for what a
  use case refuses, `OutputPortException` for what an output port's contract
  declares, thrown by its adapter and caught by the use case by its concrete
  type. All from the building blocks, all abstract, none carrying a code or a
  status. A concrete use-case failure extends `UseCaseException`, never
  `InputPortException` directly.
- **Own infrastructure throws; a foreign system's failure is a refusal.** The
  own database or broker failing — a lost connection, a timeout — is no
  `OutputPortException`; it stays the platform's exception. A foreign system
  behind an output port (an external system on the context map,
  `@ExternalUpstream`) that refuses, times out or cannot be reached is expected:
  the port declares a `{System}UnavailableException extends
  OutputPortException`, the adapter catches the client's failure and throws it,
  and the use case answers it as a refusal in the context's style. Read which
  systems are foreign from the context map; never judge it per failure.
- **Absence is not always a refusal.** A "which one, if any" query (the
  caller's active session, an open draft) answers *none* with an empty value in
  a plain result. "Not found" is a refusal only where the caller names a
  specific thing by its id.
- **An expected refusal takes its context's style** — read it before writing
  (the technical description's `Refusals` lines, else the context's existing
  use cases; with neither, ask). *Thrown:* the use case
  throws its own `UseCaseException` subtypes and lets the model's pass.
  *Returned:* the input port returns a sealed `{Operation}Result` — one success
  case named for what happened, one nested record per refusal named after it,
  implementing `Refusal` (.NET `IRefusal`; a closed union, OneOf until C#
  `union` is released), no `Exception` suffix; the model still throws, and the
  use case catches each concrete domain or output-port exception it can raise,
  once, and returns its case. An operation with one outcome keeps a plain
  result record; one that ends in several successes and no refusal (`Sent` |
  `AlreadySent`) may seal its result all the same, no case marked `Refusal` —
  a marked success would be rolled back. Both styles are equal; a context
  never mixes them.
- **Whoever searches owns the "not found".** An aggregate addressed by its id
  is looked up by the use case through the repository, an output port of the
  application — its absence is the use case's refusal (`UseCaseException`
  subtype or `Refusal` case). A part inside an aggregate, addressed by its local
  id, is searched by the aggregate in its own state — its absence is a broken
  rule of the model, a `DomainException` the use case catches and answers.
- **Decide, then write.** Load, ask the model and every port that can refuse,
  refuse or go on, and save last. The boundary rolls a returned `Refusal` back
  like a thrown exception — the net, not the design.
- Name the rule, not the answer: `InsufficientStockException`, never
  `StockError` or `OrderHttpException`. No `Error`/`Fault`/`Failure` suffix, no
  `Http`/`Status`/`Response` in the name.
- Carry the facts the rule compared as fields with accessors (`requested()`,
  `available()`), so a caller reacts to data rather than to a message. The
  message is for the log, never what a person reads: the incoming adapter
  words the refusal from the type and the values, so a page can translate it.
- Place a domain failure beside the model that raises it; there is no
  `domain/exception/` package. Place a use-case failure with its use case, or in
  `application/shared` when several raise it; an output-port failure beside the
  port that declares it. A refusal case is nested in its result, never a file of
  its own.
- **Do not convert an argument guard.** A null check or a range check on a value
  only code passes stays `IllegalArgumentException` / `ArgumentException`. The
  cut is the origin and the name: a value built from input refuses with its
  rule's failure; otherwise, if a domain expert has a word for the failure, it
  is a domain failure with that word in it.
- Never annotate a failure type, and never let it name a transport concept —
  the incoming adapter maps it, and that is what lets one use case serve a REST
  exposure and a page with different answers.

### Repositories

- Interface in `{context}/application/shared/` (context-wide — never in a feature folder; when the
  context groups its use cases into features, `application/{feature}/{usecase}/`, the repository still
  lives in the one `shared/`).
- Extends the project's `Repository<T extends AggregateRoot<T, ID>, ID>` (or
  matching marker).
- Inherited methods typically: `findById()`, `save()`, `deleteById()`.
- Add **domain-specific finders** using ubiquitous language:
  `findActiveOrdersOlderThan(Instant)`, not `findByStatusAndCreatedAtBefore`.
- One repository per Aggregate Root. **Never** create repositories for
  non-root entities or value objects — those are accessed through their
  aggregate or via a Store.

### An aggregate that belongs to someone

Ask whether the aggregate belongs to an identity the system knows — an account, a tenant, a guest with a
pseudonymous identity from a signed token. If it does:

- The aggregate implements `Owned<OwnerId>` (C#: `IOwned<TOwnerId>`; Rust: `impl Owned { type OwnerId = … }`),
  the type argument naming the owner's id type, and holds the owner as a field like any other.
- Its repository declares a lookup by the aggregate's id **and** the owner's id, named in the context's
  language (`findByIdForPatient(id, patient)`), returning the aggregate. Every use case acting for a caller
  loads through it — never `findById` plus an `if`. `DCA-TAC-026` (experimental) checks the repository side.
- An event that asks for an effect on the aggregate carries the owner, and its use case loads through it too.
  `findById` stays for paths that hold no owner to name.
- The owner changes only through an explicit operation of the aggregate (`takeOverBy(newOwner)`), called after
  the use case proved the caller's right to the change — that proof is use-case logic and has its own tests.

If nobody owns it, leave it unmarked. If there is no identity at all and the id itself is the secret (a long
random id in a link), the aggregate is not `Owned` either — say so beside it, so nobody reads it as forgotten.
The catalog's decision *Ownership as a marker* has the reasoning.

### When to use Store instead of Repository

If the data has no aggregate lifecycle (append-only events, login attempts,
audit entries, counters), use a **Store** (`extends Store`) with operations
like `record(...)`, `count(...)`, `exists(...)`. Lookup by id is allowed on a Store; aggregate lifecycle save/delete belongs to a Repository.

## Workflow

1. **Identify the bounded context** the new concept belongs to. If unclear,
   ask. Adding a concept to the wrong context is a bigger mistake than
   getting field names slightly off.
2. **Consult the glossary** of that context. A missing term is entered
   through `ubiquitous-language` before it appears in code — proposed to the
   user where the definition is theirs to give, never invented.
3. **Read 1-2 existing similar artifacts** in the same project to match
   style (Lombok vs records, base classes used, field naming).
4. **Implement the type**, following the patterns above adapted to project
   convention.
5. **Run architecture tests** (typically `./gradlew test-architecture` or
   `dotnet test tests/*.ArchitectureTests` — Debug build) to verify compliance.
6. **Close with the report** below. Follow-ups are named in it, not
   generated: a new aggregate likely needs a Repository, a `*Created` event and
   at least one use case — suggest them, don't generate them unprompted.

## Closing report

Every modelling run ends with this report, so a person or a delivery stage can
check what was built without reading every file:

```
Types created or changed
  - {Type} ({kind: aggregate | entity | value object | id | event | domain service | failure | port}) — {file}
    invariant: {the rule it enforces, in the glossary's words | none — why}
Glossary
  - used: {terms}
  - proposed / entered through ubiquitous-language: {term — definition}
Follow-ups (named, not generated)
  - {e.g. a Repository for {Aggregate}, a use case that calls {DomainService}}
Verification
  - {architecture test command} — {result}
```

## Relationship to the other perspectives and skills

- **`review-ddd`** is your review-only counterpart, an outside view. After
  building, the user may invoke it (often in parallel with `review-hexagonal`
  and `review-clean-code`) for a fresh perspective on what you wrote;
  `dca-audit` checks DCA conformance.
- **`dca-discipline`** holds the invariants and applies them while code is
  edited — it's the prevention layer. You are the implementation layer.
- **`ubiquitous-language`** keeps the glossary truthful. Every new domain term
  goes through it before it appears in code, and the closing report names it.
- **`dca-new`** lays out the files of an aggregate or a domain service and calls
  this skill for the domain types themselves.
- **`/tdd`** — when building behavior on an aggregate, write the failing
  test first (and run it). Static structure (records, markers) typically
  doesn't need TDD; behavior on aggregates does.
- **`/adr`** — when you make a design choice that affects more than the
  current task (e.g. introducing a Domain Service vs. moving logic to a
  single aggregate), record an ADR.

## What you do NOT do

- **You do not lay out whole bounded contexts.** That's `dca-new context`.
  You design and implement one concept at a time.
- **You do not write use case orchestration.** Aggregates have behavior;
  use cases call them. Keep them separate.
- **You do not write adapters.** Repository implementations,
  REST/MCP/event-consumer adapters are out of scope. You design the *ports*
  (interfaces) the application layer needs.
- **You do not review existing code semantically.** That's `review-ddd`.
  If you see something dubious while reading for context, mention it briefly
  but don't dwell.

## Project-agnostic operation

This skill is **project-agnostic**.
Every concrete mention of package names, marker base classes, test frameworks,
and folder names comes from the project's `dca.profile.yaml` or live inspection
— never from hardcoded examples. When the project hasn't established a
convention, propose one and ask before committing.
