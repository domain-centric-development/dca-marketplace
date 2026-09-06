---
name: dca-scaffold
disable-model-invocation: true
description: |
  Scaffolds new Domain-Centric Architecture (DCA) code into Java/Spring projects: bounded
  contexts, use cases (Command/Query + InputPort + Result + Impl), and aggregate roots
  (with Id, Repository, and Created event). Use when the user asks to "create a new bounded
  context", "scaffold a use case", "add an aggregate root", "generate DCA structure for
  feature X", or "/dca-scaffold". Adapts to existing project conventions: reads BaseArchUnitTest
  constants (if dca-bootstrap was installed) and existing code style. Never overwrites files.
---

# dca-scaffold

Generates DCA-compliant code in three modes: **bounded context**, **use case**, **aggregate root**.

This is the second skill in the DCA suite. Use after `dca-bootstrap` has installed markers
and the ArchUnit governance — but `dca-scaffold` also works standalone (it adapts to the
project's existing conventions either way).

## Core principle: read first, generate second

Before generating anything, **inspect the project** to find:
1. Whether `dca-bootstrap` ran (look for `BaseArchUnitTest` — it encodes the conventions)
2. Otherwise: existing markers, layer naming, use-case-class suffix, lombok-or-records preference

Generate code that matches what's already there. Don't impose DCA defaults if the project
follows different (but consistent) conventions.

**Never overwrite an existing file.** If a target path exists, stop and ask.

## Sub-operations

The user's wording determines which mode:

- **"new bounded context X"** / "create context X" / "scaffold X module" → [Mode A: Bounded Context](#mode-a-bounded-context)
- **"use case X"** / "create X use case" / "scaffold create-order use case" → [Mode B: Use Case](#mode-b-use-case)
- **"aggregate X"** / "aggregate root X" / "create domain entity X" → [Mode C: Aggregate Root](#mode-c-aggregate-root)
- **"store for X"** / "operational store" / "scaffold a Store" → [Mode D: Store](#mode-d-store)

If unclear, ask via `AskUserQuestion`.

---

## Convention discovery (run before any mode)

```bash
# 1. Check for BaseArchUnitTest — if present, read it for the canonical project conventions
find . -name 'BaseArchUnitTest.*' -not -path '*/build/*' -not -path '*/target/*'
```

If found: `Read` it. Extract:
- `BASE_PACKAGE`
- `DOMAIN_SUBPKG`, `APP_SUBPKG`, `ADAPTER_SUBPKG`, `INCOMING_SUBFOLDER`, `OUTGOING_SUBFOLDER`
- Marker FQNs (`AGGREGATE_ROOT_MARKER`, `USE_CASE_MARKER`, `REPOSITORY_MARKER`, etc.)
- Use-case-impl-suffix from custom constants like `APPLICATION_SERVICE_SUFFIX`

If not found: scan the project directly:
```bash
# Find existing aggregate root style
grep -rln --include='*.java' -E 'extends BaseAggregateRoot|implements AggregateRoot' src/main/java

# Find existing use case style — interface/impl naming
grep -rln --include='*.java' -E 'implements\s+\w+UseCase|class\s+\w+(UseCase|ApplicationService)' src/main/java

# Find existing adapter folders
find . -type d \( -name incoming -o -name outgoing -o -name in -o -name out \) -path '*/adapter/*' -not -path '*/build/*'
```

Build a `conventions` summary and (if anything is ambiguous) confirm with the user before generating.

---

## Mode A: Bounded Context

**User intent:** "Add a new bounded context called `orders`."

> Pattern choice per subdomain decides whether to scaffold the full tactical structure —
> check for a pattern-selection ADR (e.g. `docs/adr/`) before scaffolding a full DDD context;
> supporting/generic subdomains may warrant a simpler layout.

### Steps

1. **Validate:** the context name must be lowercase, single word (no hyphens). E.g. `orders`, `inventory`. If hyphenated, the user means a multi-word concept — ask whether to use `customeraccount` (concatenated) or `customer-account` (Gradle module name) — these are different.
2. **Decide install location.** Two common patterns:
   - **Single-module project:** create the package directly under `src/main/java/{basePackage}/{context}/`.
   - **Multi-module Gradle:** create a new sub-project `{context}/` with its own `build.gradle.kts`. Ask the user which mode applies.
3. **Generate the directory tree** (per `templates/bounded-context/`):
   ```
   {basePackage}/{context}/
     domain/
       event/                # empty package — events live here when scaffolded by Mode C
       model/                # aggregates, value objects, IDs
       service/              # domain services (optional, only when needed)
     application/
       shared/               # shared output ports across use cases (Repository, etc.)
       # use cases get their own subdirectory each via Mode B
     adapter/
       {incoming}/           # honors INCOMING_SUBFOLDER from BaseArchUnitTest
         api/                # REST resources
         event/              # event consumers
         web/                # MVC controllers + ViewModels (if applicable)
       {outgoing}/
         persistence/        # repository impls
         event/              # integration event publishers
     package-info.java       # @BoundedContext("name")
   ```
4. **Write `package-info.java`** with `@BoundedContext` annotation. Use the FQN of the project's existing `BoundedContext` annotation (from convention discovery).
5. **Add Gradle module** if multi-module: create `build.gradle.kts` from `templates/bounded-context/build.gradle.kts.tmpl` and add `include("{context}")` to `settings.gradle.kts`.
6. **Verify:** run the architecture tests if they exist. The new (empty) context should not break anything.

---

## Mode B: Use Case

**User intent:** "Add a `placeOrder` use case to the `orders` context."

### Required parameters (ask if not given)

- **Context** the use case lives in (e.g. `orders`)
- **Use-case name** in lowerCamelCase (e.g. `placeOrder`, `getOrderById`)
- **Type:** Command (write — modifies state) or Query (read — pure data fetch)
- **Output ports needed:** which existing repositories/data ports does it need? Or ask the skill to auto-create a fresh `*Repository` if a new aggregate is in play.

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
  above the feature); refuse to scaffold it and point to the bounded-context mode instead.

### Generated files

In `src/main/java/{basePackage}/{context}/application/{usecasename}/` (lowercase, no separator) — or
`application/{feature}/{usecasename}/` in a grouped context:

| File | Generated from | Notes |
|---|---|---|
| `{Name}InputPort.java` | `templates/use-case/InputPort.java.tmpl` | Interface extending `UseCase<{Name}Command|Query, {Name}Result>` |
| `{Name}Command.java` _or_ `{Name}Query.java` | `templates/use-case/Command.java.tmpl` / `Query.java.tmpl` | Java record with the fields the user named |
| `{Name}Result.java` | `templates/use-case/Result.java.tmpl` | Java record with the result fields |
| `{Name}{ImplSuffix}.java` | `templates/use-case/UseCase.java.tmpl` | `@Service @Transactional` impl. ImplSuffix from convention discovery (default `UseCase`, but can be `ApplicationService`, etc.) |

### Wiring

The implementation gets:
- Constructor injection of all needed output ports (declared explicitly by the user or detected)
- A `// TODO: implement` body — the skill doesn't try to write business logic
- Proper imports (using project conventions: lombok `@RequiredArgsConstructor` if project uses lombok elsewhere; otherwise explicit constructor)

If the user named output ports that don't exist yet, scaffold them in `application/shared/` as interfaces extending `Repository` or `OutputPort` (depending on intent).

### Naming check

If the user's name doesn't follow the project's verb pattern (`placeOrder` vs `orderPlace`), gently warn but proceed with what they asked for.

### DTO Mapping at the Adapter Boundary

Use cases speak `Command`/`Query`/`Result` records. Adapter framework code speaks request-DTOs,
response-DTOs, JPA `@Entity` types, Kafka records etc. Mapping happens **at the adapter boundary
only** — never in the use case, never in the domain.

#### Responsibility ownership

| Direction | Adapter type | Maps | Lives in |
|---|---|---|---|
| **In →** | `*Resource` (REST), `*Controller` (MVC), `*EventConsumer` | request-DTO → `*Command`/`*Query` | `adapter/incoming/...` |
| **In ←** | same as above | `*Result` → response-DTO (`*Response`, `*ViewModel`) | `adapter/incoming/...` |
| **Out →** | `*Repository`-Impl, `*EventPublisher`-Impl | Domain (`Order`, `OrderPlacedEvent`) → JPA-Entity / `*IntegrationEvent` / persistence-record | `adapter/outgoing/...` |
| **Out ←** | same as above | JPA-Entity / row → Domain (`Order`) | `adapter/outgoing/...` |

#### Decision: Inline-Mapping vs. dedicated `*Converter` class

```
Wenn (Command-Shape ≈ Request-DTO-Shape, ≤ 5 Felder, keine Transformation):
    Inline im Controller mappen
    → kein Mapper-File, keine Indirection

Wenn (Shapes divergieren, Validierung/Lookup/Default-Berechnung nötig):
    Dedizierten *Converter im selben Adapter-Folder
    → z.B. adapter/incoming/api/PlaceOrderRequestConverter.java

Wenn (mehrere Resources mappen ähnliche Strukturen):
    Geteilten Converter in adapter/incoming/api/mapper/
    → erst extrahieren wenn die dritte Stelle ihn braucht (Rule of Three)
```

#### Beispiel: REST-Inbound (Inline)

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

#### Beispiel: REST-Inbound mit dediziertem Converter

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

#### Beispiel: Outbound (Repository-Impl)

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
class OrderEntity { /* JPA-Felder, getter/setter, @Id, @Column ... */ }
```

#### Anti-Patterns

- **Aggregat direkt als REST-Response** — leakt Domain-Form an Clients (`Order` als JSON-Antwort). Immer auf `*Response`-Record im Adapter mappen.
- **`*Command`/`*Query`/`*Result` als JPA-`@Entity`** — bricht Framework-freies Domain/Application und vermischt zwei Lebenszyklen (Use-Case-Input vs Persistence-Row).
- **Mapper-Logik in der Use Case** — wenn `PlaceOrderUseCase` ein `PlaceOrderRequest` konstruiert oder ein `*Response` baut, ist die Boundary verschoben. Mapper gehören in `adapter/`.
- **Geteilter `*Dto` für Request *und* Persistence** — derselbe Record erfüllt zwei Rollen; jede Änderung an einer Seite zwingt die andere. Lieber zwei separate Records mit explizitem Mapping.
- **Mapper in `application/` oder `domain/`** — Mapper sind Adapter-Concern. ArchUnit-Regel `dtosShouldLiveInAdapterLayer` fängt das.
- **Domain-Event direkt als Kafka-Payload** — DCA-Konvention: Domain-Events bleiben kontextintern. Cross-Context geht über `*IntegrationEvent` (mit `version`-Feld), gemappt im `adapter/outgoing/event/`-Publisher.

Siehe [use-case-pattern.md §4](../dca-review/reference/use-case-pattern.md#4-adapter-wiring-wer-ruft-was) für das vollständige Wiring-Bild und [naming-conventions.md](../dca-review/reference/naming-conventions.md#adapter-layer) für die Adapter-Namens-Tabelle.

---

## Mode C: Aggregate Root

**User intent:** "Create an `Order` aggregate root in the `orders` context."

### Required parameters

- **Context** (e.g. `orders`)
- **Aggregate name** in PascalCase (e.g. `Order`)
- **ID type:** auto-generated UUID, sequence number, or natural key — ask
- **Optional:** initial fields the user knows (e.g. `customerId`, `placedAt`)

### Generated files

In `src/main/java/{basePackage}/{context}/domain/model/`:

| File | Notes |
|---|---|
| `{Name}.java` | `extends BaseAggregateRoot<{Name}, {Name}Id>` if available, otherwise `implements AggregateRoot<{Name}, {Name}Id>`. Has `id()`, factory method `create(...)`, and a TODO for business methods. |
| `{Name}Id.java` | Java record `implements Id`. Type matches the chosen ID type (UUID/Long/String). |
| `{Name}Created.java` (in `domain/event/`) | Java record `implements DomainEvent`. Has `aggregateId`, `occurredAt`. |

In `src/main/java/{basePackage}/{context}/application/shared/`:

| File | Notes |
|---|---|
| `{Name}Repository.java` | Interface `extends Repository<{Name}, {Name}Id>`. Methods: `findById`, `save`. |

If the project uses lombok: use `@Getter`, `@AllArgsConstructor` etc. Otherwise explicit accessors.

### Don't generate business methods

The skill scaffolds the structure — the user writes the actual invariants and business operations. The generated aggregate has:
- A `create(...)` static factory that emits a `{Name}Created` event
- Empty `domainEvents()` and `clearDomainEvents()` (or inherit from `BaseAggregateRoot` if present)
- A `// TODO: invariants and business methods` placeholder

Generate intention-revealing methods, never public setters.

---

---

## Mode D: Store

**User intent:** "Add a `LoginProtection` store to the `customeraccount` context."

A **Store** is the second persistence-shaped output port in DCA. Use Mode D **instead of** Mode C's Repository when the data being persisted has no aggregate lifecycle.

### Decision: Store or Repository?

Before scaffolding, confirm with the user:

| If the stored object… | Use |
|---|---|
| has identity, gets loaded by ID, mutated, saved back | **Repository** (Mode C generates this for Aggregate Roots) |
| is appended/recorded; queried by aggregate (count, exists, sum) | **Store** (this mode) |
| is a Value Object or `record` | almost always **Store** |

If the user is unsure, ask: "Will you ever call `findById` on a `{StoredType}`? If no, it's a Store."

### Required parameters

- **Context** (e.g. `customeraccount`)
- **Store name** (e.g. `LoginProtection` — generates `LoginProtectionStore`)
- **Stored type:** the value object / record / event being stored (e.g. `LoginAttempt`)
- **Query methods:** what aggregate questions the Store answers (e.g. `countRecentFailures`, `isBlocked`)

### Generated files

In `src/main/java/{basePackage}/{context}/application/shared/`:

- `{Name}Store.java` (from `templates/store/Store.java.tmpl`) — interface `extends Store`. Has `record(...)` plus the user-named query methods.

The skill does NOT generate a `findById` or `save` method — those are Repository semantics.

### Anti-pattern guard

If the user names the new port `*Repository` but the stored type is a Value Object or record, the skill must point that out and recommend Mode D instead. Likewise, if the user asks for Mode D but names the stored type as an Aggregate Root, recommend Mode C.

---

## Templates and substitutions

See `templates/` for the actual `.java.tmpl` files.

Common placeholders:
- `{{basePackage}}`, `{{context}}` — base package + bounded context name
- `{{usecasename}}` (lowercase, no separator) — for use case folder
- `{{featureSegment}}` — empty in a flat context, `{feature}.` in a grouped one (so the package reads `application.{{featureSegment}}{{usecasename}}`)
- `{{Name}}` — PascalCase name (e.g. `PlaceOrder`, `Order`)
- `{{commandOrQuery}}` — `Command` or `Query`
- `{{useCaseImplSuffix}}` — `UseCase` (default) or `ApplicationService` etc.
- `{{aggregateRootMarker}}` — short class name to use (`BaseAggregateRoot` if available, else `AggregateRoot`)
- `{{repositoryMarker}}`, `{{storeMarker}}`, `{{useCaseMarker}}`, `{{idMarker}}` etc. — short names
- `{{storedType}}`, `{{StoredType}}`, `{{queryMethods}}` — for Mode D (Store)
- `{{incomingSubfolder}}`, `{{outgoingSubfolder}}` — `incoming` (default) or `in`
- `{{useLombok}}` — `true` / `false` based on project convention

## Idempotency check

Before any write:
```
if Path(target).exists():
    ask user: "{path} already exists. Overwrite / skip / abort?"
    default action: skip
```

## After scaffolding

Run the architecture tests if they exist:
```bash
./gradlew test-architecture     # if dca-bootstrap was used
./gradlew :{context}:test       # otherwise the regular test task for this module
```

Any failures should be findings, not skill bugs. Print:
```
✓ Scaffolded {N} files for {operation}
  - Files: {list}
  - Tests: {pass count} / {total}

Next:
  - Implement business logic in {primary file}
  - Wire output ports in the use case impl (look for TODO comments)
```

## Anti-patterns

- **Don't write business logic.** The skill scaffolds structure. The user's domain expertise fills it.
- **Don't impose conventions** the project doesn't follow. If they use `*ApplicationService`, scaffold `*ApplicationService` — not `*UseCase`.
- **Don't auto-generate Repository methods beyond `findById`/`save`.** Specific finders are project decisions.
- **Don't add Spring `@Component` to domain classes.** Domain stays framework-free (DCA invariant).
- **Don't generate package-info.java for sub-packages** (only for the bounded context root) — keeps the tree clean.
