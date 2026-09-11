---
name: dca-review
description: |
  Reviews Java/Spring or .NET/C# code against Domain-Centric Architecture (DCA) conventions. Complements
  ArchUnit by checking semantic aspects that static rules can't: aggregate-design quality,
  use-case granularity, port semantics, domain-event hygiene, cross-context boundaries, naming
  consistency. Use when the user asks to "review my DCA code", "is this DCA-compliant", "audit
  the changes for DCA", or "/dca-review". Default scope is the git diff against main; the user
  can pass explicit paths instead.
---

# dca-review

Reviews changed code (or specific paths) for **DCA compliance** — focusing on issues that
ArchUnit rules can't detect because they are semantic, not structural.

This is the third skill in the DCA suite. It assumes `dca-bootstrap` may or may not have run.
If it ran, the review reads the project's `DcaLayout` from the architecture test (and
`.claude/dca/conventions.md`) for naming conventions; otherwise it falls back to defaults. Java and C# are
reviewed against the same checklist — `reference/naming-conventions.md` carries the language mapping.

## Where ArchUnit ends and dca-review begins

| Checked by ArchUnit | Checked by dca-review |
|---|---|
| Class names match suffix patterns | Whether the names actually describe what the class does |
| Domain doesn't depend on adapters | Whether use cases hold too many output ports (god-use-case) |
| Aggregates implement marker | Whether aggregates have real invariants vs. anemic |
| Domain events implement marker | Whether events are emitted at the right state-transition points |
| Cross-context refs forbidden | Whether the cross-context API is well-designed |
| Records/finals on value objects | Whether value objects model the domain or just hold getters |

## Workflow

### Phase 1: Scope

Determine which files to review.

**Default — git diff:**
```bash
git diff --name-only main...HEAD                  # commits on this branch
git diff --name-only HEAD                         # uncommitted (modified + staged)
git diff --name-only --diff-filter=A main...HEAD  # added in this branch
```
Combine to get all changed `*.java` / `*.cs` files. If no git repo or no diff, fall back to:

**User-specified paths.** If the user passed explicit paths (files or directories), review those instead.

If neither: ask the user which paths to review.

### Phase 2: Layer classification

For each file, determine its DCA layer from path:

```
**/domain/model/**       → domain.model
**/domain/event/**       → domain.event
**/domain/service/**     → domain.service
**/application/{usecasename}/**  → application.usecase
**/application/{feature}/{usecasename}/**  → application.usecase (feature-grouped context)
**/application/shared/** → application.outputports
**/adapter/{in,incoming}/**  → adapter.incoming
**/adapter/{out,outgoing}/** → adapter.outgoing
```

C# uses the same segments in PascalCase (`Domain/Model`, `Application/{UseCase}`, `Application/Shared`,
`Adapter/Incoming`, `Adapter/Outgoing`); match case-insensitively.

Files outside these patterns: report as "uncategorized" — could be infra or shared kernel.

### Phase 3: Apply review checks per layer

See `reference/checklist.md` for the full per-layer checklist. Run only the checks that
apply to each file's layer. For application-layer files (use cases, output ports), consult
`reference/use-case-pattern.md` for the canonical folder structure, shape, and
shared-vs-local port decision guide.

For each finding, capture:
- **File + line** (use file_path:line)
- **Severity:** `must-fix` (violates DCA invariant), `should-fix` (anti-pattern), `nit` (style)
- **Rule** (short name from checklist)
- **Why** (one sentence — quote the principle)
- **Suggested fix** (one-line code suggestion when feasible)

### Phase 4: Suggest missing ArchUnit rules

After the review, if you noticed patterns that *could* be enforced statically but aren't covered
by the current ArchUnit suite, suggest adding rules. Format:

Past-tense event names are a language review prompt: `Sent` is valid without an `ed` suffix.
Do not propose a suffix rule to infer tense. Propose a static rule only for a structural property with
named positive and negative fixtures and a clear selection scope.

### Phase 5: Output

Produce a structured report:

```
## DCA Review

**Scope:** {N} files changed in this branch (vs. main)

### Findings ({must-fix} must-fix · {should-fix} should-fix · {nit} nits)

#### must-fix
- `path/Order.java:42` — Aggregate has setters
  Why: Aggregates must enforce invariants — public setters bypass them.
  Fix: Replace `setStatus(...)` with `markCompleted()` or `cancel(reason)`.

#### should-fix
- `path/PlaceOrderUseCase.java:15` — Use case takes 7 output ports
  Why: God-use-case smell. Consider splitting or introducing a domain service.

#### nits
- `path/CartCleared.java` — Event name is past tense ✓ but missing `occurredAt` field
  Suggested fix: add `Instant occurredAt`.

### Suggested ArchUnit rules

(rules that would catch these statically — add to your test-architecture suite)

### Strengths

- Events are emitted only when a domain fact needs publication ✓
- Output ports are interfaces in application, shared when reused and local when owned by one operation ✓
```

## Anti-patterns this review catches

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

### Domain event without timestamp
Why: events are causal records; without time you can't reason about ordering across contexts.

### Domain event with mutable field
Why: events are facts about the past — facts don't change.

### Setter on value object
Why: value objects are immutable by definition.

