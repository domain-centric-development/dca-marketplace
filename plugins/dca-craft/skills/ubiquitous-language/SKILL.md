---
name: ubiquitous-language
description: |
  Maintains a per-bounded-context Ubiquitous Language glossary (`glossary.md`
  per context) and checks code naming for consistency. Use when adding a new
  domain concept, renaming an existing one, or auditing naming drift, and as
  the carrier of the glossary for any skill or delivery stage that enters a
  term. Holds the one glossary format; updates the glossary, finds outdated
  terms in code, and proposes consistent renames.
disable-model-invocation: false
---

# /ubiquitous-language — Domain glossary per bounded context

- The one place the glossary's location and format are defined. A skill that builds domain types, or a delivery
  stage, enters a term through this skill, never with an entry shape of its own.
- Glossary and code disagree → surface it; the user / domain expert decides which side moves.

## Glossary location

```
{spec}/{context}/glossary.md        # default: product/spec/{context}/glossary.md
```

- `{spec}`: the `spec:` key of the configuration file `AGENTS.md` names (``- configuration: `<file>` ``);
  `product/spec` where file or key is absent. A project naming its own glossary place there keeps it.
- `{context}`: context name lowercased, words joined by `-` (`Product Catalog` → `product-catalog`).
- The glossary is the one spec file a skill writes; the scenarios beside it change only through a delivery.
- Glossaries still beside the domain code: move them (the delivery pipeline's update where there is one, else
  `git mv`). Never start a second glossary beside one.
- **Shared kernel** (model several contexts share identically): `{spec}/shared-kernel/glossary.md`, same format;
  no context — no scenarios, no features. A context names a shared term where it uses it (an aggregate's
  `**Identity:**` line names its shared id) and never defines it again.
- **Designed context without a glossary file:** its section of words in the project description is its glossary.
  The first entry written to the file moves the section's rows with it and leaves one line naming the file —
  moved, not copied.

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

**Operations:** aufgeben (`place`), stornieren (`cancel`), als bezahlt markieren (`markPaid`),
ausliefern (`fulfill`)
```

- Required: `Definition`, `Type`; `Operations` too for every domain term with operations a person of the domain
  names. Optional: `Identity`, `Synonyms (avoid)`, `Related terms`, `Notes`.
- `Type` is one of: `Aggregate Root`, `Entity`, `Value Object`, `Domain Event`, `Integration Event`,
  `Domain Service`, `Specification`, `Feature`, `Use Case`, `Concept` (anything else).
- Heading: the term as its owners say it, plus the code's word in parentheses where it differs —
  `### Titel (TaskTitle)`. Readers and checks find it by either word; code word alone = a glossary of the code.

### What a glossary covers

- **Domain:** aggregates, entities, value objects carrying meaning (each with its operations); domain events and
  the integration events other contexts read.
- **Application:** features and use cases.
- **Feature** = a term, `**Type:** Feature`: behaviour its people name; groups use cases and, with a living spec,
  a folder `<spec>/<context>/<feature>/scenarios.md`. Heading carries the package spelling:
  `### Produktdetails (productdetails)`. Definition says what it groups; `Related terms` its use cases where the
  code mirrors them.
- Test for a term and an operation alike: would a person of the domain name it? Not entered: constructors and
  conversions (`of`, `fromHash`), getters, purely technical objects.

### Operations are entered like terms

- `Operations` lists commands and queries (*is it available*, *does it match*) a domain person names.
- Domain verb, code word in parentheses where it differs: `anlegen (create)`, `erledigen (complete)`. Where the
  domain word could name more than one operation, add one line saying which.
- The code word is a modelling decision, asked, never chosen while translating: *anlegen* = *create* (comes into
  existence) or *add* (goes into a collection); *löschen* = *delete* (gone) or *cancel*/*archive* (kept, with a
  state). The effect decides which object holds the rules.
- How to ask (event first, Event-Storming grammar) and how to look up the field's vocabulary per context:
  read `reference/entering-operations.md` before entering an operation.
- Code names follow the entry: the code word names method, command and whatever calls the operation; the event is
  term + past participle (`OrderPlaced` for `place`).

## Operations

### `/ubiquitous-language add <Term>`

1. Determine the context; unclear → ask.
2. Term already in this context's glossary → refuse: "already defined, did you mean update?".
3. Term in **other** contexts → warn, propose a cross-reference (allowed, but make it conscious).
4. Term in code under another word (user says "Order", code "Purchase") → suggest renaming the code or adding the
   code term as a synonym.
5. For an operation: follow `reference/entering-operations.md` (lookup, then event, then code word, then which
   effect). Enter it on the term it acts on, never as a heading of its own.
6. Write the entry; add cross-references in related entries.

### `/ubiquitous-language check [path]`

Scope: changed files (git diff) by default, or the path. Per source file (`*.java`, `*.cs`): context from the
path, read its `glossary.md`, extract class/method/field identifiers:

- in the glossary → silent pass
- near-miss synonym (`OrderItem` vs `OrderLine`) → finding
- names an operation by a verb the term's `Operations` lack (`addEntry` where the glossary says `create`) → finding
- generic technical name (`*Helper`, `*Util`, `*Data`, `*Info`) → finding, suggest a domain name. `*Manager` is
  domain vocabulary when the glossary says so (`PortfolioManager`)
- absent and domain-significant → suggest `add`

Report grouped by file:

- **must-fix:** identifier is a deprecated synonym (struck-through in glossary)
- **should-fix:** near-miss spelling or generic technical name
- **nit:** new domain concept not in glossary yet (propose `add`)

### `/ubiquitous-language rename <Old> <New>`

1. Read the glossary: does `Old` exist?
2. Show plan: affected code files, glossary entries, other contexts referencing `Old`.
3. Mark `Old` superseded (`Synonyms (avoid)` of `New`).
4. On confirmation: search-and-replace with the user reviewing each change — never auto-apply repo-wide.
5. Substantial rename → suggest `/adr new "Rename {Old} to {New} in {Context} context"`.

### `/ubiquitous-language audit`

- Term in 2+ glossaries → list as "polysemous" (fine, or needs an ACL).
- Glossary entry no longer in code → propose cleanup (delete or mark deprecated).
- Domain-significant code identifier in no glossary → propose `add`.

## Anti-patterns flagged

- `OrderDto`, `OrderEntity`, `OrderHelper`, `OrderManager` inside `domain/` (DTOs belong in adapters; entity
  needs no suffix).
- Implementation verbs: `processItem`, `executeAction`, `handleRequest`.
- Same term in two contexts, glossaries not referencing each other → suggest making the polysemy explicit.
- Entry describing a class ("OrderRepository is a Spring Data interface…") instead of the business term.

## Related skills

- `/clean-code` uses the glossary's words; this skill keeps them accurate.
- Same term in two contexts is allowed; the project's architecture rules keep the code apart.
- `/context-map`: shared term + a code-level relationship → nudge toward ACL or Published Language.
- `/adr`: substantial language changes (renaming an aggregate, retiring a concept).

## Project conventions

From the configuration file `AGENTS.md` names (``- configuration: `<file>` ``), or `AGENTS.md` itself:

- glossary location (`spec:`, or a place of its own instead of `{spec}/{context}/glossary.md`)
- format extensions (e.g. mandatory `Examples:` section)
- forbidden suffixes beyond the defaults

## Not in scope

- Writing definitions: suggest, the human ratifies.
- Translating: keep the language's own words (`Bestellung`, `Auftrag`); where code is in another language, the
  code word stands beside the domain word, decided by the domain's owners.
- Entry length: one sentence or a paragraph.
