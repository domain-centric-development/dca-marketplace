# The element modes — context, usecase, aggregate, store, domainservice

Detail of `dca-new`'s code modes: parameters, placement, files per language, wiring, decision tables.

## Mode context

> Subdomain type in the designed map (`domain:` in `dca.profile.yaml`, `product/domain.md` by default) and a
> pattern-selection ADR (e.g. `docs/adr/`) decide the full tactical structure; supporting/generic may get a
> simpler layout. A context the map lacks → `dca-describe`, never added silently.

### Steps

1. **Validate:** lowercase, single word (`orders`). Hyphenated → ask: `customeraccount` (package) or `customer-account` (Gradle module name) — they differ.
2. **Decide install location:**
   - **Single-module project:** create the package directly under `src/main/java/{basePackage}/{context}/`
     (C#: the namespace `{rootNamespace}.{Context}` inside the existing project).
   - **Multi-module Gradle:** a sub-project `{context}/` with its own `build.gradle.kts`. Ask which applies.
   - **.NET, one project per context** (the .NET reference layout): create `src/{rootNamespace}.{Context}/` from
     `templates/bounded-context/Context.csproj.tmpl`, add it with `dotnet sln add`.
3. **Generate the directory tree** (per `templates/bounded-context/`):
   ```
   {basePackage}/{context}/
     domain/
       event/                # empty package — events live here when created by Mode aggregate
       model/                # aggregates, value objects, IDs
       service/              # domain services (optional, only when needed — Mode domainservice)
     application/
       shared/               # shared output ports across use cases (Repository, etc.)
       # use cases get their own subdirectory each via Mode usecase
     adapter/
       {incoming}/           # honors the DcaLayout incoming segment (incoming / in)
         api/                # REST resources
         event/              # event consumers
         web/                # MVC controllers + ViewModels (if applicable)
       {outgoing}/
         persistence/        # repository impls
         event/              # integration event publishers
     package-info.java       # @BoundedContext("name")
   ```
   C#: PascalCase segments (`Domain/Model`, `Application/Shared`, `Adapter/Incoming/Web`, `Adapter/Outgoing/Persistence`,
   `Infrastructure/`).
4. **Declare the context.** Java: `package-info.java` with `@BoundedContext` (`templates/bounded-context/package-info.java.tmpl`).
   C# has no `package-info`: write the marker class `{Context}Context` in the context root namespace
   (`templates/bounded-context/Context.cs.tmpl`) and the DI extension `Add{Context}Context()` in `Infrastructure/`
   (`ContextRegistration.cs.tmpl`); tell the user to call it from the host's `Program.cs`.
5. **Add Gradle module** if multi-module: create `build.gradle.kts` from `templates/bounded-context/build.gradle.kts.tmpl` and add `include("{context}")` to `settings.gradle.kts`.
6. **Move the context's glossary.** Where the designed domain (`domain:` in `dca.profile.yaml`, `product/domain.md` by
   default) has a `### {context}` section under `## Glossary`, write its rows as entries of the new context's
   glossary through `ubiquitous-language` — at `<spec>/<context>/glossary.md` (`spec:` in `dca.profile.yaml`,
   `product/spec/<context>/glossary.md` by default, `<context>` the context's name in lowercase, words joined by
   `-`), never beside the domain code — and replace the section with one line naming that file. Moved, not
   copied: one place per word.
7. **Verify:** run the architecture tests if they exist; the empty context must not break them.

---

## Mode usecase

### Required parameters (ask if not given)

- **Context**; **name** in lowerCamelCase (`placeOrder`, `getOrderById`); **type** Command (writes) or Query (reads)
- **Output ports:** existing repositories/ports, or a fresh `*Repository` for a new aggregate
- **Expected refusals** a caller can answer — not found, may not act, a business rule says no, a foreign system
  behind an output port refused or did not answer — each named after the refusal (`OrderNotFound`, `OrderAlreadyShipped`, `PaymentProviderUnavailable`), or none. A foreign system is
  one the context map declares as an external system; the own database or broker failing is never a refusal. A
  query that asks "which one, if any" has none for "there is none": it answers with an empty value in its result.
  "Not found" is a refusal only where the caller names a specific thing by its id.

### Refusals: thrown or returned

The context's style is a line of the technical description (`product/tech.md`, or `tech:` in `dca.profile.yaml`):
`Refusals (<context>): thrown | returned`, else `Refusals: thrown | returned`. No line → the context's existing
use cases; neither → ask the person (both equal, the template never picks) and write the answer as that line via
`dca-describe`, never into this run alone. A context never mixes styles.

