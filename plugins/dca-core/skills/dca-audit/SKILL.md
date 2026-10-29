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

Audits code for **DCA compliance** — a diff, a bounded context or the whole project — focusing on
issues that ArchUnit rules can't detect because they are semantic, not structural, and on the rules
the project could enforce next. It is the method's audit, run by a person: the entry point for a
brownfield project after `dca-init` installed the rules ("where does this code stand against the
method, and which rules can we switch on?"), and the reader of a change before it is committed.

It assumes `dca-init` may or may not have run. If it ran, the review reads the project's `DcaLayout`
from the architecture test and the naming conventions from `dca.profile.yaml` at the project root
(the `AGENTS.md` line ``- configuration: `dca.profile.yaml` ``, which `dca-init` writes, points at it);
where it is missing or a key is absent, the defaults. Java and C# are reviewed against the same checklist —
`reference/naming-conventions.md` carries the language mapping.

This file is the router: the scope, the five phases in order, the shape of the answer and the hard rules; for
every phase the reference to read before it. The detail is in `reference/`.

## The method's view beside the general ones

This is the one DCA reviewer: it checks conformance with the method — use-case shape, port hierarchy,
marker contracts, the failure-translation site, context isolation, naming — where the rules cannot.
Its checklist is its own. The general perspectives `review-ddd`, `review-hexagonal` and
`review-clean-code` (in `dca-craft`) give the outside view — Evans/Vernon, Cockburn, Martin/Fowler —
without knowing the markers or the rules. The overlap is intended: where the two views disagree about
the same code, that is a finding to report, not a drift to reconcile.

**Where it runs, and where not.** A person runs it: on a brownfield project, on a context, on a branch.
A delivery pipeline's judge runs the three general perspectives and the project's rule suite on every
story; this audit is not one of its defaults — the rules it would confirm already run as ArchUnit in
every gate, and its anti-patterns that neither the suite nor the general reviews catch are few. It is
not a judge perspective at all: a person runs it to examine a project by hand.

Where ArchUnit ends and this audit begins — the table of what each checks — opens
`reference/audit-phases.md`. The rule suite has grown into semantic territory (`DCA-USE-015/016/017`,
`DCA-HEX-012`, `DCA-TAC-021`, `DCA-MAP-008`). Where the checklist cites a rule id, the review confirms what
that rule cannot see — it does not repeat the rule.

## Workflow

Read `reference/audit-phases.md` before the first phase: it carries each phase below in full, and before them
*Reading the project's DCA setup* — the `DcaLayout` builder chain as the convention list, the rule sets
switched off in `dca-archunit.properties`, the designed map and the glossaries, and `dca-knowledge` for the
doctrine behind a finding. This makes the review match the project's actual conventions, not DCA defaults.

1. **Phase 1: Scope** — the argument (`/dca-audit <scope>`): nothing, or `project` — every source file under
   the base package or namespace, the brownfield audit, the default, reported per bounded context in the
   order the designed map lists them; a context name or a path — that context's files; `diff` — what changed
   on this branch (the git commands are in the reference), user-specified paths instead where given. Without
   a repository or a diff, `diff` falls back to the whole project and says so.
2. **Phase 2: Layer classification** — each file's DCA layer from its path, by the classification table in
   the reference (`domain.model` … `published.events`, `infrastructure`), through the project's `DcaLayout`
   segments, C# in PascalCase matched case-insensitively; files outside the patterns are "uncategorized".
3. **Phase 3: Apply review checks per layer** — `reference/checklist.md` for the per-layer checklist, run
   only the checks that apply to each file's layer; `reference/use-case-pattern.md` for application-layer
   files; `reference/anti-patterns.md` for the findings catalogue, each with symptoms and the reason. For each
   finding capture file + line, severity (`must-fix` violates a DCA invariant, `should-fix` an anti-pattern,
   `nit` style), rule, why, suggested fix.
4. **Phase 4: The structure, rule by rule** — Block A: where the code stands against the rule suite of
   `reference/archunit-rule-catalog.md`, whether the suite is installed or not — read against each rule's
   *Selects* and *Checks* by default, taken from the suite's last report where one is younger than the newest
   source file, never by running the build; what counts follows the suite's configuration (sets on `off`,
   `warn`, frozen rules, experimental rules only with the opt-in); a set opens to its failing rules. Then the
   two lists: the rules the project does not enforce yet and could, and the patterns the suite has no rule for.
   The detail of the reading, the run, what counts and the two lists is in the reference.