### Public setter on entity or aggregate
Symptoms: `setX(...)` on a domain model class, even when it validates internally.
Why: state changes go through intention-revealing methods from the ubiquitous language
(`adjustStockTo`, not `setAvailableQuantity`). A setter name hides the business operation.

### Injected dependency in aggregate
Symptoms: an aggregate holds a `*Repository`, output port, or service as a field.
Why: aggregates are persistence-ignorant — dependencies are loaded by the use case and
passed as method parameters.

### Transaction outside the application layer
Symptoms: `@Transactional` on a domain class or incoming adapter.
Why: the use case owns the unit of work. (Outgoing persistence adapters may use it for
multi-statement atomicity — joins the caller's transaction.)

### Controller reaching past the use case
Symptoms: a `*Controller`/`*Resource` injects a `*Repository`.
Why: incoming adapters drive the application through input ports only — direct repository
access bypasses transactions, authorization, and orchestration.

### Technical names in the domain
Symptoms: `*Helper`/`*Util`/`*Impl` classes in `domain/` (`Manager` is valid domain vocabulary), or bucket packages
like `entities/`, `valueobjects/`, `helpers/`, `util/`.
Why: technical names signal a missing domain concept; packages are named by domain concept.

### Spring annotation on domain class
Why: domain stays framework-free (DCA invariant). The C# twin: an ASP.NET, EF Core (`[Table]`, `DbContext`)
or `System.Text.Json` attribute on a class in `Domain/`, or an `async` member on an aggregate — the .NET
catalog keeps the domain synchronous and framework-free (`DCA-NET-00x`).

### Cross-context import not via api/
Symptoms: file in `contextA/...` imports from `contextB/domain/...` directly.
Why: contexts communicate via Open Host Service or events, never raw domain.

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
Symptoms: a `*Store` exposes aggregate persistence methods (`save`, `delete`), OR a `*Repository`'s stored type is a Value
Object / record without aggregate lifecycle.
Why: DCA distinguishes Repository (for Aggregate Roots — collection-like, identity-based) from
Store (for operational data — record/count/exists). Confusing them breaks the Ubiquitous
Language: a reader can no longer tell from the port name what kind of data it manages.
Fix: rename and re-marker. If `findById` makes sense → `*Repository extends Repository<T,ID>`.
If `record`/`count` makes sense → `*Store extends Store`.
Note: the Store half is now mechanical — ArchUnit checks the marker, both placements, and the
forbidden `findById`/`save`/`delete` method names. What remains for review is the direction ArchUnit
cannot see: a `*Repository` whose stored type has no aggregate lifecycle.

## Reading dca-bootstrap conventions (if installed)

Find the architecture test (`grep -rn "DcaLayout\." --include='*.java' --include='*.cs'`) and read its
`DcaLayout` builder chain — every `with…`/`With…` call is a deviation from the DCA default:
- The use-case-impl suffix (`withUseCaseSuffix` — default `UseCase`, but may be `ApplicationService`)
- The adapter sub-folder names (`withIncomingSubpackage`/`withOutgoingSubpackage` — `incoming`/`outgoing` or `in`/`out`)
- The REST adapter suffix (`withRestControllerSuffix` — `Resource` or `Controller`)
- `dca-archunit.properties`: rule sets switched off there mark patterns the project deliberately does not use
  (a context without `tactical` is not an anemic-model finding)
The markers are the library's (`dev.domaincentric.dca.buildingblocks.…` / `DomainCentric.BuildingBlocks.…`).

This makes the review match the project's actual conventions, not DCA defaults.

## Things this review does NOT do

- **Doesn't run code or tests.** Static review only.
- **Doesn't refactor.** It reports — the user fixes.
- **Doesn't catch business-logic bugs.** It only flags structural/conceptual issues.
- **Doesn't enforce a single style.** If the project's convention is `*ApplicationService` and
  it's consistent, that's not a finding.
- **Doesn't force the full pattern set on every context.** Pattern choice follows subdomain
  type: a supporting context whose ADR declares transaction-script/active-record style is not
  an anemic-model finding — only the structural baseline applies there (layer dependencies,
  no cycles, context isolation). Check `docs/architecture/adr/` for a pattern-selection ADR
  before flagging tactical-DDD violations in simple contexts.

## Reference

- `reference/checklist.md` — the complete per-layer checklist (includes Output Port Granularity section)
- `reference/use-case-pattern.md` — central reference for use-case folder structure, file roles, shared-vs-local output-port decision guide, ArchUnit rules
- `reference/naming-conventions.md` — extracted from `dca-guide/architecture/package-structure.md`

### Wiring and metadata review

Check how operations are registered: a stereotype or configuration is equally valid.
Static references cannot prove runtime wiring; NAM-002 is informational only.
Presets also configure member roles (`injectionSite`, `persistenceMapping` in Java;
attribute namespace roles in .NET). Review prohibited roles on types and members,
including composed annotations/derived attributes; unknown metadata is unclassified
and allowed by these checks. Outgoing adapters can reuse own/global infrastructure,
while another module’s infrastructure remains private.

## Cross-sample contract checkpoint (D08)

For a shared behavior change, identify the counterpart implementation and the pinned specification revision. Review the counterpart change and spec revision together, including scenario fixtures and event JSON. An intentional difference needs the accepted compatibility note; do not silently fork behavior.
