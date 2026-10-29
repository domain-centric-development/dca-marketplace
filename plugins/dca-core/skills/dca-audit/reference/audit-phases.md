# The audit, phase by phase

Part of the `dca-audit` skill: what its *Workflow* steps point to — where ArchUnit ends, reading the project's DCA
setup, and the detail of Phase 1 (scope) to Phase 4 (the structure, rule by rule); the output shape of Phase 5 is
the contract of the answer and stays in `SKILL.md`.

## Where ArchUnit ends and dca-audit begins

| Checked by ArchUnit | Checked by dca-audit |
|---|---|
| Class names match suffix patterns | Whether the names actually describe what the class does |
| Domain doesn't depend on adapters | Whether use cases hold too many output ports (god-use-case) |
| Aggregates implement marker | Whether aggregates have real invariants vs. anemic |
| Domain events implement marker | Whether events are emitted at the right state-transition points |
| Cross-context refs forbidden | Whether the cross-context API is well-designed |
| Records/finals on value objects | Whether value objects model the domain or just hold getters |
| Failures extend the base type of their layer | Whether a refusal should have been a named failure at all, and whether an adapter catches too widely — a `throw` and a `catch` are not in the import model |

The rule suite has grown into semantic territory (`DCA-USE-015/016/017`, `DCA-HEX-012`, `DCA-TAC-021`, `DCA-MAP-008`).
Where the checklist cites a rule id, the review confirms what that rule cannot see — it does not repeat the rule.

## Reading the project's DCA setup (if `dca-init` ran)

Find the architecture test (`grep -rn "DcaLayout\." --include='*.java' --include='*.cs'`) and read its
`DcaLayout` builder chain — every `with…`/`With…` call is a deviation from the DCA default:
- The use-case-impl suffix (`withUseCaseSuffix` — default `UseCase`, but may be `ApplicationService`)
- The adapter sub-folder names (`withIncomingSubpackage`/`withOutgoingSubpackage` — `incoming`/`outgoing` or `in`/`out`)
- The REST adapter suffix (`withRestControllerSuffix` — `Resource` or `Controller`)
- `dca-archunit.properties`: rule sets switched off there mark patterns the project deliberately does not use
  (a context without `tactical` is not an anemic-model finding)
The markers are the library's (`dev.domaincentric.dca.buildingblocks.…` / `DomainCentric.BuildingBlocks.…`).

This makes the review match the project's actual conventions, not DCA defaults.

**The designed map and the glossary.** The designed context map is where `dca.profile.yaml` puts it
(`domain:`, by default `product/domain.md`), `docs/context-map.md` where neither exists; the glossaries are
in the spec, one per context at `<spec>/<context>/glossary.md` (`spec:` in `dca.profile.yaml`,
`product/spec/<context>/glossary.md` by default) — where the `ubiquitous-language` skill puts them. A glossary
still beside the domain code is named as a finding: a migration moves it (`factory.sh update` in a project
with a delivery pipeline, `git mv` otherwise). Read the map's subdomain column to calibrate strictness, and check the strategic declarations against it — see *Declared
relationships against the designed map* in `reference/checklist.md`.

**Doctrine behind a finding.** When a finding needs the reason, consult `dca-knowledge` (the vendored
catalog: `guide/elements.md`, `guide/rules.md`, the `pitfall/` and `decision/` nodes) and cite the node;
never invent a DCA convention from memory.

## Phase 1: Scope

Determine which files to audit. The scope is the argument (`/dca-audit <scope>`):

- nothing, or `project` — every source file under the base package or namespace: the brownfield audit,
  the default. Report per bounded context, contexts in the order the designed map lists them.
- a context name (`billing`) or a path (`src/main/java/com/example/billing`) — that context's files.
- `diff` — what changed on this branch, the reader of a change before it is committed:

**`diff` — git:**
```bash
git diff --name-only main...HEAD                  # commits on this branch
git diff --name-only HEAD                         # uncommitted (modified + staged)
git diff --name-only --diff-filter=A main...HEAD  # added in this branch
```
Combine to get all changed `*.java` / `*.cs` files. If no git repo or no diff, fall back to:

**User-specified paths.** If the user passed explicit paths (files or directories), review those instead.

Without a repository or a diff, `diff` falls back to the whole project and says so.

## Phase 2: Layer classification

For each file, determine its DCA layer from path:

```
**/domain/model/**         → domain.model
**/domain/event/**         → domain.event          (domain events, internal to the context)
**/domain/service/**       → domain.service
**/domain/gateway/**       → domain.gateway        (DomainGateway interfaces owned by the domain)
**/domain/readmodel/**     → domain.readmodel      (Value snapshots and read models)
**/domain/specification/** → domain.specification
**/application/{usecasename}/**  → application.usecase
**/application/{feature}/{usecasename}/**  → application.usecase (feature-grouped context)
**/application/shared/**   → application.outputports
**/adapter/{in,incoming}/**  → adapter.incoming
**/adapter/{out,outgoing}/** → adapter.outgoing
**/{context}/api/**        → published.api         (synchronous published contract, Open Host Service)
**/{context}/events/**     → published.events      (integration events, asynchronous published contract)
**/infrastructure/**       → infrastructure        (per-context or global wiring)
```

