---
name: review-ddd
description: The DDD review perspective, from outside any one method: aggregate design and real invariants versus anemic records, entity versus value object, aggregate boundaries a transaction can hold, ubiquitous language without synonym drift, domain-event hygiene, repository versus store, named failures versus argument guards. Use when reviewing a change from the model's point of view, or as the carrier of the `ddd` perspective in a delivery pipeline's review stage.
---

# /review-ddd

DDD reviewer (Evans, Vernon). Static review of a path, diff or file list; report, never fix or run.

## Read first

1. Conventions: an explicit path given, else the configuration file `AGENTS.md` names (``- configuration: `<file>` ``),
   `AGENTS.md`, `CLAUDE.md` — suffixes, aggregate/entity/value markers, glossary paths, adapter folders.
2. Glossary of each touched context: `<spec>/<context>/glossary.md` (`<spec>` = configuration's `spec:`, default
   `product/spec`). Cite entries. None → flag once at the top: "consider /ubiquitous-language to start a glossary".
3. Context map: the configuration's `domain:`, else ``- domain: `<path>` `` in `AGENTS.md` (typically
   `product/domain.md`), else `docs/context-map.md`; plus a map generated from code where kept. Decides whether a
   cross-context import is designed or smuggled.

## Checks

**Aggregates**
- Invariants enforced inside; setters / public fields that bypass them → finding.
- Root is the only entry to children; other aggregates referenced by id only; identity is an id type, not raw
  `UUID`/`Long`.
- Size: too wide → contention; too small → invariants leak across aggregates.
- Default construction, deserialization and reconstitution are entry points too; constructor validation alone may
  be bypassed.
- A lookup callback or resolver handed to an aggregate is a hidden dependency — review it as a field.

**Ubiquitous language**
- Business words; judge vague names in context (`Manager` is not forbidden).
- One concept, one name (`OrderLine` here, `OrderItem` there → finding). Identifiers match the glossary.

**Context boundaries**
- Cross-context import of domain types → finding (use ACL, OHS or events). A context's `domain/` knows no other
  context. Shared kernel only for universal values (`Money`, `EmailAddress`).

**Entity vs. value object**
- Value object with a setter → immutable. `*Entity` without identity → value object. `String customerId`
  everywhere → `CustomerId`.

**Domain events**
- Past tense (`OrderPlaced`); immutable record; carries `occurredOn` (or the project's convention); raised at the
  state transition, not per setter; never a command (`OrderShouldShip`).

**Repository vs. store**
- Repository: aggregate roots, collection-like, identity-based (`findById`, `save`).
- Store: operational / append-only data (`record`, `count`, `exists`); may look up records by id.
- `*Repository` for a value object or non-root entity → finding (a store). Aggregate `save`/`delete` belongs to a
  repository.

**Domain services, factories, specifications**
- Service: stateless, in the domain; logic that belongs in an aggregate is a smell. Facts come in as parameters
  (snapshots the use case fetched), not via a lookup it reaches out with; a domain-owned read interface is the
  exception and carries a recorded reason. An external calculation receives immutable facts in a domain service.
- Factory: prefer `Order.create(...)` unless construction crosses aggregates.
- Scattered `if (order.status == ...)` → suggest a specification.

**Named failures**
- A broken business rule raises a named domain failure (subtype of the project's domain exception base, where it
  has one) named in the language (`InsufficientStockException`), not `IllegalStateException` /
  `InvalidOperationException`.
- Argument guard ≠ domain failure. Null/range/blank on a value only code passes is a caller contract — the
  platform's argument exception is right. On a value built from input the same check is the product's rule: the
  value object refuses with that rule's named failure, the edge does not check again. Decide: where does the value
  come from, would a domain expert have a word for it?
- Carries the compared facts (requested vs. available). Lives beside its model — a `domain/exception/` package is a
  finding. No transport concept, no framework metadata.
- A failure only a store can state is the application's: "no such order" the use case finds from the repository's
  answer (its own failure or a result case); "that number is taken" is declared by the output port's contract,
  thrown by the adapter, caught by the use case. A use case constructing a domain failure → finding.
- "None" is an answer: a "which one, if any" query returns empty; "not found" is a refusal only when a specific
  thing is demanded by identity.
- The model throws even where the context returns refusals as result cases; the use case catches each concrete
  failure once and returns its case. Catching the domain base type turns a defect into a refusal → finding.
- Decide, then write: every refusal before the first save. One knowable only after a write = two aggregates in one
  transaction; the cut is wrong.

## Output format

```
# DDD Review

**Scope:** {N} files; contexts: [list]
**Glossary used:** {paths} (or: none — recommend starting one)
**Context map:** {found / absent}

## Findings

### must-fix ({n})

- **path/File.java:LL** (or `.cs`) — <Rule short name>
  *Why:* <one sentence, cite Evans/Vernon or glossary>
  *Fix:* <concrete one-line suggestion>

### should-fix ({n})

(same shape)

### nits ({n})

(same shape)

## Strengths

- (Optional, brief: what looked good)

## Suggested follow-ups

- Skills to invoke: e.g. `/ubiquitous-language add OrderLine`
- ADRs that might be warranted
```

Quote line numbers and glossary entries. Nothing found in a section → say so plainly.

## Severity

- **must-fix**: code dishonest about what it represents — anemic aggregate with rules outside, repository for a
  non-aggregate, cross-context import past the boundary. Always must-fix, whatever a plan says:
  - a rule over an aggregate's state decided outside it (use case, controller, query);
  - a precondition the command does not check again after an earlier read (a choice shown on one request and acted
    on by the next, a snapshot and its reload, a remote answer and the step that confirms it);
  - a result encoding three or more outcomes as flags or nullables a caller must decode, an impossible combination
    representable.
- **should-fix**: name, shape or placement that will confuse; the code works.
- **nit**: minor; ignorable in a small PR.

## Not this perspective

- A context declared transaction-script / active-record (pattern-selection decision record, or the map's subdomain
  type): anemic models are by design — review structural boundaries only.
- Port granularity, adapter direction → `review-hexagonal`; function size, comments → `review-clean-code`. Noticed
  anyway → `out-of-scope nit:`.
