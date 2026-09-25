---
name: context-map
description: |
  Maintains the designed strategic DDD Context Map (where the project
  instructions name it — `docs/context-map.md` by default — with a Mermaid
  diagram): the bounded contexts with their subdomain type (Core/Supporting/
  Generic — drives modelling effort and how strict rules and reviews are) and
  the relationships between them (Customer/Supplier, Anti-Corruption Layer,
  Open Host Service, Shared Kernel, Published Language, Conformist, Separate
  Ways, Partnership) with the translation and the reason for each. Use when
  introducing a context or a relationship, drafting a map from existing code,
  checking the map against the code, explaining one pattern, onboarding to a
  system, or as the carrier of the designed map for another skill or a
  delivery stage.
disable-model-invocation: false
---

# /context-map — Strategic DDD context map

The context map is DDD's strategic-design centerpiece: which bounded contexts
exist, what kind of subdomain each one is, how they relate, who is upstream
and downstream, and *which pattern* governs each relationship — and why.

This skill is the carrier of the **designed map**. Whoever needs one — a
project description, a delivery pipeline's document stage, the answer to a
structural question, the setup of an existing project, a person — calls it;
the patterns, the subdomain types, the map's structure and the questions to
ask live here, in one place.

## Two maps, two owners

| Map | Owner | Content |
|---|---|---|
| the designed map | this skill, by hand | the strategic reading: contexts with responsibility and subdomain type, relationships with pattern, translation and reason — "as designed", written before the code where a context is planned |
| a map generated from the code, where the project keeps one | its generator | which contexts exist and which dependencies they have. Never hand-edited; regenerate it |

A difference between the two is a finding — a context planned and not built
yet, or built without being designed — never a duplicate to reconcile
silently.

**Where the designed map is.** Read the project instructions (`AGENTS.md`)
first: a project description section names it as ``- domain: `<path>` ``
(typically `project/domain.md`). Where no line names it, the default is
`docs/context-map.md`. Never write a second designed map beside the one the
instructions name, and never read another tool's configuration for the path.

## Map structure

The designed map has three sections.

### 1. Bounded contexts

```markdown
## Bounded contexts

| Context | Responsibility | Subdomain |
|---|---|---|
| lending | Loans, renewals and returns of items | Core |
| catalogue | Items and their availability for loan | Supporting |
| membership | Members, their standing and limits | Supporting |
| notification | Reminders by mail and push | Generic |
```

A project that tracks ownership adds an `Owner` column; the three above are
the minimum.

**Subdomain** is one of:

- **Core** — the competitive differentiator; it gets the most modelling
  effort, the rich domain model, and the strictest rules and reviews.
- **Supporting** — necessary but not differentiating; a transaction script or
  active record with the structural baseline is legitimate.
- **Generic** — a commodity; buy or adopt, and integrate behind an
  Anti-Corruption Layer. Qualify when helpful: `Generic (UI)`, `Generic (Ops)`.