5. **Phase 5: Output** — the report below.

## Phase 5: Output — the shape of the answer

Produce a structured report. It **leads with the standing**: how far the code fits the method, so a reader
sees it before the findings — that is what an audit is for. Two blocks, kept apart, because they answer
different questions and a red cell in one must not hide a green one in the other:

- **Block A — Structure** (Phase 4): what the rule suite checks, a row per rule set, opened to the rule where
  one fails.
- **Block B — Review**: what only a reader sees, a row per section of `reference/checklist.md` that applies to
  the scope, a column per bounded context in scope (one column for a single context or a diff). A cell counts
  the **must-fix and should-fix** findings of that section: `✓` none, `✗ n` that many, `–` no files of the
  layer. **Nits do not colour a cell** — they are listed below with the findings, and a cell may read `✓ · 2 nits`.
  A check the checklist marks with a rule id is Block A's; Block B confirms only what that rule cannot see.

Findings outside the checklist — a security flaw, a runtime defect, a broken contract with a client — are
reported in their own section, **Outside the method**, with the same severities; they do not enter either
block's standing. Say so rather than stretching a checklist section to hold them.

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

Every `✗ n` has its `n` places below — Block A's in the rule rows (the violating classes, grouped), Block B's
in the findings, file and line each. A `✓` is a claim about every file of that layer in that context, so say
in one line how many files each block ran over. Run the audit again after the fixes: the two blocks are what
a team compares between two runs.

## Anti-patterns this review catches

The catalogue is `reference/anti-patterns.md`, each entry with symptoms and the reason — anemic aggregate, god
use case, leaky output port, port without an application-side caller, cookies of one exchange with different
policies, the domain-event contract, setters, injected dependency in an aggregate, a business rule as an
argument exception, a blanket catch, a failure translated in more than one place, status derived from the base
type, a domain gateway without a rationale, transaction and controller placement, technical names and framework
annotations in the domain, cross-context imports, naming, DTOs and mutable messages, repository versus store.
Document each so the user understands.

## Things this review does NOT do

- **Doesn't run code or tests.** Static review only — Block A is read against the rule catalog; where the
  suite is installed it may take the suite's last report instead (Phase 4), and it never starts the build.
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

- `reference/audit-phases.md` — where ArchUnit ends, reading the project's DCA setup, and Phases 1–4 in full
- `reference/checklist.md` — the complete per-layer checklist (includes Output Port Granularity section)
- `reference/anti-patterns.md` — the findings catalogue: symptoms and the reason behind each anti-pattern
- `reference/use-case-pattern.md` — central reference for use-case folder structure, file roles, shared-vs-local output-port decision guide, ArchUnit rules
- `reference/naming-conventions.md` — extracted from the guide's package-structure chapter
- `reference/archunit-rule-catalog.md` — every rule of both libraries, set by set, with what it selects and checks;
  generated (`scripts/render-rule-catalog.py`), the same text as `dca-init`'s — Block A reads it

## Twin implementation checkpoint

When the project has a twin — the same system in a second language or stack — a behaviour change is reviewed
together with its counterpart: the same use case, the same event contracts (`events/` schemas, wire JSON), the
same ubiquitous language. An intentional difference needs a recorded compatibility note in the project; the review
does not let the two silently fork. Without a twin this section does not apply.
