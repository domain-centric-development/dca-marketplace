---
name: dca-audit
description: |
  Audits Java/Spring or .NET/C# code against Domain-Centric Architecture (DCA) conventions — a whole project,
  one bounded context, or a diff. Complements ArchUnit by checking semantic aspects that static rules can't:
  aggregate-design quality, use-case granularity, port semantics, domain-event hygiene, failure types and their
  translation, cross-context boundaries, naming consistency — and says which rules of the suite the project
  could switch on next. The brownfield entry beside `dca-init`. Use when the user asks to "review my DCA code",
  "is this DCA-compliant", "audit this project / this context for DCA", "/dca-review" (the former name), "where does this code stand against the
  method", "/dca-review" (the former name), or "/dca-audit [<scope>]". The answer leads with the standing in two
  blocks per bounded context — the rule suite set by set, opened to the failing rule, and the review checklist
  section by section — then the findings and the rules to switch on next.
  Default scope is the whole project; `diff`, a path or a context name narrows it. A person runs it; a delivery
  pipeline's judge does not load it by default.
---

# dca-audit

The method's audit, run by a person: a diff, a context or the whole project — the semantic issues ArchUnit
cannot see, and the rules the project could enforce next. Brownfield entry after `dca-init`; also the reader of
a change before commit.

- Conventions: the project's `DcaLayout` (architecture test) and `dca.profile.yaml` at the root (the `AGENTS.md`
  line ``- configuration: `dca.profile.yaml` `` points at it); absent file or key → DCA defaults.
- Java and C# against the same checklist; `reference/naming-conventions.md` maps the languages.
- Where a checklist item cites a rule id (incl. the semantic ones `DCA-USE-015/016/017`, `DCA-HEX-012`,
  `DCA-TAC-021`, `DCA-MAP-008`), confirm only what that rule cannot see — never repeat it.

## The method's view beside the general ones

- This is the one DCA reviewer: use-case shape, port hierarchy, marker contracts, failure-translation site,
  context isolation, naming. Its checklist is its own.
- `review-ddd`, `review-hexagonal`, `review-clean-code` (dca-craft) give the outside view without markers or
  rules. Overlap is intended: where the two views disagree on the same code, report it as a finding.
- A person runs it. Not a judge perspective and not a pipeline default: the judge runs the three general
  perspectives and the rule suite on every story.

## Workflow

Read `reference/audit-phases.md` before Phase 1: where ArchUnit ends, *Reading the project's DCA setup*
(`DcaLayout` chain, sets off in `dca-archunit.properties`, designed map, glossaries, `dca-knowledge` for
doctrine), then each phase in full.

1. **Phase 1: Scope** — `/dca-audit <scope>`: none or `project` (default; every source file under the base
   package/namespace, reported per bounded context in the designed map's order); a context name or path (that
   context); `diff` (this branch's changes; user-given paths instead where passed). No repository or no diff →
   whole project, and say so.
2. **Phase 2: Layer classification** — each file's layer from its path via the reference's table and the
   project's `DcaLayout` segments; C# PascalCase, case-insensitive; else "uncategorized".
3. **Phase 3: Apply review checks per layer** — `reference/checklist.md`, only the checks of the file's layer;
   `reference/use-case-pattern.md` for application files; `reference/anti-patterns.md` for the findings catalogue.
   Per finding: file + line, severity (`must-fix` DCA invariant, `should-fix` anti-pattern, `nit` style), rule,
   why, suggested fix.
4. **Phase 4: The structure, rule by rule** — Block A against `reference/archunit-rule-catalog.md`, installed or
   not: read against each rule's *Selects*/*Checks*, or from the suite's last report if younger than the newest
   source file; never run the build. The suite's configuration decides what counts (`off`, `warn`, frozen,
   experimental only with opt-in); a set opens to its failing rules. Then the two lists: rules not yet enforced
   that could be, patterns the suite has no rule for.
5. **Phase 5: Output** — the report below.

## Phase 5: Output — the shape of the answer

Lead with the standing, in two blocks kept apart (a red cell in one must not hide a green one in the other):

- **Block A — Structure** (Phase 4): a row per rule set, opened to the rule where one fails.
- **Block B — Review**: a row per applicable section of `reference/checklist.md`, a column per bounded context
  (one column for a single context or a diff). Cell = must-fix + should-fix count of that section: `✓` none,
  `✗ n`, `–` no files of the layer. Nits never colour a cell (`✓ · 2 nits`). A check marked with a rule id is
  Block A's.

Security flaws, runtime defects, broken client contracts → **Outside the method**, same severities, in neither
block's standing. Never stretch a checklist section to hold them.

