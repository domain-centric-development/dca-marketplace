---
name: dca-discipline
description: |
  Applies Domain-Centric Architecture invariants while writing or editing
  Java/Spring or .NET/C# code: framework-free domain, dependency inversion (interfaces in
  app/domain, impls in adapters), bounded-context isolation (no raw cross-context
  imports), domain-event hygiene (publish + clear). Use during edits to
  domain/, application/, or adapter/ folders.
disable-model-invocation: false
---

# /dca-discipline — DCA invariants while writing code

This skill is a **set of write-time guards**, not a review. Before every edit
inside a DCA-shaped project, Claude checks the file's layer and applies the
rules that apply to that layer.

## The five invariants

### 1. No framework in domain

Files under `**/domain/**` MUST NOT import:

- `org.springframework.*`
- `jakarta.persistence.*`, `jakarta.validation.*` (except Bean-Validation
  annotations only if the project deliberately allows it — check conventions)
- `org.hibernate.*`
- `com.fasterxml.jackson.*`
- Any other framework-specific package

C# (`**/Domain/**`): no `Microsoft.AspNetCore.*`, `Microsoft.EntityFrameworkCore.*`, `System.Data.*`,
`System.Transactions.*`, `System.Text.Json.Serialization` attributes, `Microsoft.Extensions.*` — and no
`async` member: ports are async, the domain is not.

**What to do when the user asks for a forbidden import:**

> The annotation `@Component` would put framework code into the domain. The
> DCA invariant is: domain is framework-free. Place this class in
> `application/{usecase}/` (if it's a use case) or in `adapter/` (if it
> integrates with a framework).
>
> Want me to (a) move the class, or (b) keep it in domain *without* the
> annotation, or (c) explicitly override the rule via an ADR?

Don't silently rewrite; ask. The third option is rare but real — if the user
chooses it, suggest `/adr new` to record the exception.

### 2. Dependency inversion

Code in `domain/` and `application/` may only depend on:

- Other domain types
- Output ports (interfaces) — never their implementations
- Standard library and language

It MAY NOT import:

- Classes from `adapter/`, `infrastructure/`
- Concrete clients (`RestTemplate`, `JdbcTemplate`, `KafkaProducer`, `HttpClient`, `DbContext`, etc.)
- Framework annotations on the **API surface** of a use case (return types,
  parameters)

**What to do when a use-case impl needs new infrastructure:**

1. Define an output port interface in `application/shared/` (or in the use
   case's own folder if it's only used there — see decision guide in
   `../dca-review/reference/use-case-pattern.md` §3).
2. Reference the port from the use case.
3. Add an implementation in `adapter/outgoing/...`.

If the user tries to inject a concrete adapter type, stop and suggest the
port-first refactor.

### 3. Bounded-context isolation

Direct imports from `{basePackage}.contextA.domain.*` into a file in
`{basePackage}.contextB.*` are forbidden.

**Allowed cross-context channels:**

| Channel | Where the dependency lives | Example |
|---|---|---|
| Open Host Service (REST/MCP) | downstream calls upstream's incoming API | `Cart` reads `Catalog` via HTTP `/products/{id}` |
| Integration event | downstream consumes upstream event | `Checkout` listens to `OrderPlacedEvent` |
| Shared kernel value objects | both contexts import from `sharedkernel/` | `Money`, `ProductId` |

**What to do when you see a cross-context import:**

> `cart.application.AddToCart` imports `catalog.domain.Product`. That couples
> the contexts at the domain level. Options:
>
> 1. Call Catalog's Open Host Service (REST) — recommended for read-time data.
> 2. Listen to a Catalog integration event and project locally — recommended if
>    Cart needs to react to changes.
> 3. Move `Product` into the shared kernel if it's truly universal (rare).
>
> Which fits the use case?

### 4. Domain-event hygiene

When a domain class registers events (`registerEvent(...)`), the calling use
case must clear them after persistence or publication. Otherwise events
accumulate on a long-lived aggregate and get re-emitted.

