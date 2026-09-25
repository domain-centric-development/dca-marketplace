---
name: dca-new
disable-model-invocation: true
description: |
  Creates new Domain-Centric Architecture (DCA) code in Java/Spring or .NET/C#, in six modes: `project` (an
  empty directory becomes a runnable DCA project — skeleton from Spring Initializr or `dotnet new`, git,
  then dca-init and dca-add), `context` (a bounded context), `usecase` (Command/Query + InputPort + Result +
  implementation), `aggregate` (aggregate root with Id, Repository and Created event), `store` (an
  operational store port) and `domainservice` (a domain service on the DomainService marker). Use when the
  user asks to "start a new DCA project", "create a new bounded context", "scaffold a use case", "add an
  aggregate root", "add a domain service", or "/dca-new". Adapts to existing project conventions: reads the
  project's DcaLayout (architecture test) and conventions file, plus existing code style. Never overwrites
  files.
---

# dca-new

Creates what is new, in one of six modes — in **Java** (Spring) or **C#** (.NET). Templates exist for both:
`*.java.tmpl` and `*.cs.tmpl` side by side.

| Mode | Creates | From |
|---|---|---|
| `project` | a runnable DCA project in an empty directory | a generator, then `dca-init` and `dca-add` |
| `context` | a bounded context: package tree and its declaration | `templates/bounded-context/` |
| `usecase` | input port, command or query, result, implementation | `templates/use-case/` |
| `aggregate` | aggregate root, id, created event, repository port | `templates/aggregate/`, then `dca-modelling` |
| `store` | an operational store port | `templates/store/` |
| `domainservice` | a domain service on the `DomainService` marker | `templates/domain-service/`, then `dca-modelling` |

The code modes lay out files and wiring. The domain types themselves — the invariants, the behaviour, the
events at the right transition — are the craft of `dca-modelling`; `aggregate` and `domainservice` call it
for that part, so the building guide lives in one place. The invariants while editing are `dca-discipline`'s.

## Sub-operations

The user's wording determines which mode:

