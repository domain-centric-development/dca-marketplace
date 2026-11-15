---
name: adr
description: |
  Creates and manages Architecture Decision Records (ADRs) in Michael Nygard
  format. Use when making a non-trivial architectural decision (choice of
  framework, pattern, integration style, deprecation), superseding an old
  decision, or auditing past decisions. Maintains numbered, immutable records
  with cross-references and a regenerated index.
disable-model-invocation: false
---

# /adr — Architecture Decision Records

- Nygard format, extended with `Date`, `Deciders`, `Tags`, `References`.
- **Accepted = immutable.** Change only by a new ADR that supersedes; the history is the point.

## Storage

- Default `docs/adr/` at repo root; another path from the configuration file `AGENTS.md` names
  (``- configuration: `<file>` ``).
- Files: `NNNN-kebab-case-title.md`, 4-digit zero-padded — `0007-use-spring-modulith-instead-of-microservices.md`.
- Index: `docs/adr/README.md`, regenerated.

## ADR template

```markdown
# NNNN. Kurztitel

- **Status:** Proposed | Accepted | Deprecated | Superseded by NNNN (`NNNN-...md`)
- **Date:** YYYY-MM-DD
- **Deciders:** Names or roles
- **Tags:** bounded-context, framework, integration, persistence, security, ...

## Context

Welches Problem? Welche Kräfte wirken? Constraints, Trade-offs, Annahmen.
Hier *keine* Lösung — nur die Situation.

## Decision

Was wurde entschieden? Aktiv und kurz formulieren: „Wir verwenden X."

## Consequences

Positive, negative, neutrale Folgen. Welche Optionen schließt diese
Entscheidung aus? Welche neuen Möglichkeiten entstehen? Welche Risiken
nehmen wir in Kauf?

## Alternatives Considered

Optional. Kurz die ernsthaft erwogenen Alternativen und warum verworfen.

## References

- Code: `path/file.java:42`
- Commit: `abc1234`
- Ticket: JIRA-123
- Related ADRs: 0005 (`0005-...md`)
```

## Operations

### `/adr new "Titel"`

1. No ADRs yet → offer the meta-ADR first (`reference/first-adr.md`).
2. Next number: highest existing NNNN + 1; kebab-case filename from the title.
3. Search existing ADRs for related tags/keywords, surface them ("ADR-0003 also tagged 'persistence', wert zu
   verlinken?"). An active ADR on the same topic → warn; usually `supersede` is right.
4. Write the template with `Status: Proposed`, `Date: <heute>`.
5. Leave `Context`, `Decision`, `Consequences` empty with a comment cue — no placeholder prose; the user authors
   them.
6. Update the index.

### `/adr accept NNNN`

1. Status must be `Proposed`.
2. `Context`, `Decision`, `Consequences` all non-empty, else refuse and list what is missing.
3. Warn: "Once accepted, edit only by writing a new ADR. Are you sure?"
4. Set Status → `Accepted`, nothing else. From now on only `supersede` / `deprecate` change it.

### `/adr supersede NNNN "Titel des Nachfolgers"`

1. Old ADR must be `Accepted` (not `Proposed`, not `Deprecated`).
2. New ADR via `new`, with `References` linking back to NNNN and a `Supersedes NNNN (`NNNN-...md`)` note in
   `Context`.
3. Old ADR: Status `Accepted` → `Superseded by NNNN+k (`NNNN+k-...md`)` — the only change permitted on an
   accepted ADR.
4. Update the index.

### `/adr deprecate NNNN`

No longer applies, no successor (e.g. feature removed): `Accepted` → `Deprecated`. No new ADR.

### `/adr list [--status=...] [--tag=...]`

Regenerates `docs/adr/README.md`, sorted by number:

```markdown
# Architecture Decision Records

| # | Title | Status | Date | Tags |
|---|---|---|---|---|
| 0001 (`0001-record-architecture-decisions.md`) | Record architecture decisions | Accepted | 2026-05-17 | meta |
| 0002 (`0002-use-spring-modulith.md`) | Use Spring Modulith | Accepted | 2026-05-20 | framework, modules |
| 0003 (`0003-jpa-for-persistence.md`) | JPA for persistence | Superseded by 0007 (`0007-...md`) | 2026-06-01 | persistence |
| ... | ... | ... | ... | ... |
```

Filters: `--status=Accepted` (active), `--status=Superseded` (historical, with `Superseded by` links),
`--tag=persistence`.

### `/adr link NNNN <path:line>`

Add the code reference to `References`. On user confirmation, also insert `// ADR-NNNN: <title>` at that line.

## Anti-patterns flagged

- Editing an Accepted ADR beyond `supersede` / `deprecate` → refuse: "ADRs are immutable history. Write a new ADR
  that supersedes this one."
- No clear "we will do X" in `Decision` → not an ADR yet.
- Implementation detail ("Rename `OrderHandler` to `OrderUseCase`") → a code change, not an ADR.
- Duplicate topic → warn, suggest `supersede`.
- No trade-offs in `Consequences`.

## When other skills suggest an ADR

- Bending one of the project's architecture rules (e.g. a framework annotation in the domain for legacy
  compatibility) → suggest `/adr new` to make the exception explicit.
- `/context-map`: new context, pattern shift (Conformist → ACL), removed integration.
- `/ubiquitous-language`: renaming an aggregate or a whole concept.
- `/clean-code` style choices (constructor vs field injection) are too small for an ADR.

## Project conventions

The configuration file `AGENTS.md` names may set: ADR path (`docs/decisions/`, …); required tags from a fixed
vocabulary; approval workflow (e.g. a `Reviewer:` line in Status); language (German or English — the skill is
language-agnostic).

## Not in scope

- Authoring the decision — the user writes Context / Decision / Consequences.
- Enforcing a review/approval process.
- Deciding that a change deserves an ADR — other skills suggest; the user decides.
