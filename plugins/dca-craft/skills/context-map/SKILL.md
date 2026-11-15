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

Carrier of the **designed map**: patterns, subdomain types, map structure and the questions live here. A project
description, a delivery stage, a structural question, an existing project's setup or a person calls this skill.

## Two maps, two owners

| Map | Owner | Content |
|---|---|---|
| the designed map | this skill, by hand | the strategic reading: contexts with responsibility and subdomain type, relationships with pattern, translation and reason — "as designed", written before the code where a context is planned |
| a map generated from the code, where the project keeps one | its generator | which contexts exist and which dependencies they have. Never hand-edited; regenerate it |

A difference between them is a finding (planned not built, or built not designed) — never reconciled silently.

**Where the designed map is:** the `domain:` key of the configuration file `AGENTS.md` names
(``- configuration: `<file>` ``); else a project-description line ``- domain: `<path>` `` in the instructions
(typically `product/domain.md`); else `docs/context-map.md`. Never a second designed map beside the named one;
never a path from a configuration the instructions do not name.

## Map structure

Three sections.

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

These three columns are the minimum; a project tracking ownership adds `Owner`.

**Subdomain** is one of:

- **Core** — differentiator; most modelling effort, rich domain model, strictest rules and reviews.
- **Supporting** — necessary, not differentiating; transaction script or active record with the structural
  baseline is legitimate.
- **Generic** — commodity; buy or adopt, integrate behind an ACL. May be qualified: `Generic (UI)`, `Generic (Ops)`.

Where a decision record also declares each context's subdomain type and pattern style, map and record must agree;
disagreement is a `validate` finding.

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

- **Pattern** (Evans/Vernon): Customer/Supplier, Open Host Service (OHS), Published Language, Conformist,
  Anti-Corruption Layer (ACL), Shared Kernel (sparingly — tight coupling), Separate Ways, Partnership,
  Big Ball of Mud (diagnostic only — marks legacy boundaries).
- **Translation:** where and how the downstream turns the upstream's model into its own (adapter or translator), or
  "none" for a Conformist.
- **Reason:** why this shape. A relationship without a reason is a draft, not a design.

### 3. Mermaid diagram

A `## Diagram` section with a Mermaid `graph LR`: node style by subdomain type, edge style by pattern. Layout and
style tables: read `reference/mermaid.md` before writing or changing it.

## Questions when a context or a relationship is added

Ask them; never answer them for the person.

**A new context:**

- Responsibility in one sentence of the ubiquitous language — and what it is *not* responsible for that a neighbour
  could claim?
- Core, Supporting or Generic? (differentiating logic → Core; necessary plumbing → Supporting; replaceable by a
  product → Generic)
- Which existing context loses a responsibility to it?
- Which terms does it share with other contexts, and do they mean the same there?

**A new relationship:**

- Who is upstream — whose model changes, who follows?
- Synchronous (API) or asynchronous (events)?
- Translate (ACL), adopt (Conformist), or a published schema (Published Language)?
- Can the upstream be influenced (Customer/Supplier, Partnership) or not (Conformist, ACL toward an external system)?
- Why this shape and not a cheaper one — would Separate Ways do?

## Relationships declared in code

Where contexts or relationships are declared in code (annotation/attribute on a context's root package or type, a
module descriptor, framework module metadata), **the declaration is the source** for which contexts exist and their
dependencies: read it instead of guessing from imports; a map generated from it belongs to its generator. Subdomain
type, reason and often the pattern name stay in the designed map. This skill never writes such declarations
(project setup, not map craft).

## Operations

### `/context-map init`

First draft from the code, for a project with code and no map.

1. Find the contexts: declarations in code; else framework module metadata (e.g. Spring Modulith
   `@ApplicationModule`); else each directory below the base package containing the layer folders (`domain/`,
   `application/`, `adapter/`; C#: `Domain/`, `Application/`, `Adapter/`, usually one project per context).
2. Subdomain type: from the classification decision record if one exists; else ask per context with the heuristics
   above and suggest recording the answers.
3. Per pair of contexts: collect evidence (*Detection signals*), propose a pattern.
4. Write the three sections, mark every row as read from the code, ask for the reasons. The person confirms before
   the map counts.

### `/context-map update`

When a context or relationship changes: re-scan, diff against the map, propose:

```
Detected changes:
  + new context: 'reservation'
  + new relationship: lending → reservation (Published Language: ItemReturned)
  ! relationship changed: catalogue → lending changed from
    'Customer/Supplier' to 'Published Language' (now event-driven)
  - relationship removed: membership ↔ legacy-crm (no code references found)
```

Ask the questions above for every addition. The person confirms each change before it is applied.

### `/context-map validate`

Designed map against code; every difference is a finding:

- map OHS, downstream has no outgoing adapter for it → "designed but not implemented"
- downstream imports upstream's domain types, map says OHS → "implementation diverges from the designed pattern"
- context in code not on map / on map not in code → "built without being designed" / "designed, not built yet"
- map vs classification decision record → "classification mismatch — align map or record"
- **Generic** with a rich model (aggregates, domain events, invariants) → "over-investment in a generic subdomain,
  or misclassified"
- **Core** without invariants, only CRUD → "under-modelled core, or misclassified"

Output: findings list. The fix goes either way — map or code.

### `/context-map show <pattern>`

Explain one pattern (meaning, fit, cost) and list the map's relationships using it, with their translation.
`/context-map show ACL` answers "which integrations need attention if the upstream changes its schema".

### Onboarding

Explain the system from the map: core contexts first, then who depends on whom and why, then the riskiest
relationships (Conformist to a volatile upstream, Shared Kernel).

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

## Related skills

- `/ubiquitous-language`: shared term in two glossaries → document the polysemy, nudge toward ACL or Published
  Language.
- `/adr`: significant map changes (new context, ACL → Published Language, Conformist → ACL).

## Project conventions

The configuration file `AGENTS.md` names may set: module-discovery overrides (no declarations, no framework
metadata); a custom relationship column (e.g. "SLA", "Sync/Async", "Versioning"). Location: `domain:` (above).

## Not in scope

- Redesigning the architecture — records the design, proposes consistency fixes; redesign happens in workshops.
- Answering the questions — subdomain types and reasons come from the person who decides what is built.
- Editing a generated map.
- Mermaid styling beyond `reference/mermaid.md`.
- Replacing EventStorming or DDD workshops — captures their result.
