---
name: context-map
description: |
  Maintains a strategic DDD Context Map (`docs/context-map.md` with Mermaid
  diagram) showing relationships between bounded contexts (Customer/Supplier,
  Anti-Corruption Layer, Open Host Service, Shared Kernel, Published Language,
  Conformist, Separate Ways, Partnership) and each context's subdomain type
  (Core/Supporting/Generic — drives pattern choice and rule-set strictness).
  Use when introducing a new context, changing cross-context communication,
  classifying subdomains, or onboarding to understand the system.
disable-model-invocation: false
---

# /context-map — Strategic DDD context map

The context map is DDD's strategic-design centerpiece: which bounded contexts
exist, how they relate, who's upstream/downstream, and *what pattern* governs
each relationship. This skill keeps the map in sync with the code.

## Map location

Default: `docs/context-map.md` at repo root.

Alternative path can be set in `<project-root>/.claude/dca/conventions.md`.

## Map structure

The file contains three sections:

### 1. Contexts (list)

```markdown
## Bounded Contexts

| Context | Responsibility | Subdomain | Owner |
|---|---|---|---|
| catalog | Produkt-Stammdaten, Pricing-Lookups | Core | Team A |
| cart | Warenkorb für authentifizierte & Gast-Nutzer | Core | Team B |
| checkout | Bestellprozess, Payment-Initialisierung | Core | Team B |
| inventory | Verfügbarkeitsführung, Reservierung | Supporting | Team A |
| account | Kunden-Stammdaten, Auth | Supporting | Team C |
| portal | UI-Aggregation für Storefront | Generic (UI) | Team B |
| pricing | Preisermittlung, Promotions | Supporting | Team A |
| backoffice | Admin-UI für Stammdatenpflege | Generic (Ops) | Team A |
```

**Subdomain column** uses one of:

- **Core** — competitive differentiator; gets the most modeling effort, the
  rich domain model, and the full ArchUnit rule set.
- **Supporting** — necessary but not differentiating; transaction script /
  active record with the structural-baseline rule set is legitimate.
- **Generic** — commodity; buy/adopt and integrate via ACL. Qualify when
  helpful: `Generic (UI)`, `Generic (Ops)`.

The classification's source of truth is the project's **pattern-selection
ADR** (one ADR declaring each context's subdomain type and pattern style —
see ADR-025 in the reference implementation). If map and ADR disagree, that
is a `validate` finding. The classification drives pattern choice, ArchUnit
module selection (`/dca-bootstrap` "By subdomain type"), and where review
strictness applies (`/dca-review`).

### 2. Relationships (table)

```markdown
## Relationships

| Upstream | Downstream | Pattern | Realised via |
|---|---|---|---|
| catalog | cart | Customer/Supplier (OHS) | REST `/api/products/{id}` |
| inventory | checkout | Published Language | Event `StockReserved` |
| account | cart | Conformist | (no mapping; cart adopts account's user model) |
| legacy-erp | checkout | Anti-Corruption Layer | `ErpOrderMapper` in checkout/adapter/outgoing |
| catalog ↔ pricing | (mutual) | Partnership | Shared release schedule, mutual API contract |
```

**Pattern column** uses one of (Evans/Vernon strategic patterns):

- **Customer/Supplier** — upstream knows about downstream's needs; downstream
  has influence over upstream's API priorities.
- **Open Host Service (OHS)** — upstream publishes a stable API for many
  downstreams; downstream conforms or doesn't consume.
- **Published Language** — both sides agree on a third-party schema (often
  events).
- **Conformist** — downstream accepts upstream's model as-is; no translation.
- **Anti-Corruption Layer (ACL)** — downstream wraps upstream behind a
  translation layer to protect its own model.
- **Shared Kernel** — small piece of code both contexts depend on (use
  sparingly; tight coupling).
- **Separate Ways** — no integration; either context can ignore the other.
- **Partnership** — two teams coordinate releases and APIs as equals.
- **Big Ball of Mud** — diagnostic, not aspirational. Marks legacy boundaries.

### 3. Mermaid diagram

```markdown
## Diagram

\`\`\`mermaid
graph LR
  catalog -->|OHS REST| cart
  inventory -.->|Event: StockReserved| checkout
  account ==>|Conformist| cart
  legacyERP -->|ACL| checkout
  catalog <-->|Partnership| pricing

  catalog:::core
  cart:::core
  inventory:::supporting
  legacyERP:::generic

  classDef core stroke-width:3px;
  classDef supporting stroke-width:1px;
  classDef generic stroke:#888,color:#666;
\`\`\`
```

**Node-style convention (subdomain type):**

| Subdomain | Mermaid classDef | Visual |
|---|---|---|
| Core | `stroke-width:3px` | thick border |
| Supporting | default | normal border |
| Generic | `stroke:#888,color:#666` | gray |

(Keep `stroke-dasharray` reserved for Separate-Ways nodes so the two
dimensions — subdomain type and integration pattern — stay distinguishable.)

**Edge-style convention:**

| Pattern | Mermaid syntax | Visual |
|---|---|---|
| OHS / Customer-Supplier | `-->` | solid arrow |
| Published Language (events) | `-.->` | dotted arrow |
| Conformist | `==>` | thick arrow |
| ACL | `-->` with `\|ACL\|` label | solid + label |
| Partnership | `<-->` | bidirectional |
| Shared Kernel | dashed bidirectional `<-.->` | dashed bidir |
| Separate Ways | (omit edge) | — |

