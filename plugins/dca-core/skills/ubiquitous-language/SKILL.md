---
name: ubiquitous-language
description: |
  Maintains a per-bounded-context Ubiquitous Language glossary (`glossary.md`
  per context) and checks code naming for consistency. Use when adding a new
  domain concept, renaming an existing one, or auditing naming drift. Updates
  the glossary, finds outdated terms in code, and proposes consistent renames.
disable-model-invocation: false
---

# /ubiquitous-language — Domain glossary per bounded context

The Ubiquitous Language is DDD's most underused tool. This skill keeps it
**alive**: a maintained glossary per bounded context, plus checks that the
code agrees with the glossary.

When the glossary and the code disagree, one of them is wrong. The skill
surfaces the mismatch; the user (or domain expert) decides which side moves.

## Glossary location

Default: one `glossary.md` per bounded context, co-located with the domain
code:

```
{basePackagePath}/{context}/domain/glossary.md
```

Alternative path can be set in `<project-root>/.claude/dca/conventions.md`.

## Glossary entry format

Every entry uses this shape:

```markdown
### Order

**Definition:** Vom Kunden bestätigter Kaufwunsch über eine oder mehrere
Positionen, der zur Auslieferung führt.

**Type:** Aggregate Root

**Identity:** `OrderId` (UUID)

**Synonyms (avoid):** ~~Purchase~~, ~~Booking~~ — diese Begriffe waren in
früheren Iterationen im Umlauf, sind aber abgelöst.

**Related terms:**
- `OrderLine` (Entity inside the aggregate)
- `OrderPlaced` (Domain Event)
- `Customer` (referenced by ID, lives in `customer` context)

**Operations:** `place`, `cancel`, `markPaid`, `fulfill`
```

Required fields: `Definition`, `Type`.
Optional: `Identity`, `Synonyms (avoid)`, `Related terms`, `Operations`, `Notes`.

`Type` is one of: `Aggregate Root`, `Entity`, `Value Object`, `Domain Event`,
`Integration Event`, `Domain Service`, `Specification`, `Concept` (anything else).

## Operations

### `/ubiquitous-language add <Term>`

1. Determine which context the term belongs to. If unclear, ask.
2. Check whether the term already exists in this context's glossary →
   refuse with "already defined, did you mean update?".
3. Check whether the term exists in **other** contexts → warn, propose a
   cross-reference. Same word in two contexts is OK (DDD allows it), but
   surface it so the user is conscious of it.
4. Check whether the term appears in code as a different word (e.g. user
   says "Order", but code uses "Purchase") → suggest renaming the code or
   adding the code term as a synonym.
5. Write the entry. Add cross-references in related entries.

### `/ubiquitous-language check [path]`

Default scope: changed files (git diff). Optional explicit path.

For each Java file:

1. Determine the context (from path).
2. Read the context's `glossary.md`.
3. Extract identifiers (class names, method names, field names).
4. For each identifier:
   - Is it in the glossary? ✓ silent pass.
   - Is it a near-miss synonym (`OrderItem` vs glossary's `OrderLine`)? → finding.
   - Is it a generic technical name (`*Helper`, `*Util`, `*Manager`, `*Data`,
     `*Info`)? → finding (suggests a domain name).
   - Is it absent from glossary entirely (and looks domain-significant)? →
     suggest adding to glossary.

Output: report grouped by file, with severity:

- **must-fix:** identifier is a deprecated synonym (struck-through in glossary)
- **should-fix:** near-miss spelling or generic technical name
- **nit:** new domain concept not in glossary yet (propose `add`)

### `/ubiquitous-language rename <Old> <New>`

1. Confirm both terms — read glossary to see if `Old` exists.
2. Show plan: code files affected, glossary entries to update, related
   contexts that reference `Old` and need updating.
3. Mark `Old` as superseded in the glossary (`Synonyms (avoid)` of `New`).
4. On user confirmation: perform the rename via search-and-replace **with
   the user reviewing each change** (don't auto-apply across the whole repo).
5. Suggest `/adr new "Rename {Old} to {New} in {Context} context"` if the
   rename is substantial.

### `/ubiquitous-language audit`

Cross-context audit:

- Find terms that appear in two+ glossaries → list as "polysemous" (might
  be fine, might need an ACL).
- Find glossary entries that no longer appear in code → propose Cleanup
  (delete or mark deprecated).
- Find code identifiers that look domain-significant but aren't in any
  glossary → propose `add`.

## Anti-patterns flagged

- **Technical-prefix names in domain:** `OrderDto`, `OrderEntity`,
  `OrderHelper`, `OrderManager` inside `domain/`. DTOs live in adapters;
  Entities are the domain (no need for the suffix); helpers/managers betray
  procedural thinking, not DDD.
- **Domain-foreign vocabulary:** `processItem`, `executeAction`,
  `handleRequest`. The Ubiquitous Language has *verbs from the business*,
  not from the implementation.
- **Same term, two contexts, no acknowledgment:** `Customer` in `sales` and
  `Customer` in `support` may legitimately mean different things. If both
  glossaries define it without referencing each other, the team is at risk
  of confusion. Suggest making the polysemy explicit.
- **Glossary as documentation of code:** entries that just describe what a
  class does ("OrderRepository is a Spring Data interface...") miss the
  point. The glossary is about the **business term**, independent of code.

## Relationship to other skills

- **`/clean-code`** — Clean Code says "names should reflect intent". This
  skill provides the *agreed-on* intent. Together: clean code uses the
  glossary's words; this skill keeps the glossary accurate.
- **`/dca-discipline`** — DCA's bounded-context isolation rule means the
  same term in two contexts is allowed, but the *code* must not couple them.
  This skill makes that polysemy visible.
- **`/context-map`** — If two contexts share a term in their glossaries and
  also have a code-level relationship in the context map, this skill nudges
  you toward an Anti-Corruption Layer or Published Language.
- **`/adr`** — Substantial language changes (renaming an aggregate, retiring
  a concept) deserve an ADR for posterity.

## Conventions overlay

Read `<project-root>/.claude/dca/conventions.md` for:

- Custom glossary location (e.g. `docs/glossary/{context}.md` instead of
  inline)
- Custom glossary format (e.g. mandatory `Examples:` section)
- Project-wide forbidden suffixes beyond the defaults

## What this skill does NOT do

- **Doesn't auto-generate definitions.** The user / domain expert writes
  the *Definition* prose. Claude can suggest, but the human ratifies.
- **Doesn't translate.** If the project's Ubiquitous Language is in German
  (e.g. `Bestellung`, `Auftrag`), keep it German. Don't anglicize.
- **Doesn't enforce length.** A glossary entry can be one sentence or one
  paragraph. The point is shared meaning, not exhaustive docs.
