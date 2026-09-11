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

ADRs capture *why* a non-trivial architectural choice was made — the context,
the decision, the consequences. They're short, dated, numbered, and **once
accepted, immutable**. Changes happen by writing a new ADR that supersedes
the old one. That history is the reader's most valuable asset: every
decision shows when it was made, what was known at the time, and why a later
ADR changed it.

Format: Michael Nygard's, lightly extended with `Date`, `Deciders`, `Tags`,
and `References`.

## Storage

Default: `docs/adr/` at repo root.

Files: `NNNN-kebab-case-title.md` (zero-padded to 4 digits), e.g.
`0007-use-spring-modulith-instead-of-microservices.md`.

Index: `docs/adr/README.md` — auto-regenerated table of all ADRs.

Alternative paths can be set in `<project-root>/.claude/dca/conventions.md`.

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

1. Scan `docs/adr/` for the highest existing NNNN, take `NNNN+1`.
2. Build kebab-case filename from the title.
3. Search existing ADRs for related tags/keywords — surface them to the user
   ("ADR-0003 also tagged 'persistence', wert zu verlinken?").
4. Write the file with the template, `Status: Proposed`, `Date: <heute>`.
5. Prompt the user to fill `Context`, `Decision`, `Consequences`. Do not
   write placeholder prose; leave the sections empty (with a comment cue)
   for the user to author. Architecture decisions are *theirs* to make —
   the skill only structures.
6. Update `docs/adr/README.md` index.

### `/adr accept NNNN`

1. Read the ADR. Confirm Status is `Proposed`.
2. Validate the ADR has non-empty `Context`, `Decision`, `Consequences`.
   If any is empty: refuse, list what's missing.
3. Set Status → `Accepted`. Do not touch other fields.
4. From this point, the file is **immutable** in this skill's operations —
   only `supersede` or `deprecate` can change it further.

Warn the user: "Once accepted, edit only by writing a new ADR. Are you sure?"

### `/adr supersede NNNN "Titel des Nachfolgers"`

1. Read ADR NNNN. Confirm Status is `Accepted` (you cannot supersede
   `Proposed` or `Deprecated`).
2. Create a new ADR (NNNN+k, following `new` logic) with:
   - Title from the user
   - Pre-filled `References` linking back to NNNN
   - A `Supersedes NNNN (`NNNN-...md`)` note in `Context`
3. On the **old** NNNN: change Status from `Accepted` to
   `Superseded by NNNN+k (`NNNN+k-...md`)`. This is the *only* change
   permitted on an accepted ADR.
4. Update the index.

### `/adr deprecate NNNN`

For decisions that no longer apply but have no successor (e.g. a feature
was removed). Status: `Accepted` → `Deprecated`. No new ADR created.

### `/adr list [--status=...] [--tag=...]`

Generates / regenerates `docs/adr/README.md` with a table of all ADRs
sorted by number:

```markdown
# Architecture Decision Records

| # | Title | Status | Date | Tags |
|---|---|---|---|---|
| 0001 (`0001-record-architecture-decisions.md`) | Record architecture decisions | Accepted | 2026-05-17 | meta |
| 0002 (`0002-use-spring-modulith.md`) | Use Spring Modulith | Accepted | 2026-05-20 | framework, modules |
| 0003 (`0003-jpa-for-persistence.md`) | JPA for persistence | Superseded by 0007 (`0007-...md`) | 2026-06-01 | persistence |
| ... | ... | ... | ... | ... |
```

Filtering options:
- `--status=Accepted` — only active decisions
- `--status=Superseded` — historical, with `Superseded by` links
- `--tag=persistence` — slice by tag

### `/adr link NNNN <path:line>`

Attach a code reference to an ADR's `References` section. Optionally — on
user confirmation — insert `// ADR-NNNN: <title>` as a comment at the
referenced line.

## Anti-patterns flagged

- **Editing an Accepted ADR** (other than the status transitions
  `supersede` / `deprecate`). Refuse and explain: "ADRs are immutable
  history. Write a new ADR that supersedes this one."
- **No Decision section.** Lots of context, no clear "we will do X" — not
  yet an ADR; refine it.
- **Implementation detail, not architecture.** "Rename `OrderHandler` to
  `OrderUseCase`" is a code change, not an ADR. Architecture concerns
  cross-cutting structural choices.
- **Duplicate topic.** If a search of existing ADRs surfaces an active
  decision on the same topic, warn before creating a new one — the right
  move is usually `supersede`.
- **Missing Consequences.** Every decision has trade-offs. An ADR without
  trade-offs hides what was given up.

## Relationship to other skills

- **`/dca-discipline`** — When the user wants to bend a DCA rule (e.g.
  Spring annotation in domain for legacy compatibility), suggest
  `/adr new` to make the exception explicit and traceable.
- **`/context-map`** — Significant strategic changes (new context,
  pattern shift Conformist → ACL, removing an integration) should be
  recorded as ADRs.
- **`/ubiquitous-language`** — Large domain renames (an aggregate or whole
  concept being renamed) deserve an ADR explaining why.
- **`/clean-code`** — Style decisions ("we prefer constructor injection
  over field injection") are usually too small for ADRs. Reserve ADRs
  for choices that affect architecture, not coding style.

## First ADR: record the practice itself

The very first ADR in any repo using this skill should be a meta-ADR:

```
# 0001. Record architecture decisions

- Status: Accepted
- Date: <today>
- Tags: meta, process

## Context
Wir treffen regelmäßig architektonische Entscheidungen ohne strukturierte
Dokumentation. Das macht es schwer für neue Teammitglieder zu verstehen,
warum bestimmte Pfade gewählt wurden.

## Decision
Wir dokumentieren architektonische Entscheidungen mit Architecture Decision
Records (ADRs) im Michael-Nygard-Format unter `docs/adr/`, verwaltet via
`/adr`-Skill.

## Consequences
+ Nachvollziehbarkeit von Entscheidungen über die Zeit.
+ Onboarding-Material entsteht als Nebeneffekt.
- Disziplin erforderlich; ADRs verfallen, wenn nicht gepflegt.
- Kleine Entscheidungen können nicht alle dokumentiert werden — Schwelle
  setzen.

## References
- https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- /adr skill: ~/.claude/skills/adr/SKILL.md
```

When `/adr new` is run for the first time in a repo with no existing ADRs,
offer to generate this meta-ADR first.

## Conventions overlay

`<project-root>/.claude/dca/conventions.md` may set:

- Alternative ADR path (`docs/decisions/`, etc.)
- Required tags (e.g. enforce a `Tags:` value from a fixed vocabulary)
- Approval workflow (e.g. "Status must include a `Reviewer:` line")
- Language (German vs. English; this skill is language-agnostic)

## What this skill does NOT do

- **Doesn't author the decision.** The user writes Context / Decision /
  Consequences. The skill structures and indexes them.
- **Doesn't enforce a review/approval process.** That's an organizational
  practice on top.
- **Doesn't auto-detect "this change deserves an ADR".** Other skills
  (`dca-discipline`, `context-map`, `ubiquitous-language`) *suggest* an
  ADR at appropriate moments, but the decision to record stays with the
  user.