Where the project records the classification in a decision record as well
(one record declaring each context's subdomain type and pattern style), map
and record must agree; a disagreement is a `validate` finding.

### 2. Relationships

```markdown
## Relationships

| Upstream | Downstream | Pattern | Translation | Reason |
|---|---|---|---|---|
| catalogue | lending | Customer/Supplier (OHS) | lending's outgoing adapter maps the catalogue API into its own `LoanableItem` | lending needs availability, not the catalogue's item model |
| membership | lending | Conformist | none — lending adopts membership's standing as is | the standing rules are membership's and lending must not reinterpret them |
| lending | notification | Published Language | notification reads the `LoanOverdue` event schema | reminders follow loans, never the other way round |
| payment provider | membership | Anti-Corruption Layer | a translator in membership's outgoing adapter | the provider's model changes with its releases |
```

**Pattern** is one of (Evans/Vernon strategic patterns):

- **Customer/Supplier** — upstream knows the downstream's needs; the
  downstream influences the upstream's API priorities.
- **Open Host Service (OHS)** — upstream publishes a stable API for many
  downstreams; a downstream conforms or does not consume.
- **Published Language** — both sides agree on a shared, documented schema
  (often events).
- **Conformist** — the downstream adopts the upstream's model as is; no
  translation.
- **Anti-Corruption Layer (ACL)** — the downstream wraps the upstream behind
  a translation layer to protect its own model.
- **Shared Kernel** — a small piece of model both contexts depend on (use
  sparingly; tight coupling).
- **Separate Ways** — no integration; either context can ignore the other.
- **Partnership** — two teams coordinate releases and APIs as equals.
- **Big Ball of Mud** — diagnostic, not aspirational. Marks legacy boundaries.

**Translation** says where and how the downstream turns the upstream's model
into its own — the adapter or translator, or "none" for a Conformist.
**Reason** says why the relationship has this shape; a relationship without a
reason is a draft, not a design.

### 3. Mermaid diagram

```markdown
## Diagram

\`\`\`mermaid
graph LR
  catalogue -->|OHS| lending
  membership ==>|Conformist| lending
  lending -.->|Event: LoanOverdue| notification
  paymentProvider -->|ACL| membership

  lending:::core
  catalogue:::supporting
  membership:::supporting
  notification:::generic

  classDef core stroke-width:3px;
  classDef supporting stroke-width:1px;
  classDef generic stroke:#888,color:#666;
\`\`\`
```

**Node style (subdomain type):**

| Subdomain | Mermaid classDef | Visual |
|---|---|---|
| Core | `stroke-width:3px` | thick border |
| Supporting | default | normal border |
| Generic | `stroke:#888,color:#666` | gray |

(Keep `stroke-dasharray` reserved for Separate-Ways nodes so the two
dimensions — subdomain type and integration pattern — stay distinguishable.)

**Edge style (pattern):**

| Pattern | Mermaid syntax | Visual |
|---|---|---|
| OHS / Customer-Supplier | `-->` | solid arrow |
| Published Language (events) | `-.->` | dotted arrow |
| Conformist | `==>` | thick arrow |
| ACL | `-->` with `\|ACL\|` label | solid + label |
| Partnership | `<-->` | bidirectional |
| Shared Kernel | `<-.->` | dashed bidirectional |
| Separate Ways | (omit edge) | — |

## Questions when a context or a relationship is added

Ask them; never answer them for the person.

**A new context:**

- What is it responsible for, in one sentence of the ubiquitous language —
  and what is it *not* responsible for that a neighbour could claim?
- Core, Supporting or Generic? Differentiating business logic → Core;
  necessary plumbing → Supporting; replaceable by a product → Generic.
- Which existing context loses a responsibility to it, if any?
- Which terms does it share with other contexts, and do they mean the same
  thing there?

**A new relationship:**

- Who is upstream — whose model changes, and who has to follow?
- Synchronous (an API) or asynchronous (events)?
- Does the downstream translate (ACL), adopt the model (Conformist), or do
  both sides agree on a published schema (Published Language)?
- Can the upstream be influenced (Customer/Supplier, Partnership), or not
  (Conformist, ACL toward an external system)?
- Why this shape and not a cheaper one — would Separate Ways do?

## Relationships declared in code

Where the project declares its contexts or their relationships in code — an
annotation or attribute on a context's root package or type, a module
descriptor, a framework's module metadata — **that declaration is the source**
for which contexts exist and which dependencies they have. The skill then
reads the declarations instead of guessing from imports, and a map generated
from them belongs to its generator. What a declaration cannot carry — the
subdomain type, the reason, often the pattern name — stays in the designed
map. The skill does not write such declarations; that is the project's setup,
not the map's craft.

## Operations

### `/context-map init`

A first draft from the code, for a project that has code and no map.

1. Find the bounded contexts:
   - declarations in code (see above), where the project has them;
   - a framework's module metadata (e.g. Spring Modulith `@ApplicationModule`);
   - otherwise each directory below the base package that contains the
     project's layer folders (`domain/`, `application/`, `adapter/`; C#:
     `Domain/`, `Application/`, `Adapter/`, usually one project per context).