The `api`/`events` segment names follow the project's `DcaLayout` (`withApiSubpackage`/`withEventsSubpackage`).
C# uses the same segments in PascalCase (`Domain/Model`, `Application/{UseCase}`, `Application/Shared`,
`Adapter/Incoming`, `Adapter/Outgoing`, `Api`, `Events`); match case-insensitively.

Files outside these patterns: report as "uncategorized" — could be the shared kernel or a layout deviation.

## Phase 3: Apply review checks per layer

See `reference/checklist.md` for the full per-layer checklist. Run only the checks that
apply to each file's layer. For application-layer files (use cases, output ports), consult
`reference/use-case-pattern.md` for the canonical folder structure, shape, and
shared-vs-local port decision guide. The findings catalogue — the anti-patterns with their symptoms and the
reason each is one — is `reference/anti-patterns.md`.

For each finding, capture:
- **File + line** (use file_path:line)
- **Severity:** `must-fix` (violates DCA invariant), `should-fix` (anti-pattern), `nit` (style)
- **Rule** (short name from checklist)
- **Why** (one sentence — quote the principle)
- **Suggested fix** (one-line code suggestion when feasible)

## Phase 4: The structure, rule by rule

Block A of the report: where the code stands against the rule suite, **whether the suite is installed or
not**. On a brownfield project it is not — that is the point of the block: it shows what already holds and
what would fail on the first run, before anyone adds a dependency. The rules are those of
`reference/archunit-rule-catalog.md` (Java and .NET, generated from both rule libraries), grouped by its rule
sets; the set names are the rows, the bounded contexts the columns.

**The reading — the default.** For every rule, its *Selects* and *Checks* columns say which classes it looks at
and what it asserts; judge the code in scope against exactly that, with the layout the project actually has
(Phase 2) — a project whose packages do not match the default layout is read through the `DcaLayout` options
the rule catalog names, and the deviations are said once in the summary. A rule that selects nothing in a
context is `–` there. Informational rules have no mark. The marks are the audit's reading, not a run: the
summary line says so, and the first run of the suite confirms or corrects them.

**The run — where the suite is installed.** A project with the architecture test (`dca-init` ran) may have its
last result: the JUnit report (Java: `build/test-results/<task>/TEST-*.xml` of the task that runs the
`DcaArchitectureTest`; .NET: the `.trx` of the architecture test project). Where it is younger than the newest
source file, its outcomes replace the reading: one test case per rule id (`[DCA-TAC-002] …`), a failure's
message lists the violating classes, which name their context, a skipped case is a rule on `off` or
informational. A stale report is not used. The audit reads a report — it never runs the build.

**What counts.** With the suite installed, its configuration decides: `dca-archunit.properties` (or the .NET
configuration) and the architecture test's `additionalSelection()` — a set or rule on `off` is `off` in its
cell, one on `warn` keeps its mark with `(warn)`, a frozen rule counts only what is not in its baseline.
Without the suite every released rule counts — Block A then answers "what if we switched all of it on today".
An experimental rule (*(experimental)* in the rule catalog, `maturity: experimental` on its node) counts only
where the project opted in — `withExperimental()` / `WithExperimental()` in the architecture test, or
`dca.rules.experimental = true` in `dca-archunit.properties`. Check that before citing one; without the
opt-in it gets no mark and no finding, at most a line under the summary as information.

**Fine where it fails.** A set every rule of which holds in a context is one row with `✓`. A set with a
failing rule in any context opens: its row shows the count, and below it one row per failing rule — id,
short name, places per context — while the rules that hold stay summarised in the set row (`12 of 14 hold`).
A failing rule is never hidden in a set total, and a holding one never gets a row of its own.

Then two lists:

1. **Rules of the suite the project does not enforce yet** and could: the sets and rules on `warn`, `off` or
   absent, each with the places that would fail today — from Block A, and from the findings of Block B a
   rule would have caught statically. That is the adoption path: switch on what fails nowhere, freeze what
   fails somewhere, and fix the frozen list story by story. The catalog's adoption tiers (`dca-knowledge`:
   `guide/archunit-governance/`) say the order.
2. **Patterns the suite has no rule for** that *could* be enforced statically: propose one only for a
   structural property with named positive and negative fixtures and a clear selection scope. Past-tense
   event names are a language review prompt: `Sent` is valid without an `ed` suffix — do not propose a
   suffix rule to infer tense.

## Phase 5: Output

The report shape — the summary lines, Block A, Block B, the findings, *Outside the method*, the rules to switch on
next and the strengths — is the contract of the answer and stands in `SKILL.md` § Phase 5. Two notes that belong
to the review pass behind it:

### Wiring and metadata

Check how operations are registered: a stereotype or configuration is equally valid.
Static references cannot prove runtime wiring; NAM-002 is informational only.
Presets also configure member roles (`injectionSite`, `persistenceMapping` in Java;
attribute namespace roles in .NET). Review prohibited roles on types and members,
including composed annotations/derived attributes; unknown metadata is unclassified
and allowed by these checks. Outgoing adapters can reuse own/global infrastructure,
while another module’s infrastructure remains private.