**Checklist for use-case impls:**

```java
@Transactional
public Result execute(Command cmd) {
    var aggregate = repository.findById(cmd.id()).orElseThrow();
    aggregate.doSomething(cmd.payload());    // registers event(s) internally
    repository.save(aggregate);              // persist
    eventPublisher.publishAndClearEvents(aggregate); // dispatch succeeds before clearing
    return Result.of(aggregate);
}
```

C# — the same discipline with the library's publisher, which clears after dispatching:

```csharp
public Task<Result> ExecuteAsync(Command cmd, CancellationToken ct = default) =>
    _transaction.InTransactionAsync(async innerCt =>
    {
        var aggregate = await _repository.FindByIdAsync(new Id(cmd.Id), innerCt) ?? throw new ArgumentException(...);
        aggregate.DoSomething(cmd.Payload);                       // registers event(s) internally
        await _repository.SaveAsync(aggregate, innerCt);          // persist first
        await _events.PublishAndClearEventsAsync(aggregate, innerCt);   // then publish + clear
        return Result.From(aggregate);
    }, ct);
```

Use the building-block publisher contract. Its implementation clears only after successful synchronous dispatch.
Events are optional when no domain fact needs publication: an event-free aggregate needs no publisher dependency.
The conservative USE-009 exemption requires a resolved, completely inspected aggregate hierarchy.

An own-context outgoing adapter subscribes to the domain fact, translates to a contract in `{context}/events/`,
and captures it inside the transaction. For Spring, the subscription can be a plain synchronous `@EventListener`:

```java
// Same context, adapter/outgoing/event; the publisher captures transactionally.
@EventListener
public void on(DocumentApproved fact) {
    integrationEvents.publish(DocumentApprovedEvent.from(fact));
}
```

In .NET the same adapter implements the local domain-event listener contract and awaits its integration publisher.
Async consumers acknowledge per consumer/effect; bounded retry and intentional manual replay preserve the snapshot
and stable event/consumer/effect key. Provider-supported idempotency is needed to suppress acceptance-before-ack duplicates.
Synchronous remote effects cannot roll back with local state. Event snapshot policy does not decide template or recipient policy.

**Event shape rules** (all four required):

1. **Immutable**: Java record or immutable class / C# record or immutable class/readonly struct, no mutable instance fields or setters.
2. **Past tense name**: `OrderPlaced`, not `PlaceOrder` or `OrderPlacement`.
3. **`occurredOn` field** of type `Instant` / `DateTimeOffset` (or matching convention).
4. **Carries IDs and value objects only**, no aggregate references.

### 5. Domain-model and transaction discipline

When writing or editing domain model classes:

- **Never add public setters.** State changes go through intention-revealing
  ubiquitous-language methods (`confirm()`, `cancel(reason)`), not
  `setStatus(...)`.
- **Aggregates are persistence-ignorant.** No `Repository`, `Store`, or other
  `OutputPort` fields on an aggregate — if domain logic needs one, pass it as
  a method parameter.
- **`@Transactional` only on application-layer use cases.** Outgoing
  persistence adapters are an allowed exception; never on domain classes or
  incoming adapters. C# has no such attribute: the boundary is
  `ITransactionBoundary.InTransactionAsync` (or a decorator around `IUseCase`)
  in the use case, and EF Core / `System.Transactions` stay out of
  `Application/` (`DCA-NET-006`).