2. Classify each context's subdomain type: read the classification decision
   record if one exists; otherwise ask per context, with the heuristics
   above, and suggest recording the answers.
3. For each pair of contexts, collect relationship evidence (see
   *Detection signals*) and propose a pattern.
4. Write the three sections, mark every row as read from the code, and ask
   for the reasons — code cannot tell why. The person confirms before the
   map counts.

### `/context-map update`

Bring the map in line when a context or a relationship changes. Re-scan,
diff against the existing map, propose changes:

```
Detected changes:
  + new context: 'reservation'
  + new relationship: lending → reservation (Published Language: ItemReturned)
  ! relationship changed: catalogue → lending changed from
    'Customer/Supplier' to 'Published Language' (now event-driven)
  - relationship removed: membership ↔ legacy-crm (no code references found)
```

Ask the questions above for every added context or relationship. The person
confirms each change before it is applied.

### `/context-map validate`

The designed map against the code; every difference is a finding:

- Map says `catalogue → lending` is OHS, but lending has no outgoing adapter
  for it → "designed but not implemented".
- Code has lending importing catalogue's domain types directly, but the map
  says OHS → "implementation diverges from the designed pattern".
- A context in the code that is not on the map, or the reverse → "built
  without being designed" / "designed, not built yet".
- The map's classification disagrees with the classification decision record
  → "classification mismatch — align map or record".

And plausibility:

- A **Generic** context with a rich model — aggregates, domain events,
  invariants → "over-investment in a generic subdomain, or misclassified".
- A **Core** context without invariants, only CRUD → "under-modelled core,
  or misclassified".

Output: a list of findings. The fix can go either way — update the map, or
change the code.

### `/context-map show <pattern>`

Explain one pattern — what it means, when it fits, what it costs — and list
the relationships on the map that use it, with their translation.
`/context-map show ACL` answers "which integrations need attention if the
upstream changes its schema".

### Onboarding

Read the map and explain the system: the core contexts first, then who
depends on whom and why, then the relationships whose reason carries the most
risk (Conformist to a volatile upstream, Shared Kernel).

## Detection signals

| Signal | Implies |
|---|---|
| a relationship declared in code on the context root | exactly what it says — the declaration is the source |
| `@ApplicationModule(allowedDependencies = {"X"})` | the module consumes X; check what kind |
| a `*Mapper` / `*Translator` in B's adapter that imports A, with A's types absent from B's domain and application | ACL |
| B's event consumer listens to an event A publishes | Published Language |
| B's outgoing adapter calls A's API | OHS or Customer/Supplier |
| B's domain imports A's domain directly | Conformist (flag for review!) |
| a module exporting value objects both contexts use | Shared Kernel |
| two contexts in one module, no boundary | Big Ball of Mud (flag!) |

## Relationship to other skills

- **`/ubiquitous-language`** — When two contexts share a term in their
  glossaries, this skill nudges toward documenting the polysemy and toward an
  ACL or a Published Language.
- **`/adr`** — Significant map changes (a new context, ACL → Published
  Language, Conformist → ACL) are worth a decision record.

## Project conventions

The conventions file the project instructions name (a
``- conventions: `<path>` `` line in `AGENTS.md`) may set:

- module-discovery overrides, where the project uses neither declarations nor
  framework module metadata;
- a custom relationship column (e.g. "SLA", "Sync/Async", "Versioning").

The designed map's location comes from the ``- domain: `<path>` `` line, not
from the conventions.

## What this skill does NOT do

- **Doesn't redesign the architecture.** It records the design and proposes
  consistency fixes. Strategic redesign happens in workshops, not in a skill.
- **Doesn't answer the questions itself.** Subdomain types and reasons come
  from the person who decides what is built.
- **Doesn't edit a generated map.** Its generator owns it.
- **Doesn't auto-generate Mermaid styling beyond the tables above.** Custom
  visual choices stay manual.
- **Doesn't replace EventStorming or DDD workshops.** It captures their
  *result* in a maintainable form.
