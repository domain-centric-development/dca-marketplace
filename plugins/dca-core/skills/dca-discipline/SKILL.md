---
name: dca-discipline
description: |
  Applies Domain-Centric Architecture invariants while writing or editing
  Java/Spring or .NET/C# code: framework-free domain, dependency inversion (interfaces in
  app/domain, impls in adapters), bounded-context isolation (no raw cross-context
  imports), domain-event hygiene (publish + clear), named failures — expected
  refusals thrown or returned as cases, uniform per context — each answered once
  per context. Use during edits to domain/, application/, or adapter/ folders.
disable-model-invocation: false
---

# /dca-discipline — DCA invariants while writing code

Write-time guards, not a review. Never rewrite silently past a violation. Unsure what DCA says → `/dca-knowledge`.

## The six invariants

### 1. No framework in domain

- Java `**/domain/**` imports none of: `org.springframework.*`, `jakarta.persistence.*`, `jakarta.validation.*`
  (unless the project's conventions allow Bean Validation), `org.hibernate.*`, `com.fasterxml.jackson.*`, any
  other framework.
- C# `**/Domain/**`: none of `Microsoft.AspNetCore.*`, `Microsoft.EntityFrameworkCore.*`, `System.Data.*`,
  `System.Transactions.*`, `System.Text.Json.Serialization` attributes, `Microsoft.Extensions.*`; no `async`
  member (ports are async, the domain is not).
- Asked for one (`@Component` on a domain class) → offer: (a) move to `application/{usecase}/` or `adapter/`,
  (b) keep in domain without it, (c) ADR exception (`/adr new`, rare).

### 2. Dependency inversion

- `domain/` and `application/` depend only on domain types, output port interfaces, the standard library.
- Never: classes from `adapter/`/`infrastructure/`, concrete clients (`RestTemplate`, `JdbcTemplate`,
  `KafkaProducer`, `HttpClient`, `DbContext`…), framework types on a use case's API (parameters, return types).
- Use case needs infrastructure, or someone injects a concrete adapter → port first: interface in
  `application/shared/` (or the use case's folder if only it uses it — `dca-audit`'s `use-case-pattern.md`,
  section 3), impl in `adapter/outgoing/…`.

### 3. Bounded-context isolation

No import of `{basePackage}.contextA.domain.*` from `{basePackage}.contextB.*`. Allowed channels:

| Channel | Dependency | Example |
|---|---|---|
| Open Host Service (REST/MCP) | downstream calls upstream's incoming API | Cart reads Catalog via `/products/{id}` |
| Integration event | downstream consumes upstream event | Checkout listens to `OrderPlacedEvent` |
| Shared kernel value objects | both import `sharedkernel/` | `Money`, `ProductId` |

Seen a cross-context import → offer: (1) call the OHS (read-time data), (2) consume an integration event and
project locally (react to changes), (3) move the type to the shared kernel (rare, truly universal).

### 4. Domain-event hygiene

- Use case: load → behaviour (aggregate registers events) → save → `publishAndClearEvents` /
  `PublishAndClearEventsAsync` (the building-block publisher; clears only after successful synchronous dispatch).
  Java and C# shape → `reference/events-and-rules.md`.
- Event-free aggregate → no publisher dependency (USE-009 exemption needs a resolved, fully inspected hierarchy).
- Integration event: own-context `adapter/outgoing/event` subscribes to the domain fact, translates to a contract
  in `{context}/events/`, captures it in the transaction (Spring: synchronous `@EventListener` →
  `integrationEvents.publish(XEvent.from(fact))`; .NET: local domain-event listener awaiting its publisher).
- Event shape, all four: immutable (record / immutable class / C# readonly struct); past tense (`OrderPlaced`);
  `occurredOn` as `Instant` / `DateTimeOffset`; IDs and value objects only, no aggregate references.
- Reacting: a listener that drives an input port runs after commit, own transaction, from an outbox —
  `@ApplicationModuleListener` (Spring), the project's transactional listener type (.NET) — for foreign contracts
  and own domain events alike. A synchronous listener (`@EventListener`, plain listener) calls output ports only
  (the capturing translator, a metric).
- Async delivery, idempotency, remote effects → the same reference.

### 5. Domain-model and transaction discipline

- No public setters; intention-revealing methods (`confirm()`).
- Owned aggregate: implements `Owned<OwnerId>` / `IOwned<TOwnerId>`, repository declares lookup by id and owner id
  (`DCA-TAC-026`); a use case acting for a caller, or for an event naming the owner, uses it — never `findById` + `if`.
- Aggregates persistence-ignorant: no `Repository`/`Store`/`OutputPort` fields; pass as method parameter.
- `@Transactional` only on application use cases (persistence adapters allowed), never domain or incoming
  adapters. C#: `ITransactionBoundary.InTransactionAsync` (or a decorator around `IUseCase`) in the use case;
  EF Core / `System.Transactions` stay out of `Application/` (`DCA-NET-006`).
- No remote call inside the transaction: a use case calling a port that may leave the process drops the class
  annotation — remote reads first, then `transactionBoundary.inTransaction(() -> { load; mutate; save; publish; })`
  (`TransactionBoundary` = building-block execution abstraction, not a port). Remote effects after commit, as a
  reaction to an integration event.

### 6. A failure has a type, and only the adapter answers it

- Named failure from the building blocks: domain `DomainException`; application under `PortException` — use case's
  own extends `UseCaseException` (never `InputPortException` directly); output port declares `OutputPortException`,
  adapter throws, use case catches. Name = rule: `InsufficientStockException`, not `OrderError`.
- Own DB/broker failing → platform exception. A foreign system behind an output port (external on the context map)
  refusing / timing out / unreachable → its port's `OutputPortException`, thrown by the adapter, answered by the use
  case as a refusal. A caller with nobody to answer throws the case back so delivery is retried.
- "Which one, if any" → empty value; "not found" refuses only a caller naming a thing by id.
- Whoever searches owns "not found": aggregate by id via repository → use case's refusal, never `DomainException`;
  a part by local id inside the aggregate → model's `DomainException`, caught and answered by the use case.
- Expected refusal thrown or returned, uniformly per context (style from the technical description, else the
  context's use cases). Returned: case of a sealed result implementing `Refusal` / `IRefusal`, ids and figures, no
  suffix; the model still throws, the use case catches each concrete exception once and returns its case. A sealed
  result of successes only (`Sent` | `AlreadySent`) carries no `Refusal`; `DCA-ERR-008` lists those for
  confirmation.
- Decide, then write: every refusal before the first write (rollback of a returned `Refusal` is only a net).
- Argument guard stays platform: `IllegalArgumentException` / `ArgumentException`, `ArgumentNullException`,
  `ArgumentOutOfRangeException`. Cut = origin and name: a value object built from input refuses null and bounds with
  its rule's named failure; a domain expert's word for the failure → domain exception with that word.
- Rule on input checked once, in the value object; the incoming adapter checks shape, passes the raw value (absent
  as absent) — no Bean Validation / DataAnnotations repeating it, no `defaultValue = ""`.
- Who states it: "already confirmed" = aggregate; "no such order" = use case (never a domain exception it
  constructs); store-detected failure = `OutputPortException` beside its port.
- Never show `getMessage()` / `.Message` to a user: the incoming adapter words it from type and values (message
  key); the message is for the log.
- No transport in the type: no `@ResponseStatus`/framework metadata, no `Error`/`Fault`/`Failure` suffix, no
  `Http`/`Status`/`Response` in the name (`DCA-ERR-004`, `DCA-ERR-005`).
- Answer once per context in `adapter/incoming/`. Thrown: one handler per context — `@RestControllerAdvice` scoped
  to its package / `IExceptionHandler` scoped to its routes — producing a problem document. Returned: each call site
  switches without `default` (OneOf: `Match`, in type order), answers in one adapter class the switches call;
  handler stays for the unexpected. Status follows the failure, not the base type. A page adapter turns a refusal
  into its redirect in one method every handler calls.
- Nobody drops a result: a test helper asserts success; an event consumer throws the case on purpose.
- Never catch `Exception`/`RuntimeException` around a use-case call, nor `PortException`/`InputPortException` as
  such (swallows an escaped `OutputPortException`). Inside a use case too: catch the rule's own type.

Strictness follows the context's pattern style (pattern-selection ADR): transaction script (supporting subdomain)
→ 1–3 hold, 4–5 may relax.

## How this skill operates

Classify the target path, apply its rules, cross-check the imports the edit introduces; violation ahead → stop, offer
the invariant's options.

| Layer | Rules applied |
|---|---|
| `domain/` | 1, 2, 3, 4, 5 |
| `application/{usecase}/` — or `application/{feature}/{usecase}/` in a feature-grouped context (one form per context, `DCA-USE-014`; no feature cycles, `DCA-CYC-005`) | 2, 3, 4, 5 (`@Transactional` / `InTransactionAsync` lives here) |
| `application/shared/` | 2 (interfaces only — no impls) |
| `adapter/incoming/` | 3 (must not bypass application layer to reach domain: no `DomainService` injected or invoked, `DCA-HEX-012`; reads and formats the `*Result` — a delivered read model's own queries included — constructs no domain object, combines nothing into a new business fact), 5 (no `@Transactional`) |
| `adapter/outgoing/` | 3 (must implement a port, not introduce new domain concepts); `@Transactional` allowed on persistence adapters |
| `infrastructure/` | — (framework code belongs here; C#: DI registration `Add{Context}Context()`) |

C# PascalCase folders (`Domain/`, `Application/{UseCase}/`, `Adapter/Incoming/`…) take the same rules. Operation boundaries (`DCA-USE-016`, `DCA-USE-017`, `DCA-NET-003`), ACL
evidence (`DCA-MAP-008`) and modelling edge cases → `reference/events-and-rules.md`, read when editing a use case's
public surface, a coordinator, an ACL adapter, or when one of those rules fails.

## Project configuration

`dca.profile.yaml` at the root (`AGENTS.md` line ``- configuration: `dca.profile.yaml` ``), flat `key: value`, every
key optional:

- base package / root namespace (markers: `dev.domaincentric.dca.buildingblocks.…` / `DomainCentric.BuildingBlocks.…`)
- layer folders `incoming`/`outgoing` or `in`/`out` (also in the test's `DcaLayout` builder)
- suffixes: `use_case_suffix:`, `input_port_suffix:`, `repository_suffix:`, `controller_suffix:`,
  `rest_controller_suffix:`, `failure_suffix:`
- project exceptions (e.g. Bean Validation allowed in domain)

Refusal style per context: technical description (`tech:`, `product/tech.md`) line
`Refusals (<context>): thrown | returned`, else `Refusals: …`; neither line nor use case → ask.
Missing file or key → the guide's DCA defaults (`dca-knowledge` cites them).

Experimental rules (`maturity: experimental` in the catalog node) bind only with `withExperimental()` /
`WithExperimental()` in the architecture test or `dca.rules.experimental = true` in `dca-archunit.properties`.
Otherwise information at most; never change code or stop an edit for one.

## What this skill does NOT do

- Audit existing code → `dca-audit`, the reviewer agents.
- Lay out new code → `dca-new`; domain types → `dca-modelling`; naming → `/clean-code`, `/ubiquitous-language`.
- Run ArchUnit — the net after this skill.

## Anti-pattern: silently bypassing the rule

User insists ("just add `@Entity` to the aggregate") → refuse with the alternative (port + adapter, ACL…) or record
the exception via `/adr new` — an ADR exception (legacy, framework-mandated annotation) is a successful outcome.
