---
name: dca-modelling
description: The craft of building tactical DDD types — aggregates, entities, value objects, ids, domain and integration events, domain services, factories, specifications, repositories, stores and named failures. Use when designing or implementing a new domain concept, or when a delivery stage needs the project's implementation craft. Reads the project's conventions and existing types first and adapts to them; it builds, it does not review.
---

# /dca-modelling — building the domain types

Design and implement one domain concept at a time; write code, do not review (review → `review-ddd`). The
write-time invariants (framework-free domain, dependency inversion, context isolation, event hygiene, named failures
answered once per context) are `dca-discipline`'s — apply it alongside. A long session may run in a subagent so the
main conversation keeps only the closing report. Unsure what DCA says → `/dca-knowledge`.

## How you read the project (mandatory first step)

1. Conventions, in this order: a path given to you, `dca.profile.yaml` at the root (`AGENTS.md` line
   ``- configuration: `dca.profile.yaml` ``), `AGENTS.md`, `CLAUDE.md`; absent key → defaults. Take:
   - language; the markers in two spellings:

     | Java | .NET |
     |---|---|
     | `AggregateRoot`, `BaseAggregateRoot` | `IAggregateRoot`, `AggregateRootBase` |
     | `Value`, `Id` | `IValue`, `IId` |
     | `Repository`, `Store` | `IRepository`, `IStore` |
     | `DomainEvent`, `IntegrationEvent` | `IDomainEvent`, `IIntegrationEvent` |
     | `DomainService`, `Factory`, `Specification` | `IDomainService`, `IFactory`, `ISpecification<T>` |
     | `@BoundedContext` on `package-info` | `[BoundedContext]` on the `XContext` marker class |

     The .NET domain is synchronous; only ports are async.
   - base package / root namespace; marker FQNs from `dev.domaincentric.dca.buildingblocks.…` /
     `DomainCentric.BuildingBlocks.…` unless the project keeps its own
   - layer folders (`incoming`/`outgoing` vs `in`/`out`)
   - suffixes: `use_case_suffix:`, `input_port_suffix:`, `repository_suffix:`, `controller_suffix:`,
     `rest_controller_suffix:` first, then the `DcaLayout` builder in the architecture test, the code last. A failure
     is named by its rule plus `failure_suffix:` (`Exception` when missing)
   - refusal style per context: technical description (`tech:`, `product/tech.md`) line
     `Refusals (<context>): thrown | returned`, else `Refusals: …`, else the existing use cases
   - Lombok or records; C#: `sealed record` for values and events, `readonly record struct` for ids
   - allowed domain imports (JSpecify, Apache Commons…)
2. Inspect the code: identity in existing aggregates, event base class and fields (`eventId`/`occurredOn`/
   `version`), repository base interface.
3. Glossary `<spec>/<context>/glossary.md` (`spec:` in the profile, default `product/spec/<context>/glossary.md`):
   adopt terms verbatim; name use case, command and event from the operation's code word (`PlaceOrder`,
   `OrderPlaced`). Missing term or operation, or no glossary → enter it through `ubiquitous-language` first. A verb
   that could name more than one effect (create vs add, delete vs cancel) → ask, never translate.

Adapt to what is there (`BaseAggregateRoot<T, ID>` or a flat marker); impose nothing the project does not use.

## Tactical patterns you implement

### Aggregate Roots
- Project's `AggregateRoot` marker; typed `id()` (`OrderId`, not `UUID`); other aggregates by id only.
- Persistence-ignorant: repositories/ports as method parameters, never fields.
- No setters; invariants in factory and behaviour methods (`confirm()`, `cancel(...)`); constructors validate.
- A yes/no fact is a private `boolean` field: told (`complete()`), answers (`isCompleted()`). No domain method takes
  a `boolean` (`setCompleted(true)` is a flag argument, `DCA-TAC-025`). Three+ states or ruled transitions → enum or
  value; independent facts (completed, archived) → separate fields, never one status. A glossary status wins.
- Register events at the right state transition only. `final` if the project favours closed inheritance.

### Entities (non-root)
- `Entity<T, ID>` marker; identity equality (`sameIdentityAs` or `equals` on id, per convention); inside an
  aggregate, never their own repository.

### Value Objects
- `Value` marker; immutable — Java `record`, C# `sealed record` (ids `readonly record struct`); class only for
  invariants a compact constructor cannot express.