## Operations

### `/context-map init`

First-time generation.

1. Scan repo for bounded contexts:
   - Look for `@BoundedContext` annotations on `package-info.java`.
   - Look for `@ApplicationModule` annotations (Spring Modulith).
   - Fall back to: each directory under `{basePackage}/` that contains
     `domain/` + `application/` + `adapter/`.
2. Classify each context's subdomain type:
   - Read the project's pattern-selection ADR (`docs/architecture/adr/`,
     look for "pattern selection" / "subdomain") if one exists.
   - Otherwise ask the user per context ("Is `{context}` core, supporting,
     or generic?") — heuristic prompts: differentiating business logic →
     core; necessary plumbing → supporting; replaceable by a product →
     generic. Suggest recording the answers in a pattern-selection ADR.
3. For each pair (context A, context B), scan for relationship evidence:
   - **OHS**: A has `adapter/incoming/api/*Resource.java`; B has
     `adapter/outgoing/{a}/*Client.java` (or REST template calls to `/api/...`)
   - **Published Language**: B's code (in `adapter/incoming/event/`)
     listens to events that A publishes (in `adapter/outgoing/event/` or via
     `@ApplicationModuleListener` on A's domain event).
   - **ACL**: B has a mapper class that translates A's types into its own
     domain (look for `*Mapper`, `*Translator` in B's adapter that imports
     from A — and verify A's types do NOT appear in B's domain or app).
   - **Conformist**: B's domain imports A's domain directly with no mapping
     layer. (DCA rules flag this — but if it exists, document it.)
   - **Shared Kernel**: a module marked `Type.OPEN` (Spring Modulith) or in
     `sharedkernel/` with value objects both contexts use.
4. Generate the three sections. Open it for the user to review.

### `/context-map update`

Re-scan, diff against existing map, propose changes:

```
Detected changes:
  + new context: 'shipping'
  + new relationship: shipping ← checkout (Published Language: OrderPaid)
  ! relationship changed: inventory → checkout changed from
    'Customer/Supplier' to 'Published Language' (now event-driven)
  - relationship removed: catalog ↔ legacy-erp (no code references found)
```

User confirms each change before applying.

### `/context-map validate`

Cross-check map against code:

- Map says `catalog → cart` is OHS, but no REST adapter in cart's outgoing →
  finding "documented but not implemented".
- Code has cart importing `catalog.domain.Product` directly, but map says
  "OHS" → finding "implementation diverges from documented pattern".
- Subdomain classification in the map disagrees with the pattern-selection
  ADR → finding "classification mismatch — align map or ADR".
- A context classified **Generic** has a rich domain model with aggregates
  and domain events → finding "over-investment in generic subdomain
  (or misclassification)". The inverse (core context as bare CRUD) is also
  flagged.

Output: list of mismatches. The fix can go either way (update map, or
refactor code).

### `/context-map show [pattern]`

Filter view. `/context-map show ACL` lists only ACL relationships and the
mappers that realize them. Useful for "which integrations need attention if
we change the upstream's event schema".

## Auto-detection signals (summary)

| Signal | Implies pattern |
|---|---|
| `@ApplicationModule(allowedDependencies = {"X"})` | A consumes X; check what kind |
| `*Mapper` in B/adapter that imports A | ACL |
| `@TransactionalEventListener` on A's event in B | Published Language |
| B's controller calls `/api/...` of A | OHS |
| B's domain has direct import of A's domain | Conformist (flag for review!) |
| Module marked `Type.OPEN` exporting value objects | Shared Kernel |
| Two contexts in same module / no boundary | Big Ball of Mud (flag!) |
| `dca-discipline` rule 3 violation in stable code | Conformist or undocumented dependency |

## Relationship to other skills

- **`/ubiquitous-language`** — When the map shows two contexts share a term
  (`Customer` appears in both glossaries), this skill nudges toward
  documenting the polysemy and adding an ACL or PL.
- **`/dca-discipline`** — Rule 3 (bounded-context isolation) is the runtime
  guardrail; this skill is the strategic map view of the same truth.
- **`/adr`** — Significant map changes (new context, ACL → PL migration,
  Conformist → ACL upgrade) should be recorded as ADRs.
- **`/dca-bootstrap`** — The Subdomain column feeds module selection ("By
  subdomain type"): core contexts get the full ArchUnit rule set, supporting
  contexts the structural baseline. Reclassification (supporting → core) means
  upgrading the rule set — update the pattern-selection ADR alongside the map.
- **`/dca-review`** — Reads the classification to calibrate strictness:
  tactical-DDD findings apply to domain-model contexts, not to declared
  transaction-script contexts.

## Conventions overlay

`<project-root>/.claude/dca/conventions.md` may set:

- Alternative map path
- Module-discovery overrides (if the project doesn't use Spring Modulith
  annotations)
- Custom relationship column (e.g. "SLA", "Sync/Async", "Versioning")

## What this skill does NOT do

- **Doesn't redesign the architecture.** It documents what exists and
  proposes minor consistency fixes. Strategic redesign happens in workshops,
  not in a skill.
- **Doesn't auto-generate Mermaid styling beyond the table above.** Custom
  visual choices stay manual.
- **Doesn't replace EventStorming / DDD workshops.** It captures the *result*
  of those workshops in a maintainable form.