- **No remote call inside the transaction.** A use case that calls a port
  which may leave the process (another context's API, a payment provider)
  drops the class-level annotation: remote reads first, then
  `transactionBoundary.inTransaction(() -> { load; mutate; save; publish; })` — the `TransactionBoundary`
  application-layer execution abstraction of the building blocks, not a port. Remote *effects* go after the commit,
  as a reaction to an integration event.

> **Note:** invariant strictness follows the context's declared pattern style
> (see the project's pattern-selection ADR, if any). Contexts implemented as
> transaction script (supporting subdomains) get structural rules only —
> invariants 1–3 apply, the tactical rules in 4–5 may be relaxed.

## How this skill operates

Before any write or edit, Claude:

1. Looks at the target path. Classifies the layer (`domain` / `application` /
   `adapter/incoming` / `adapter/outgoing` / `infrastructure`).
2. Applies the rules that match that layer (see table).
3. Cross-checks imports the edit would introduce.
4. If a violation is about to happen, stops and surfaces the choice to the
   user (using the exact phrasing from the invariant sections above).

| Layer | Rules applied |
|---|---|
| `domain/` | 1, 2, 3, 4, 5 |
| `application/{usecase}/` — or `application/{feature}/{usecase}/` in a feature-grouped context (one form per context, `DCA-USE-014`; no feature cycles, `DCA-CYC-005`) | 2, 3, 4, 5 (`@Transactional` / `InTransactionAsync` lives here) |
| `application/shared/` | 2 (interfaces only — no impls) |
| `adapter/incoming/` | 3 (must not bypass application layer to reach domain: no `DomainService` injected or invoked, `DCA-HEX-012`; reads and formats the `*Result` — a delivered read model's own queries included — constructs no domain object, combines nothing into a new business fact), 5 (no `@Transactional`) |
| `adapter/outgoing/` | 3 (must implement a port, not introduce new domain concepts); `@Transactional` allowed on persistence adapters |
| `infrastructure/` | — (framework code belongs here; C#: DI registration `Add{Context}Context()`) |

The same table applies to the C# folders in PascalCase (`Domain/`, `Application/{UseCase}/`,
`Adapter/Incoming/`, `Adapter/Outgoing/`, `Infrastructure/`).

## Conventions overlay

Read `<project-root>/.claude/dca/conventions.md` for:

- The actual base package / root namespace; markers come from the library
  (`dev.domaincentric.dca.buildingblocks.…` / `DomainCentric.BuildingBlocks.…`)
- Whether the project's layer folders use the DCA defaults (`incoming` /
  `outgoing`) or alternatives (`in` / `out`) — also readable from the
  `DcaLayout` builder in the architecture test
- Project-specific exceptions (e.g. "Bean Validation annotations allowed in
  domain")

If no conventions file: use DCA defaults from
`dca-guide/architecture/rules.md`.

## What this skill does NOT do

- **Doesn't review existing code.** That's `dca-review` and the reviewer agents.
- **Doesn't generate scaffolds.** That's `dca-scaffold`.
- **Doesn't enforce naming.** That's `/clean-code` and `/ubiquitous-language`.
- **Doesn't run ArchUnit.** ArchUnit is the safety net *after* this skill;
  if `dca-discipline` does its job, ArchUnit stays green.

## Anti-pattern: silently bypassing the rule

If the user insists on a violation ("just add `@Entity` to the aggregate"),
do NOT silently comply. Either:

1. Refuse and explain the alternative (port + adapter, ACL, etc.).
2. Ask the user to record the exception via `/adr new` so future readers
   understand why the rule was bent here.

The point of the skill is to make the discipline visible, not to make the
user's life harder. When the rule's cost outweighs its benefit (legacy
integration, framework-mandated annotation), an ADR makes the exception
explicit — and that's a successful outcome.

Domain vocabulary may include `Manager`. Repository and Store ports may be local to
one use case; reused ports belong in application/shared. Store lookup by key is valid;
aggregate save/delete semantics require a Repository. Response types may belong to
incoming or outgoing adapters. Review entity constructor callers for the domain
invariant boundary, rather than demanding private constructors. Configured operation
containers do not alter the flat/grouped consistency requirement.

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

Validate invariants again at aggregate entry points when default construction, deserialization or reconstitution can bypass a value constructor. Retrieve external facts in the use case and supply immutable snapshots to domain services; do not hide lookup in aggregate callbacks. TAC-002 checks fields, so semantic callback review remains manual.