- Validate in the compact constructor (C#: primary-constructor body or static `Of(...)`).
- Built from input → carries its rule alone, null included: refuses null with the rule's named failure
  (`InvalidTitleException`, same as empty/too long) — no NPE, no `requireNonNull`. The incoming adapter passes the
  raw value unchanged: no repeating annotation, no default turning absence into `""`.
- Value equality; `of(...)`/`generate()` when construction is non-trivial.

### IDs
- `Id` and `Value`; usually a record over one field; validate non-null/non-blank; `generate()` and `of(String)`.
- Referenced across contexts → `sharedkernel/domain/model/`, else `{context}/domain/model/`.

### Domain Events
- `DomainEvent` marker; past tense (`OrderPlaced`); record or immutable class; IDs and value objects only.
- Fields per convention, typically `UUID eventId`, `Instant occurredOn`; `now(...)` factory generates both.
- A business revision (`int version`) is legitimate payload — keep its domain name, never recommend renaming. Schema
  version belongs to integration contracts: `@IntegrationEventType` / `[IntegrationEventType]`, not a payload field.
- In `{context}/domain/model/` (or `/domain/event/` if the project has it).
- Outcome event (what an epic's metric or key result measures, named before the code): a domain event of the context
  where the outcome happens, named exactly as the measure names it — no synonym, no translation. The aggregate raises
  it at the transition completing the flow; the use case publishes it.

### Integration Events
- `IntegrationEvent` (often extends `DomainEvent`); past tense + `Event` (`OrderPlacedEvent`); cross-context,
  serialized at the wire.
- Contracts in the configured `{context}/events/`; translators and publishing in `adapter/outgoing/event/`.

### Domain Services
- `DomainService` marker, in `domain/service/`, named in the ubiquitous language.
- Only for a rule spanning several aggregates; one aggregate's or value's calculation lives on that type.
- Takes the aggregates as parameters, not values pulled out of them; facts the domain does not own may come along.
- The application calls it; no aggregate, entity or value constructs or calls one.
- Stateless (`final` constructor-injected fields only); no container, persistence or transaction metadata
  (unclassified metadata is not forbidden by the role checks); registered in configuration.

### Factories
- `Factory` marker, only for genuinely complex construction (multi-step, cross-aggregate); otherwise a static
  factory method on the aggregate.

### Specifications
- `Specification<T>` with `boolean isSatisfiedBy(T)`; `.and/.or/.not` if the marker hierarchy has them; for rules
  reused across queries, validations, filters.

### Failures
- A refusing rule gets its own named type; the refusal style (thrown | returned) is the context's.
- Writing a failure type, a sealed `{Operation}Result`, a `Refusal` case or a foreign system's
  `{System}UnavailableException` → read `reference/failures.md` first (hierarchy, styles, placement, naming).

### Repositories
- Interface in `{context}/application/shared/` — context-wide, never in a feature folder, also when use cases are
  grouped `application/{feature}/{usecase}/`.
- Extends `Repository<T extends AggregateRoot<T, ID>, ID>` (or matching marker); inherits `findById()`, `save()`,
  `deleteById()`.
- Finders in ubiquitous language: `findActiveOrdersOlderThan(Instant)`, not `findByStatusAndCreatedAtBefore`.
- One per aggregate root; never for entities or values (through the aggregate or a Store).

### An aggregate that belongs to someone
Ask whether it belongs to an identity the system knows (account, tenant, guest with a pseudonymous identity from a
signed token). If so:
- implements `Owned<OwnerId>` (C# `IOwned<TOwnerId>`; Rust `impl Owned { type OwnerId = … }`), owner held as a field;
- repository declares lookup by aggregate id and owner id, named in the context's language
  (`findByIdForPatient(id, patient)`); every use case acting for a caller loads through it — never `findById` + `if`.
  `DCA-TAC-026` (experimental) checks the repository side;
- an event asking for an effect carries the owner; its use case loads through it too. `findById` stays for paths with
  no owner to name;
- owner changes only through an explicit operation (`takeOverBy(newOwner)`) after the use case proved the caller's
  right — use-case logic with its own tests.

Nobody owns it → unmarked. No identity and the id is the secret (long random id in a link) → not `Owned`; say so
beside it so nobody reads it as forgotten. Reasoning: catalog decision *Ownership as a marker*.

### When to use Store instead of Repository
No aggregate lifecycle (append-only events, login attempts, audit entries, counters) → `Store` with `record(...)`,
`count(...)`, `exists(...)`. Lookup by id allowed; lifecycle save/delete belongs to a Repository.

## Workflow

1. Identify the bounded context; unclear → ask (wrong context outweighs wrong field names).
2. Consult its glossary; missing term → `ubiquitous-language`, proposed to the user where the definition is theirs,
   never invented.
3. Read 1–2 similar artifacts to match style.
4. Implement, adapted to project convention. Behaviour on an aggregate: failing test first, one unit test per
   invariant (`/testing`); static structure needs none.
5. Run architecture tests (`./gradlew test-architecture`, or `dotnet test tests/*.ArchitectureTests` — Debug build).
6. Close with the report. Follow-ups are named, not generated (new aggregate → Repository, `*Created` event, a use
   case).

## Closing report

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

- `review-ddd` — review-only counterpart (often with `review-hexagonal`, `review-clean-code`); `dca-audit` checks
  DCA conformance.
- `dca-discipline` — the invariants while editing (prevention); this skill implements.
- `ubiquitous-language` — every new term goes through it first; the report names it.
- `dca-new` — lays out the files of an aggregate or domain service, calls this skill for the types.
- `/testing` — test first for aggregate behaviour.
- `/adr` — a design choice beyond the task (domain service vs one aggregate) gets an ADR.

## What you do NOT do

- Lay out whole bounded contexts → `dca-new context`.
- Write use-case orchestration (use cases call aggregates; keep apart).
- Write adapters (repository impls, REST/MCP/event consumers); you design the ports.
- Review existing code → `review-ddd`; mention something dubious briefly, do not dwell.

## Project-agnostic operation

Every package name, marker base class, test framework and folder name comes from `dca.profile.yaml` or live
inspection, never from examples here. No convention established → propose one and ask before committing.
