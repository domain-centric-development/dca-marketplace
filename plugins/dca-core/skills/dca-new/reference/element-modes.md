# The element modes — context, usecase, aggregate, store, domainservice

Part of the `dca-new` skill: what its *Mode context* … *Mode domainservice* steps point to — the parameters, the
placement, the generated files per language, the wiring and the decision tables of every code mode.

## Mode context

**User intent:** "Add a new bounded context called `orders`."

> Pattern choice per subdomain decides whether to lay out the full tactical structure — read the subdomain
> type in the designed map (`domain:` in `dca.profile.yaml`, `product/domain.md` by default) and check for a
> pattern-selection ADR (e.g. `docs/adr/`) before creating a full DDD context; supporting/generic subdomains
> may warrant a simpler layout. A context the designed map does not carry is a question about the description
> (`dca-describe`), not something to add silently.

### Steps

1. **Validate:** the context name must be lowercase, single word (no hyphens). E.g. `orders`, `inventory`. If hyphenated, the user means a multi-word concept — ask whether to use `customeraccount` (concatenated) or `customer-account` (Gradle module name) — these are different.
2. **Decide install location.** Two common patterns:
   - **Single-module project:** create the package directly under `src/main/java/{basePackage}/{context}/`
     (C#: the namespace `{rootNamespace}.{Context}` inside the existing project).
   - **Multi-module Gradle:** create a new sub-project `{context}/` with its own `build.gradle.kts`. Ask the user which mode applies.
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
7. **Verify:** run the architecture tests if they exist. The new (empty) context should not break anything.

---

## Mode usecase

**User intent:** "Add a `placeOrder` use case to the `orders` context."

### Required parameters (ask if not given)

- **Context** the use case lives in (e.g. `orders`)
- **Use-case name** in lowerCamelCase (e.g. `placeOrder`, `getOrderById`)
- **Type:** Command (write — modifies state) or Query (read — pure data fetch)
- **Output ports needed:** which existing repositories/data ports does it need? Or create a fresh `*Repository` if a new aggregate is in play.

### Placement: flat or feature-grouped context

Before writing, look at the packages directly below `{context}/application/` (ignore `shared`):

```bash
find src/main/java/{basePackage//.//}/{context}/application -mindepth 1 -maxdepth 1 -type d -not -name shared
```

- If those folders contain use cases directly (`*InputPort`, `*UseCase` files) → the context is **flat**: the
  new use case goes to `application/{usecasename}/`.
- If they contain further folders which hold the use cases → the context is **grouped by feature**
  (`application/{feature}/{usecasename}/`). A *feature* is an optional, domain-named group of related use cases —
  a navigation boundary below the layer, not a module or aggregate owner. Ask the user which feature the new use
  case belongs to (offer the existing ones); if none fits, take a new lowercase name **from the ubiquitous
  language** (`cartrecovery`, `checkoutcompletion`). Reject technical buckets (`commands`, `queries`, `handlers`,
  `services`, `utils`) and delivery mechanisms (`web`, `api`) as feature names.
- Never mix: a flat use case in a grouped context (or vice versa) violates `DCA-USE-014`. If the user wants to
  *introduce* features into a flat context, move **all** its use cases in one refactoring, not just the new one.
- `application/shared/` stays context-wide in both forms — never create `application/{feature}/shared/`.
- A vertical slice `{context}/{feature}/{domain,application,adapter}` is **not** a feature (the layer must stay
  above the feature); refuse to create it and point to the context mode instead.

### Generated files

In `src/main/java/{basePackage}/{context}/application/{usecasename}/` (lowercase, no separator) — or
`application/{feature}/{usecasename}/` in a grouped context. C#: `Application/{Name}/` (PascalCase folder = last
namespace segment) or `Application/{Feature}/{Name}/`.