```
## DCA Audit

**Scope:** the project — 3 contexts, {N} source files          (or: {N} files changed on this branch)
**Structure:** 9 of 11 rule sets hold — 2 rules would fail in 3 places (read against the catalog; the suite is not installed)
**Review:** 21 of 27 applicable checks hold · 1 must-fix · 6 should-fix · 9 nits

### A — Structure (rule suite)
| Rule set | catalog | ordering | shipping |
|---|---|---|---|
| layered · onion · hexagonal · strategic · contextmap · advanced · naming · cycles | ✓ | ✓ | ✓ |
| tactical — 20 of 21 hold | ✓ | ✗ 2 | ✓ |
| ↳ `DCA-TAC-002` aggregate holds no injected dependency | ✓ | ✗ 2 | ✓ |
| usecase — 16 of 17 hold | ✓ | ✓ | ✗ 1 |
| ↳ `DCA-USE-013` no remote port inside a transaction | ✓ | ✓ | ✗ 1 |
| errors | off | off | off |

### B — Review (`reference/checklist.md`; must-fix and should-fix only)
| Check | catalog | ordering | shipping |
|---|---|---|---|
| Domain — Model: aggregate roots | ✓ | ✗ 2 | ✓ |
| Domain — Model: value objects | ✓ · 1 nit | ✓ | ✓ |
| Domain — Failures | ✗ 1 | ✓ | – |
| Domain — Events | ✓ | ✓ | – |
| Application — Use cases: input port, implementation, command, result | ✓ | ✓ | ✗ 1 |
| Application — Output ports: basics, granularity, location, repository vs store | ✓ | ✗ 1 | ✓ |
| Adapter — Incoming: resources, failure translation, consumers | ✓ | ✓ | ✓ |
| Adapter — Outgoing: repositories, publishers | ✓ | ✓ | ✓ |
| Cross-cutting: imports, framework placement, package structure, declarations against the map | ✓ | ✗ 1 | ✓ |

### Findings ({must-fix} must-fix · {should-fix} should-fix · {nit} nits)

#### must-fix
- `path/Order.java:42` — Aggregate has setters
  Why: Aggregates must enforce invariants — public setters bypass them.
  Fix: Replace `setStatus(...)` with `markCompleted()` or `cancel(reason)`.

#### should-fix
- `path/PlaceOrderUseCase.java:15` — Use case takes 7 output ports
  Why: God-use-case smell. Consider splitting or introducing a domain service.

#### nits
- `path/CartCleared.java` — Event name is past tense ✓ but carries no `occurredOn`
  Suggested fix: add `UUID eventId, Instant occurredOn` — the two members the `DomainEvent` contract requires.

### Outside the method

(security, runtime and contract findings no checklist section holds — same format, not counted above)

### Rules to switch on next

(the suite's rules on warn or off with the places that fail today — then the rules the suite lacks and could carry)

### Strengths

- Events are emitted only when a domain fact needs publication ✓
- Output ports are interfaces in application, shared when reused and local when owned by one operation ✓
```

- Every `✗ n` has its `n` places below: Block A's in the rule rows (violating classes, grouped), Block B's in
  the findings, file and line each.
- A `✓` claims every file of that layer in that context: say in one line how many files each block ran over.
- Re-run after fixes; the two blocks are what a team compares between runs.

## Boundaries

- Static only: never runs code, tests or the build (a fresh suite report may replace the reading).
- Reports; never refactors. Business-logic bugs are out of scope.
- A consistent project convention (e.g. `*ApplicationService`) is not a finding.
- Pattern choice follows subdomain type: a supporting context whose ADR declares transaction-script/active-record
  is not an anemic-model finding — only the structural baseline applies (layer dependencies, no cycles, context
  isolation). Check `docs/architecture/adr/` for a pattern-selection ADR before flagging tactical-DDD violations.
- Explain each finding so the user understands it (reason from `reference/anti-patterns.md`).

## Twin implementation checkpoint

Where the project has a twin (same system, second language or stack), review a behaviour change with its
counterpart: same use case, same event contracts (`events/` schemas, wire JSON), same ubiquitous language. An
intentional difference needs a recorded compatibility note; never let the two fork silently. No twin → skip.

## Reference

| File | Read |
|---|---|
| `reference/audit-phases.md` | before Phase 1 — ArchUnit vs audit, reading the setup, Phases 1–4 in full |
| `reference/checklist.md` | Phase 3 — the per-layer checklist (incl. output-port granularity) |
| `reference/anti-patterns.md` | Phase 3 — the findings catalogue: symptoms and reason |
| `reference/use-case-pattern.md` | Phase 3, application files — folder structure, file roles, shared-vs-local ports |
| `reference/naming-conventions.md` | naming checks, Java/C# mapping |
| `reference/archunit-rule-catalog.md` | Phase 4 — every rule of both libraries, set by set; generated (`scripts/render-rule-catalog.py`), same text as `dca-init`'s |