- **"new project"** / "start a DCA project" / an empty directory → [Mode project](#mode-project)
- **"new bounded context X"** / "create context X" / "scaffold X module" → [Mode context](#mode-context)
- **"use case X"** / "create X use case" → [Mode usecase](#mode-usecase)
- **"aggregate X"** / "aggregate root X" / "create domain entity X" → [Mode aggregate](#mode-aggregate)
- **"store for X"** / "operational store" → [Mode store](#mode-store)
- **"domain service X"** / "a rule across X and Y" → [Mode domainservice](#mode-domainservice)

If unclear, ask the user — through a structured question tool where the harness has one, in prose otherwise.

**Never overwrite an existing file.** If a target path exists, stop and ask.

---

## Mode project

**User intent:** "Start a new DCA project here."

Only for a directory without a build file (`build.gradle(.kts)`, `pom.xml`, `*.sln`, `*.slnx`, `*.csproj`). It
may already hold a project description, an `AGENTS.md` or a `.git`. A directory with a build file is an
existing project: point to `dca-init` instead.

### 1. The decisions come from the project description

Read `AGENTS.md`: the section between `<!-- dca-describe: start -->` and `<!-- dca-describe: end -->` names the
technical and the product description (`- tech:`, `- product:`; `project/tech.md` and `project/product.md` by
default). Where there is none, its entries are all open and asked in the one pass below; `dca-describe` then
writes the description from those answers and never invents one. Take from it:

- **the stack** — Spring Boot (Gradle or Maven, the Java line) or .NET (the SDK line);
- **the frontend approach** — server-rendered pages, a client application, or none;
- **the surfaces** — web pages, an HTTP API, a command line, events; which of them has pages decides the
  browser runner (step 6);
- **the persistence** — a data starter or package now, or in-memory until a later story.

**Every question in one pass, from the catalogue.** `reference/questions.md` lists every decision this mode
needs — the description's open entries (`dca-describe`'s catalogue), this mode's own (base package, formatter
style, browser runner, selector attribute, how the suite reaches the application) and `dca-init`'s entries
that apply to an empty directory — each with where its answer is looked up first. Look every answer up, then
ask **only the open ones — all at once, before the generator runs, in catalogue order, word for word**, with
the options and the default the catalogue gives; through a structured question tool where the harness has
one, in prose otherwise. Ask nothing the catalogue does not list, and nothing later in the run: a question
halfway stops the run with a skeleton on disk.

An answer goes where the catalogue says: a description entry into the description through `dca-describe`;
the formatter and browser answers to `dca-add formatter` and `dca-add browser`, which record them in the build
file and the conventions file; the rule sets to `dca-init`.

### 2. The skeleton comes from a generator

Versions, dependency ids and project layout come from the generator, never from memory — training data is
older than the current releases.

- **Spring Boot — Spring Initializr.** Read the metadata first: `curl -s -H 'Accept:
  application/vnd.initializr.v2.2+json' https://start.spring.io` lists the current Boot versions (take the
  default), the Java versions, the project types (`gradle-project`, `gradle-project-kotlin`,
  `maven-project`) and the dependency ids. Then generate into the directory:

  ```bash
  curl -s https://start.spring.io/starter.tgz \
    -d type=gradle-project -d language=java -d bootVersion=<default from the metadata> \
    -d javaVersion=<from the description or the metadata default> \
    -d groupId=<group> -d artifactId=<artifact> -d name=<name> -d packageName=<base package> \
    -d dependencies=<ids from the metadata: the web stack for the surfaces, a template engine for
    server-rendered pages, the data starter the description names> | tar -xzf -
  ```

  The base package is the one `dca-init` records as `DcaLayout.forBasePackage`.
- **.NET — `dotnet new`.** The installed SDK is the generator: check its line with `dotnet --list-sdks`
  against the description's version policy and say so when it is older. Create the solution and the host
  project from the template the frontend approach names (`web`, `webapp`, `mvc`, `webapi`), plus a unit-test
  project:

  ```bash
  dotnet new sln -n <Name>
  dotnet new <template> -n <Name>.Web -o src/<Name>.Web
  dotnet new xunit -n <Name>.Tests -o tests/<Name>.Tests
  dotnet sln add src/<Name>.Web tests/<Name>.Tests
  ```
- **Offline fallback (Java).** Where start.spring.io cannot be reached, write the Gradle build from
  `reference/greenfield-java-build.md` — Boot 4 renamed the web starter, split the test starters per slice and
  moved the slice annotations into technology packages, which training data does not know. The versions then
  come from Maven Central or from the person, still never from memory.

### 3. Git

`git init` where the directory has no repository, and a `.gitignore` for the build's outputs — Java/Gradle
`.gradle/` and `build/`, Maven `target/`, .NET `bin/`, `obj/` and `TestResults/`, plus `.idea/`, `.vs/`,
`*.iml`. A generator's `.gitignore` (Initializr ships one; `dotnet new gitignore` writes one) is kept: add only
the lines it lacks. Commit nothing — the first commit is the person's, after the proof.

### 4. The DCA part: `dca-init`

Run `dca-init` on the fresh skeleton. It adds the building blocks and rule packages, the architecture test with
`DCA-STR-012` on `warn` (no domain code yet — empty means green), the conventions file and the method's
section of `AGENTS.md`. Hand it the contexts `project/domain.md` names, so their roots are declared from the
start.

### 5. The formatter: `dca-add formatter`

Every project gets its formatter now, while the code base is only the skeleton — the one formatting run is
then trivial, and every later change touches only what it wrote.

### 6. The browser runner: `dca-add browser`

When the product description names a surface with pages (server-rendered or a client application), run
`dca-add browser`. It sets up the runner and one smoke test on the start page before the first feature, so the
first story's end-user test has something to run on.

### 7. Proof

The project is done when all three hold — show each:

- **It starts.** `./gradlew bootRun` / `mvn spring-boot:run` / `dotnet run --project src/<Name>.Web`, one
  request to `/` answers, then stop it.
- **Every suite is green.** `./gradlew build` (runs `check`, `test-architecture` included) and the browser
  suite (`./gradlew test-e2e`, `mvn verify`); `dotnet build` and `dotnet test` (Debug). The expected entries
  of a project without domain code — `DCA-STR-012` on `warn`, a freshly generated context map — are named,
  not hidden.
- **The browser smoke test can fail.** Empty the start page's `<title>`, run the browser suite, see it red,
  restore the title, see it green. A browser suite that stays green while the page is broken tests nothing.

### Report

The report is read from the disk, so it has the same sections and fields every time — Stack · Generator ·
DCA part · Formatter · Browser runner · Proof · Git · Open. Run `dca-init`'s report script from the project
root, with the generator you used and the result of each proof step:

```bash
python3 <dca-init skill folder>/scripts/dca-report.py --mode new --generator "start.spring.io" \
  --proof start=passed --proof suites=passed --proof smoke=passed
```

(`--generator "dotnet new"` or `"offline reference"`; a proof step that failed is `failed`, one not run is left
out and shows as open.) Show the output as it is and add nothing after it but this one line:

```
Next: the first commit is yours — then /factory-setup and /factory-backlog for a delivery pipeline, or /dca-new context | usecase | aggregate by hand.
```

---

## Convention discovery (run before every code mode)

```bash
# 1. The project's DcaLayout — the architecture test is the single source of the layout conventions
grep -rn "DcaLayout\." --include='*.java' --include='*.cs' . | grep -v '/build/\|/bin/\|/obj/'
```

If found: `Read` the test. The `DcaLayout` builder chain **is** the convention list — every `with…`/`With…`
call is a deviation from the DCA default:
- `forBasePackage("com.acme.shop")` / `ForRootNamespace("Acme.Shop")` → `{{basePackage}}` / `{{rootNamespace}}`
- `withIncomingSubpackage("in")`, `withOutgoingSubpackage("out")` / `WithIncomingSegment`, `WithOutgoingSegment`
  → adapter sub-folders
- `withUseCaseSuffix("ApplicationService")` / `WithUseCaseSuffix(...)` → `{{useCaseImplSuffix}}`
- `withRestControllerSuffix(...)` / `WithRestControllerSuffix(...)` → REST adapter suffix
- `withDomainSubpackage`, `withApplicationSubpackage`, `withAdapterSubpackage` (rare) → layer names

The marker types are the library's (`dev.domaincentric.dca.buildingblocks.…` / `DomainCentric.BuildingBlocks.…`).
The conventions file — the one the `AGENTS.md` line ``- conventions: `<path>` `` names, `.agents/dca/conventions.md`
by default, `.claude/dca/conventions.md` in older projects — may override any of it. Also read
`dca-archunit.properties` (test class path / next to the test assembly) — a rule set switched off there tells
you which patterns the project deliberately does not use (e.g. no `tactical` → do not lay out a rich aggregate
without asking).

If no architecture test exists: scan the project directly:
```bash
# Java — existing aggregate root style, use case style, adapter folders
grep -rln --include='*.java' -E 'extends BaseAggregateRoot|implements AggregateRoot' src/main/java
grep -rln --include='*.java' -E 'implements\s+\w+UseCase|class\s+\w+(UseCase|ApplicationService)' src/main/java
find . -type d \( -name incoming -o -name outgoing -o -name in -o -name out \) -path '*/adapter/*' -not -path '*/build/*'

# C# — same questions
grep -rln --include='*.cs' -E ': AggregateRootBase<|: IAggregateRoot<' src
grep -rln --include='*.cs' -E ': I\w+InputPort|class \w+(UseCase|ApplicationService)\b' src
find . -type d \( -name Incoming -o -name Outgoing -o -name In -o -name Out \) -path '*/Adapter/*' -not -path '*/bin/*' -not -path '*/obj/*'
```

Build a `conventions` summary and (if anything is ambiguous) confirm with the user before generating. Generate
code that matches what's already there. Don't impose DCA defaults if the project follows different (but
consistent) conventions.

---

## Mode context

**User intent:** "Add a new bounded context called `orders`."

> Pattern choice per subdomain decides whether to lay out the full tactical structure — read the subdomain
> type in the designed map (`project/domain.md`, or the path the `AGENTS.md` line names) and check for a
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
6. **Verify:** run the architecture tests if they exist. The new (empty) context should not break anything.

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

#### Responsibility ownership

| Direction | Adapter type | Maps | Lives in |
|---|---|---|---|
| **In →** | `*Resource` (REST), `*Controller` (MVC), `*EventConsumer` | request DTO → `*Command`/`*Query` | `adapter/incoming/...` |
| **In ←** | same as above | `*Result` → response DTO (`*Response`, `*ViewModel`) | `adapter/incoming/...` |
| **Out →** | `*Repository` implementation, `*EventPublisher` implementation | Domain (`Order`, `OrderPlacedEvent`) → JPA entity / `*IntegrationEvent` / persistence record | `adapter/outgoing/...` |
| **Out ←** | same as above | JPA entity / row → Domain (`Order`) | `adapter/outgoing/...` |

#### Decision: inline mapping or a dedicated `*Converter` class

```
If (command shape ≈ request DTO shape, ≤ 5 fields, no transformation):
    map inline in the controller
    → no mapper file, no indirection

If (shapes diverge, validation / lookup / default calculation needed):
    a dedicated *Converter in the same adapter folder
    → e.g. adapter/incoming/api/PlaceOrderRequestConverter.java

If (several resources map similar structures):
    a shared converter in adapter/incoming/api/mapper/
    → extract only when the third place needs it (rule of three)
```

#### Example: REST inbound (inline)

```java
@RestController
@RequestMapping("/orders")
class OrderResource {

    private final PlaceOrderInputPort placeOrder;

    @PostMapping
    PlaceOrderResponse place(@RequestBody @Valid PlaceOrderRequest req) {
        var cmd = new PlaceOrderCommand(
            new CustomerId(req.customerId()),
            req.items().stream().map(i -> new LineItem(new ProductId(i.productId()), i.quantity())).toList(),
            new Address(req.shipping().street(), req.shipping().city())
        );
        var result = placeOrder.execute(cmd);
        return new PlaceOrderResponse(result.orderId().value(), result.placedAt(), result.totalAmount().amount());
    }
}

record PlaceOrderRequest(String customerId, List<LineItemDto> items, AddressDto shipping) {}
record PlaceOrderResponse(UUID orderId, Instant placedAt, BigDecimal totalAmount) {}
```

#### Example: REST inbound with a dedicated converter

```java
@RestController
class OrderResource {
    private final PlaceOrderInputPort placeOrder;
    private final PlaceOrderRequestConverter converter;

    @PostMapping("/orders")
    PlaceOrderResponse place(@RequestBody @Valid PlaceOrderRequest req) {
        var result = placeOrder.execute(converter.toCommand(req));
        return converter.toResponse(result);
    }
}

// adapter/incoming/api/PlaceOrderRequestConverter.java
@Component
class PlaceOrderRequestConverter {
    PlaceOrderCommand toCommand(PlaceOrderRequest req) { ... }
    PlaceOrderResponse toResponse(PlaceOrderResult result) { ... }
}
```

#### Example: outbound (repository implementation)

```java
// adapter/outgoing/persistence/JpaOrderRepository.java
@Component
class JpaOrderRepository implements OrderRepository {

    private final JpaOrderEntityRepository jpa;

    @Override
    public Optional<Order> findById(OrderId id) {
        return jpa.findById(id.value()).map(this::toDomain);
    }

    @Override
    public void save(Order order) {
        jpa.save(toEntity(order));
    }

    private Order toDomain(OrderEntity entity) { ... }
    private OrderEntity toEntity(Order order) { ... }
}

@Entity @Table(name = "orders")
class OrderEntity { /* JPA fields, accessors, @Id, @Column ... */ }
```

#### Anti-patterns

- **The aggregate as the REST response** — leaks the domain's shape to clients (`Order` as the JSON answer). Always map to a `*Response` record in the adapter.
- **`*Command`/`*Query`/`*Result` as a JPA `@Entity`** — breaks the framework-free domain and application and mixes two lifecycles (use-case input and persistence row).
- **Mapping logic in the use case** — when `PlaceOrderUseCase` constructs a `PlaceOrderRequest` or builds a `*Response`, the boundary has moved. Mappers belong in `adapter/`.
- **One `*Dto` shared by request *and* persistence** — the same record serves two roles; every change on one side forces the other. Prefer two separate records with explicit mapping.
- **A mapper in `application/` or `domain/`** — mapping is an adapter concern.
- **A domain event as the Kafka payload** — domain events stay inside the context. Across contexts it is an `*IntegrationEvent` (schema version in `IntegrationEventType`; a business `version` stays allowed), mapped in the `adapter/outgoing/event/` publisher.

The complete wiring picture is `dca-review`'s reference `use-case-pattern.md` (section 4, "Adapter wiring: who calls
what?"), the adapter naming table its `naming-conventions.md` (section "Adapter layer").

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

---

## Templates and substitutions

See `templates/` for the actual `.java.tmpl` and `.cs.tmpl` files — one twin per artefact, pick by language.

Common placeholders:
- `{{basePackage}}`, `{{context}}` — base package + bounded context name (Java, lowercase)
- `{{rootNamespace}}`, `{{Context}}`, `{{contextDisplayName}}` — root namespace + PascalCase context segment + the
  display name in `[BoundedContext("…")]` (C#)
- `{{FeatureSegment}}`, `{{IncomingSegment}}`, `{{OutgoingSegment}}` — PascalCase twins of the Java segments (C#)
- `{{usecasename}}` (lowercase, no separator) — for use case folder
- `{{featureSegment}}` — empty in a flat context, `{feature}.` in a grouped one (so the package reads `application.{{featureSegment}}{{usecasename}}`)
- `{{Name}}` — PascalCase name (e.g. `PlaceOrder`, `Order`, `TransferPolicy`)
- `{{commandOrQuery}}` — `Command` or `Query`
- `{{useCaseImplSuffix}}` — `UseCase` (default) or `ApplicationService` etc.
- `{{aggregateRootMarker}}` — short class name to use (`BaseAggregateRoot` if available, else `AggregateRoot`)
- `{{repositoryMarker}}`, `{{storeMarker}}`, `{{useCaseMarker}}`, `{{idMarker}}` etc. — short names
- `{{storedType}}`, `{{StoredType}}`, `{{queryMethods}}` — for Mode store
- `{{domainServiceMarkerFqn}}`, `{{serviceDescription}}`, `{{operation}}` / `{{Operation}}`, `{{operationParameters}}`,
  `{{ResultType}}`, `{{aggregateList}}`, `{{domainImports}}` / `{{domainUsings}}` — for Mode domainservice
- `{{incomingSubfolder}}`, `{{outgoingSubfolder}}` — `incoming` (default) or `in`
- `{{useLombok}}` — `true` / `false` based on project convention

## Idempotency check

Before any write:
```
if Path(target).exists():
    ask user: "{path} already exists. Overwrite / skip / abort?"
    default action: skip
```

## After a code mode

Run the architecture tests if they exist:
```bash
./gradlew test-architecture     # Java (the source set dca-init installs), otherwise ./gradlew :{context}:test
dotnet test tests/*.ArchitectureTests   # .NET (Debug build — ArchUnitNET needs it)
```

When this run created the project's first `domain`, `application` or `adapter` package and
`dca-archunit.properties` carries `dca-init`'s `dca.rules.warn = DCA-STR-012` entry, remove that entry and its
comment block before running the tests, so the rule is enforced from now on. Leave any other `warn` entries
untouched.

Any failures should be findings, not skill bugs. Print:
```
✓ Created {N} files for {mode}
  - Files: {list}
  - Tests: {pass count} / {total}

Next:
  - Implement business logic in {primary file} (dca-modelling for domain types)
  - Wire output ports in the use case impl (look for TODO comments)
```

## Anti-patterns

- **Don't write business logic.** The skill lays out structure; `dca-modelling` and the user's domain expertise fill it.
- **Don't impose conventions** the project doesn't follow. If they use `*ApplicationService`, create `*ApplicationService` — not `*UseCase`.
- **Don't auto-generate Repository methods beyond `findById`/`save`.** Specific finders are project decisions.
- **Don't add Spring `@Component` to domain classes.** Domain stays framework-free (DCA invariant). Same in C#: no
  `[Table]`, no ASP.NET or EF Core attribute in `Domain/`.
- **Don't generate package-info.java for sub-packages** (only for the bounded context root) — keeps the tree clean.
  C#: one `{Context}Context` marker class per context, never per layer.
- **Don't make the C# domain async.** Ports are `Task`-based; aggregates, value objects and domain services stay
  synchronous — a rule of the .NET catalog enforces it.
- **Don't create a domain service that takes values pulled out of an aggregate.** That moves the rule out of the
  domain by the back door; it takes the aggregate.
- **Don't write a project skeleton from memory** while a generator is reachable, and don't take a version from
  memory at all.

Respect `withOperationContainers(...)` / `WithOperationContainers(...)` when a layout
configures organisational folders. Keep one normalized operation depth per context.
Place a port used by one operation beside it; shared is the reuse default.

## Resolved configuration

Read the shared resolved-configuration contract — `dca-init`'s reference `resolved-configuration.md`. `dca-init`
writes the section for every project; this skill reads and refreshes it from the resolved preset before filling
annotation/import placeholders. `none` uses explicit constructor wiring and `Configuration.java.tmpl`, without
framework imports.