| File (Java / C#) | Generated from | Notes |
|---|---|---|
| `{Name}InputPort.java` / `I{Name}InputPort.cs` | `templates/use-case/InputPort.{java,cs}.tmpl` | Interface extending `UseCase<{Name}Command|Query, {Name}Result>` / `IUseCase<…>` (async: `Task<TOut> ExecuteAsync(TIn, CancellationToken)`) |
| `{Name}Command` _or_ `{Name}Query` | `templates/use-case/Command.*.tmpl` / `Query.*.tmpl` | Record with the fields the user named (`sealed record` in C#) |
| `{Name}Result` | `templates/use-case/Result.*.tmpl` | Record with the result fields and a static `from(...)`/`From(...)` factory. Values only — no aggregate root or entity, also not via `List<T>`/`Optional<T>` / `IReadOnlyList<T>`/`T?` (`DCA-USE-015`); part records named by content, never `*Result`; a command's result stays small (ids, status, next step) |
| `{Name}{ImplSuffix}` | `templates/use-case/UseCase.*.tmpl` | Java: annotations/imports from the resolved preset and transaction mode. C#: plain class, registered in `Add{Context}Context()`; writes wrap load–mutate–save–publish in `ITransactionBoundary.InTransactionAsync`. ImplSuffix from convention discovery (default `UseCase`, but can be `ApplicationService`, etc.) |

### Wiring

The implementation gets:
- Constructor injection of all needed output ports (declared explicitly by the user or detected)
- A `// TODO: implement` body — the skill doesn't try to write business logic
- Proper imports (using project conventions: lombok `@RequiredArgsConstructor` if project uses lombok elsewhere; otherwise explicit constructor)
- C#: add the `services.AddScoped<I{Name}InputPort, {Name}UseCase>()` line to the context's `Add{Context}Context()`

If the user named output ports that don't exist yet, create them in `application/shared/` (`Application/Shared/`) as interfaces extending `Repository` or `OutputPort` (`IRepository` / `IOutputPort`, async methods) depending on intent.

### Naming check

If the user's name doesn't follow the project's verb pattern (`placeOrder` vs `orderPlace`), gently warn but proceed with what they asked for.

### DTO mapping at the adapter boundary

Use cases speak `Command`/`Query`/`Result` records. Adapter framework code speaks request DTOs, response DTOs,
JPA `@Entity` types, Kafka records etc. Mapping happens **at the adapter boundary only** — never in the use
case, never in the domain.

Read `reference/dto-mapping.md` before writing an adapter's mapping: which adapter maps which direction,
when to map inline and when a `*Converter` earns its file, an inbound and an outbound example, and the
anti-patterns (the aggregate as the REST response, a `*Command` as a JPA entity, mapping in the use case).

---

## Mode aggregate

**User intent:** "Create an `Order` aggregate root in the `orders` context."

### Required parameters

- **Context** (e.g. `orders`)
- **Aggregate name** in PascalCase (e.g. `Order`) — a term of the context's glossary; a new term enters the
  glossary through `ubiquitous-language` first
- **ID type:** auto-generated UUID, sequence number, or natural key — ask
- **Optional:** initial fields the user knows (e.g. `customerId`, `placedAt`)

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

If the project uses lombok: use `@Getter`, `@AllArgsConstructor` etc. Otherwise explicit accessors.

### The domain type itself is `dca-modelling`'s

The templates lay out the structure. The generated aggregate has:
- A `create(...)` static factory that emits a `{Name}Created` event
- Empty `domainEvents()` and `clearDomainEvents()` (or inherit from `BaseAggregateRoot` if present)
- A `// TODO: invariants and business methods` placeholder

Where the user names the invariants and behaviour, call `dca-modelling` for them: it holds how an aggregate
enforces an invariant, which events it registers at which transition, and how a refused rule gets its own
named `DomainException` subtype beside the aggregate. This mode generates no business method, no setter and no
exception type of its own — a failure's name has to come from the rule, not from a template.

---

## Mode store

**User intent:** "Add a `LoginProtection` store to the `customeraccount` context."

A **Store** is the second persistence-shaped output port in DCA. Use this mode **instead of** the aggregate
mode's Repository when the data being persisted has no aggregate lifecycle.

### Decision: Store or Repository?

Before creating it, confirm with the user:

| If the stored object… | Use |
|---|---|
| has identity, gets loaded by ID, mutated, saved back | **Repository** (Mode aggregate generates this for aggregate roots) |
| is appended/recorded; queried by aggregate (count, exists, sum) | **Store** (this mode) |
| is a Value Object or `record` | almost always **Store** |

Choose by lifecycle: an aggregate collection uses a Repository; operational records use a Store. Lookup by id does not decide between them.

### Required parameters

- **Context** (e.g. `customeraccount`)
- **Store name** (e.g. `LoginProtection` — generates `LoginProtectionStore`)
- **Stored type:** the value object / record / event being stored (e.g. `LoginAttempt`)
- **Query methods:** what aggregate questions the Store answers (e.g. `countRecentFailures`, `isBlocked`)

### Generated files

In `src/main/java/{basePackage}/{context}/application/shared/`:

- `{Name}Store.java` (from `templates/store/Store.java.tmpl`) — interface `extends Store`. Has `record(...)` plus the user-named query methods.
- C#: `I{Name}Store.cs` (from `templates/store/Store.cs.tmpl`) — `: IStore` with `RecordAsync(...)` and async query methods, in `Application/Shared/`.

A Store may expose lookup by key (`findById` / `FindByIdAsync`). Do not generate aggregate `save` or `delete` lifecycle methods.

### Anti-pattern guard

If the user names the new port `*Repository` but the stored type is a Value Object or record, point that out and recommend this mode instead. Likewise, if the user asks for a Store but names the stored type as an aggregate root, recommend the aggregate mode.

---

## Mode domainservice

**User intent:** "Add a `TransferPolicy` domain service to the `accounts` context."

A domain service is part of the domain: it lives in the domain layer, framework-free,
named in the ubiquitous language. It exists for a rule that spans several aggregates, which no single aggregate
may drive — so **the application calls it**, and it **takes the aggregates as parameters**, not values pulled out
of them. Facts the domain does not own may be passed alongside.

### Decision: is it a domain service?

Confirm with the user before creating it:

| If the logic… | Then |
|---|---|
| decides across two or more aggregates (or an aggregate and entities of another) | **domain service** (this mode) |
| computes on one aggregate or one value object alone | a method on that aggregate or value object — `dca-modelling`, no service |
| needs facts the model does not hold, and the domain itself must ask for them | a domain gateway beside the model — `dca-modelling`; it never writes to the outside |
| exists only because a use case got long | no domain service; the use case is split instead |

A service named `*Manager` or `*Helper` is a technical bucket, not ubiquitous language — ask for the domain's
word. `*Service` is fine where the business says it (a pricing service).

### Required parameters

- **Context** (e.g. `accounts`)
- **Service name** in PascalCase, from the context's glossary (e.g. `TransferPolicy`); a new term enters the
  glossary through `ubiquitous-language` first
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

- **The use case calls it**, after loading the aggregates through their output ports and before saving them.
  It obtains the service the way the project wires its other collaborators: constructed in the use case or
  registered in configuration where the resolved preset has a container — never by annotating the service.
  C#: `services.AddSingleton<{Name}>()` in the context's `Add{Context}Context()`.
- **No aggregate, entity or value object constructs or calls it.** Where the user asks for that, explain why and
  place the call in the use case.

### The rule itself is `dca-modelling`'s

The template lays out the type. Call `dca-modelling` for the operation's body: the rule across the aggregates,
the named failure when it refuses, the events the aggregates register as a result. This mode writes no business
logic of its own.