| | Thrown | Returned |
|---|---|---|
| Result | the plain `{Name}Result` record | `{Name}Result` closed: Java a `sealed interface` with the cases nested as records; C# a OneOf union (`[GenerateOneOf]`, `OneOfBase<…>`, the `OneOf` and `OneOf.SourceGenerator` packages) until C# `union` types are released |
| A refusal the use case finds | a use-case exception beside the use case, `{Refusal}Exception extends UseCaseException` (named by the refusal, carrying its ids and figures) | a case of the result implementing `Refusal` / `IRefusal`, returned |
| The model's refusal | the `DomainException` passes uncaught | caught once by its concrete type, returned as its case — never a base type |
| A failure an output port declares (`OutputPortException`): a conflict only the store sees, or a foreign system that refused or did not answer | caught by its concrete type, thrown as the use case's own `UseCaseException` | caught by its concrete type, returned as its case where the caller can answer it |
| The own database or broker failing | not caught — the platform's exception, unexpected | the same |
| "None" on a "which one, if any" query | no refusal: an empty value in the plain result | the same |
| The incoming adapter | calls the port and maps the success; the context's one exception handler maps each refusal type to its answer | a `switch` over the result **without a `default`** (C#: `Match`, one function per case, in the cases' order); each refusal arm calls the class that writes that answer once per context |
| Rollback | the thrown failure rolls the transaction back | the transaction boundary rolls back on a returned `Refusal` (Java declarative: `dca-spring`'s net; explicit: `TransactionBoundary`; .NET: the project's `ITransactionBoundary`) — still every refusal before the first write |

`returnsRefusals` (`reference/placeholders.md`) is `true` only where the context returns **and** the use case has at
least one expected refusal: a use case nobody can refuse gets the plain record in both styles. One that ends in
several successes and no refusal (`Sent` | `AlreadySent`) may have a sealed result instead — written by hand, no
case marked `Refusal`. A throwing-style use-case exception has no template: name and fields from the refusal,
written by hand beside the use case, the project's `failure_suffix` applied.

The adapter's translation, both forms (Java; the answers written once, in the context's adapter):

```java
// returned — the compiler holds every case
return switch (cancelOrder.execute(command)) {
    case CancelOrderResult.Cancelled cancelled -> ResponseEntity.ok(CancellationResponse.from(cancelled));
    case CancelOrderResult.OrderNotFound refusal -> OrderProblems.orderNotFound(refusal.orderId());
    case CancelOrderResult.OrderAlreadyShipped refusal -> OrderProblems.alreadyShipped(refusal.orderId(), refusal.shippedAt());
};

// thrown — the call maps the success; the context's exception handler maps each refusal
return ResponseEntity.ok(CancellationResponse.from(cancelOrder.execute(command)));

@ExceptionHandler(OrderNotFoundException.class)
ProblemDetail handleOrderNotFound(OrderNotFoundException exception) { ... }
```

### Placement: flat or feature-grouped context

Before writing, look at the packages directly below `{context}/application/` (ignore `shared`):

```bash
find src/main/java/{basePackage//.//}/{context}/application -mindepth 1 -maxdepth 1 -type d -not -name shared
```

- Folders hold use cases directly (`*InputPort`, `*UseCase`) → **flat**: `application/{usecasename}/`.
- Folders hold folders of use cases → **grouped by feature**: `application/{feature}/{usecasename}/`. A feature is
  an optional, domain-named group of use cases — a navigation boundary below the layer, not a module or aggregate
  owner. Ask which feature (offer existing); none fits → a new lowercase name **from the ubiquitous language**.
  Reject technical buckets (`commands`, `queries`, `handlers`, `services`, `utils`) and delivery mechanisms
  (`web`, `api`).
- Never mix (`DCA-USE-014`). Introducing features into a flat context moves **all** its use cases in one refactoring.
- `application/shared/` stays context-wide in both forms — never create `application/{feature}/shared/`.
- A vertical slice `{context}/{feature}/{domain,application,adapter}` is **not** a feature (layer stays above
  feature); refuse, point to the context mode.

### Generated files

In `src/main/java/{basePackage}/{context}/application/{usecasename}/` (lowercase, no separator) — or
`application/{feature}/{usecasename}/` in a grouped context. C#: `Application/{Name}/` (PascalCase folder = last
namespace segment) or `Application/{Feature}/{Name}/`.

| File (Java / C#) | Generated from | Notes |
|---|---|---|
| `{Name}InputPort.java` / `I{Name}InputPort.cs` | `templates/use-case/InputPort.{java,cs}.tmpl` | Interface extending `UseCase<{Name}Command|Query, {Name}Result>` / `IUseCase<…>` (async: `Task<TOut> ExecuteAsync(TIn, CancellationToken)`) |
| `{Name}Command` _or_ `{Name}Query` | `templates/use-case/Command.*.tmpl` / `Query.*.tmpl` | Record with the fields the user named (`sealed record` in C#) |
| `{Name}Result` | `templates/use-case/Result.*.tmpl` | By the context's refusal style (above): returned with refusals — the closed result, the success case `{{SuccessCase}}` and one case per refusal implementing `Refusal` / `IRefusal`; otherwise a record with the result fields and a static `from(...)`/`From(...)` factory. Values only — no aggregate root or entity, also not via `List<T>`/`Optional<T>` / `IReadOnlyList<T>`/`T?` (`DCA-USE-015`); part records named by content, never `*Result`; a command's result stays small (ids, status, next step) |
| `{Name}{ImplSuffix}` | `templates/use-case/UseCase.*.tmpl` | Java: annotations/imports from the resolved preset and transaction mode. C#: plain class, registered in `Add{Context}Context()`; writes wrap load–mutate–save–publish in `ITransactionBoundary.InTransactionAsync`. ImplSuffix from convention discovery (default `UseCase`, but can be `ApplicationService`, etc.) |

### Wiring

- Constructor injection of every output port (named or detected)
- A `// TODO: implement` body whose steps name the refusal style (return the case, or throw the use-case exception)
- Lombok `@RequiredArgsConstructor` where the project uses lombok, else an explicit constructor
- C#: add the `services.AddScoped<I{Name}InputPort, {Name}UseCase>()` line to the context's `Add{Context}Context()`

Named output ports that don't exist yet: create them in `application/shared/` (`Application/Shared/`) as interfaces extending `Repository` or `OutputPort` (`IRepository` / `IOutputPort`, async methods) depending on intent.

### Naming check

Name outside the project's verb pattern (`placeOrder` vs `orderPlace`) → warn, proceed as asked.

### DTO mapping at the adapter boundary

Use cases speak `Command`/`Query`/`Result`; adapters speak DTOs, `@Entity` types, messages. Map **at the adapter
boundary only**. Read `reference/dto-mapping.md` before writing an adapter's mapping.

---

## Mode aggregate

### Required parameters

- **Context**; **name** in PascalCase, a glossary term (a new term enters via `ubiquitous-language` first)
- **ID type** — UUID, sequence or natural key: ask
- Optional initial fields

### Generated files

In `src/main/java/{basePackage}/{context}/domain/model/` (C#: `Domain/Model/`):

| File (Java / C#) | Notes |
|---|---|
| `{Name}.java` / `{Name}.cs` | `extends BaseAggregateRoot<{Name}, {Name}Id>` / `: AggregateRootBase<{Name}, {Name}Id>`. Has `id()` / `Id`, factory `create(...)` / `Create(...)`, and a TODO for business methods. The C# aggregate is synchronous — the domain never awaits. |
| `{Name}Id.java` / `{Name}Id.cs` | Java record `implements Id` / C# `readonly record struct : IId`. Type matches the chosen ID type (UUID/Long/String — `Guid`/`long`/`string`). |
| `{Name}Created` (in `domain/event/` / `Domain/Event/`) | Record implementing `DomainEvent` / `IDomainEvent`. Has `aggregateId`, `occurredAt` (C#: `EventId`, `OccurredOn`, `AggregateId` + `Now(...)` factory). |

In `src/main/java/{basePackage}/{context}/application/shared/` (C#: `Application/Shared/`):

| File | Notes |
|---|---|
| `{Name}Repository.java` / `I{Name}Repository.cs` | Interface `extends Repository<{Name}, {Name}Id>` / `: IRepository<{Name}, {Name}Id>`. Java declares `findById`, `save`; the C# base interface already carries `FindByIdAsync`, `SaveAsync`. |

**Ask whether the aggregate belongs to someone** (an account, a tenant, a guest identity). If it does, ask for the
owner's id type, add `implements Owned<{OwnerId}>` / `, IOwned<{OwnerId}>` to the aggregate, and declare a lookup by
id and owner id on the repository (`Optional<{Name}> findByIdFor{Owner}({Name}Id id, {OwnerId} owner)` /
`Task<{Name}?> FindByIdFor{Owner}Async(...)`) — `DCA-TAC-026` asks for it. If nobody owns it, generate neither.

Lombok in the project → `@Getter`, `@AllArgsConstructor`; else explicit accessors.

### The domain type itself is `dca-modelling`'s

Generated: a `create(...)` factory emitting `{Name}Created`; `domainEvents()`/`clearDomainEvents()` (inherited
from `BaseAggregateRoot` if present); a `// TODO: invariants and business methods`.

Named invariants and behaviour → call `dca-modelling` (invariants, events per transition, a named
`DomainException` subtype per refused rule). This mode writes no business method, setter or exception type — a
failure's name comes from the rule, not a template.

---

## Mode store

Instead of a Repository when the persisted data has no aggregate lifecycle.

### Decision: Store or Repository?

Confirm with the user:

| If the stored object… | Use |
|---|---|
| has identity, gets loaded by ID, mutated, saved back | **Repository** (Mode aggregate generates this for aggregate roots) |
| is appended/recorded; queried by aggregate (count, exists, sum) | **Store** (this mode) |
| is a Value Object or `record` | almost always **Store** |

By lifecycle; lookup by id does not decide.

### Required parameters

- **Context**; **store name** (`LoginProtection` → `LoginProtectionStore`); **stored type** (value object / record /
  event, e.g. `LoginAttempt`); **query methods** — the aggregate questions it answers (`countRecentFailures`, `isBlocked`)

### Generated files

In `src/main/java/{basePackage}/{context}/application/shared/`:

- `{Name}Store.java` (from `templates/store/Store.java.tmpl`) — interface `extends Store`. Has `record(...)` plus the user-named query methods.
- C#: `I{Name}Store.cs` (from `templates/store/Store.cs.tmpl`) — `: IStore` with `RecordAsync(...)` and async query methods, in `Application/Shared/`.

A Store may expose lookup by key (`findById` / `FindByIdAsync`). Do not generate aggregate `save` or `delete` lifecycle methods.

### Anti-pattern guard

`*Repository` for a value object or record → recommend this mode. A Store for an aggregate root → recommend the aggregate mode.

---

## Mode domainservice

Domain layer, framework-free, ubiquitous-language name; for a rule spanning several aggregates that none may
drive. **The application calls it**; it **takes the aggregates as parameters**, never values pulled out of them.
Facts the domain does not own may be passed alongside.

### Decision: is it a domain service?

Confirm with the user:

| If the logic… | Then |
|---|---|
| decides across two or more aggregates (or an aggregate and entities of another) | **domain service** (this mode) |
| computes on one aggregate or one value object alone | a method on that aggregate or value object — `dca-modelling`, no service |
| needs facts the model does not hold, and the domain itself must ask for them | a domain gateway beside the model — `dca-modelling`; it never writes to the outside |
| exists only because a use case got long | no domain service; the use case is split instead |

`*Manager`/`*Helper` is a technical bucket — ask for the domain's word. `*Service` is fine where the business
says it.

### Required parameters

- **Context**; **name** in PascalCase from the glossary (a new term via `ubiquitous-language` first)
- **The operation:** its name, **the aggregates it takes** (at least one aggregate or entity parameter), the
  facts passed alongside, and the result type (a value object or a result record, never a changed foreign
  aggregate)

### Generated files

In `src/main/java/{basePackage}/{context}/domain/service/` (C#: `Domain/Service/`):

| File (Java / C#) | Generated from | Notes |
|---|---|---|
| `{Name}.java` / `{Name}.cs` | `templates/domain-service/DomainService.{java,cs}.tmpl` | `final class … implements DomainService` / `sealed class … : IDomainService`. Stateless (only `final` / `readonly` collaborator fields), no framework annotation or attribute, synchronous in C#. One operation with the aggregates as parameters and a TODO body |

The marker is the project's `DomainService` — `dev.domaincentric.dca.buildingblocks.ddd.tactical.DomainService` /
`DomainCentric.BuildingBlocks.Ddd.Tactical.IDomainService` unless the conventions name an alias.

### Wiring

- **The use case calls it**, after loading the aggregates, before saving them. Wired like the project's other
  collaborators: constructed in the use case, or registered in configuration where the preset has a container —
  never by annotating the service.
  C#: `services.AddSingleton<{Name}>()` in the context's `Add{Context}Context()`.
- **No aggregate, entity or value object constructs or calls it.** Asked for → explain, place the call in the use case.

### The rule itself is `dca-modelling`'s

Call `dca-modelling` for the body: the rule, the named failure on refusal, the events the aggregates register.
No business logic here.
