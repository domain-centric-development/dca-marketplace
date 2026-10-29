---
name: dca-init
description: |
  Adds Domain-Centric Architecture (DCA) to an existing, runnable Java or .NET project: the published
  packages — `dev.domaincentric:dca-building-blocks` + `dca-spring` and `dca-archunit` (+
  `dca-archunit-spring-modulith` with Modulith), or `DomainCentric.BuildingBlocks` +
  `DomainCentric.ArchRules.Xunit` — one thin architecture test that runs the DCA rule catalog, the
  context declarations, the method's configuration `dca.profile.yaml` and its section of `AGENTS.md`. Use when the user
  wants DCA in a codebase that already builds — e.g. "set up DCA governance", "add the DCA architecture
  rules", "init DCA in this project", "/dca-init". Inspects the project first, maps its layout onto
  `DcaLayout`, migrates or aliases existing marker-like interfaces, and never overwrites existing files.
  It does not touch the stack; on an empty directory it points to `dca-new`.
---

# dca-init

Adds Domain-Centric Architecture (DCA) to the current project: the **building blocks** the production code
implements (`AggregateRoot`, `UseCase`, `Repository`, `DomainEvent`, …) come from a published package, the
**rule catalog** from a second one, and the skill generates the one test class that runs it. Java (Gradle or
Maven, JUnit 5) and .NET (xUnit) are supported.

DCA = synthesis of DDD, Hexagonal Architecture and Clean Architecture. The rule libraries pin to the package
markers, so a project must implement *those* markers — the retrofit path for existing marker-like interfaces
is decision A.

The skill does the DCA part and nothing else. The stack, the build skeleton and the repository are the
project's (`dca-new` creates them from nothing); a browser runner, a formatter or a frozen baseline are single
capabilities (`dca-add`); the project description is `dca-describe`'s.

| | Java | .NET |
|---|---|---|
| Production dependency | `dev.domaincentric:dca-building-blocks` + `dca-spring` (Spring: `SpringDomainEventPublisher`, `SpringTransactionBoundary`, auto-configured) | `DomainCentric.BuildingBlocks` (runtime adapters stay hand-written) |
| Test dependency | `dev.domaincentric:dca-archunit` (brings ArchUnit); with Spring Modulith also `dca-archunit-spring-modulith` (`DcaSpringModulithTest`) | `DomainCentric.ArchRules.Xunit` (brings `DomainCentric.ArchRules`, ArchUnitNET) |
| Base class | `dev.domaincentric.dca.archunit.junit.DcaArchitectureTest` | `DomainCentric.ArchRules.Xunit.DcaArchitectureTest` |
| Layout | `DcaLayout.forBasePackage(..)` | `DcaLayout.ForRootNamespace(..)` |
| Context declaration | `@BoundedContext` on `package-info.java` | `[BoundedContext]` on a marker class in the context root namespace |
| Rule selection | `dca-archunit.properties` on the test class path | `dca-archunit.properties` copied next to the test assembly |
| Run | `./gradlew test-architecture` / `mvn test` | `dotnet test` (Debug) |

This file is the route; each phase's detail sits in `reference/`, named where the phase starts. Read a
reference when its phase comes, not before.

## Core principle: adapt, don't overwrite

Before writing anything, **inspect the project** and **ask the user** about deviations. The templates under
`templates/` are skeletons with placeholders, not a generator's output. **Never overwrite an existing file** —
if a target path is occupied, stop and ask.

## Workflow

### Phase 0 — Is there a project?

A directory without a build file (`build.gradle(.kts)`, `pom.xml`, `*.sln`, `*.slnx`, `*.csproj`) has nothing
to add DCA to. Stop, write nothing, and point to `dca-new project`, which creates the skeleton from a generator
and then runs this skill. The same holds for a directory that holds only a project description (`product/`,
`AGENTS.md`) — that is the starting point of `dca-new`, not of this skill.

### Phase 1 — Inspection

Read `reference/inspection.md` and determine, with `Glob`, `Read`, `Grep` and `Bash`, in this order:

1. **Language and build system** — Java or .NET branch, versions, Spring Modulith, the test framework, git.
2. **Versions — look them up, never recall them.** Every DCA package version is resolved at init time
   (Maven Central, NuGet.org); re-verify per project.
3. **Source layout** — source root, base package or root namespace, multi-module; both loaders refuse a run
   that imported nothing, and a start-up module named like a layer is INIT-EXCLUDE.
4. **Existing architecture tests** — a project that already extends `DcaArchitectureTest` has DCA: refresh,
   do not install a second test.
5. **Existing structure conventions** — layer-like folders, records vs Lombok, existing context declarations
   (reuse, never duplicate), the designed domain (`domain:` in `dca.profile.yaml`).
6. **Existing marker-like interfaces and annotations (critical)** — every hit becomes an alias, role or
   migrate decision in Phase 2; keep scanning after the first find.
7. **Installed skills** — which of the skills the `AGENTS.md` section names by role are installed; one
   that is not is left out, never named.
8. **Summarize** to the user before asking anything, in the shape the reference shows.

### Phase 2 — Decisions (ask the user)

`reference/questions.md` is the catalogue of every question this skill may ask, each with where its answer is
looked up first and when it is asked at all. After the summary, look every answer up and ask **only the open
ones — all at once, in catalogue order, word for word**, with the options and the default the catalogue gives;
through a structured question tool where the harness has one, in prose otherwise. Ask nothing the catalogue
does not list. Called by `dca-new`, take the answers it hands over; they were asked in its one pass.

What each decision means — the knowledge behind the question — is in `reference/decisions.md`; read it
before asking:

- **A. Marker policy** (INIT-MARKERS) — per existing marker-like type: `Migrate`, `Alias` (recommended for
  large code bases) or `Role` (`reference/own-vocabulary.md`).
- **B. Layout** (INIT-LAYOUT) — every deviation from the defaults is a `DcaLayout` builder call; the framework
  preset is detected, never written unless detection cannot decide; INIT-EXCLUDE, INIT-LOCAL-PORTS and an
  undeclared shared kernel → `reference/own-vocabulary.md`; folders the layout cannot express are a
  migration, not a configuration.
- **C. Rule sets** (INIT-RULES) — the `dca.rules.sets` line; `reference/module-selection-guide.md` for the
  recommendation by project profile and subdomain type; a rejected rule is `dca.rules.off` + reason, one
  the team works towards `dca.rules.warn`, an accepted baseline `dca-add freeze`.
- **D. Suffix conventions** (INIT-SUFFIX) — use case, input port, controller, REST adapter and the failure
  suffix; recorded in `dca.profile.yaml`.
- **E. Spring Modulith** (INIT-MODULITH; Java, only when detected) — the second thin test.
- **F. Context map** (INIT-CONTEXT-MAP, never asked) — `ContextMapDocumentationTest`, installed when more
  than one context is declared.
- **G. Project instructions** (INIT-CATALOG, never asked) — the `AGENTS.md` section, always written.

### Phase 3 — Generation

Only after Phase 2. Placeholders use `{{name}}`; `{{#if}}` / `{{#each}}` blocks are resolved by you
(`reference/placeholders.md` says where each value comes from). Before each write: if the target exists, ask
*overwrite / skip / abort* (default skip). The skill changes no build file outside the DCA part.

Read `reference/generation.md` for the steps; in short:

- **Java** — the production dependencies (with the in-memory transaction manager where
  `reference/in-memory-transactions.md` says so), the `test-architecture` source set and task,
  `ArchitectureTest` with the layout calls from B and D, `dca-archunit.properties` from C
  (`{{noLayeredModuleYet}}` on a project without a layered module), one `package-info.java` per context root
  and one for the shared kernel, decision A's edits, decision F's and E's tests.
- **.NET** — `DomainCentric.BuildingBlocks` in every production project, the `*.ArchitectureTests` project
  with a reference per production project, `ArchitectureTest.cs` with `Layout` and `Assemblies`, the
  properties file next to the csproj, one context marker class per context root and one for the shared
  kernel, decision A's edits, decision F's test.
- **Both** — `dca.profile.yaml` at the project root (the template's keys, every other line kept; the old
  conventions file migrated into it; glossaries beside the code named for the spec) and the block between
  `<!-- dca-core: start -->` and `<!-- dca-core: end -->` in `AGENTS.md`, with the `- configuration:` line and
  the installed skills by role — read by every tool, so keep their form.

### Phase 4 — Verification

```bash
./gradlew test-architecture          # Java, Gradle
mvn test -Dtest='ArchitectureTest'   # Java, Maven
dotnet test tests/<Solution>.ArchitectureTests   # .NET — Debug; the rules refuse Release builds
```

Report which rules passed and which failed. On a project without domain code two entries are expected and
not failures: `DCA-STR-012` on `warn` (no layered module yet) and, with decision F, a
`ContextMapDocumentationTest` that has just generated `{{contextMapPath}}` — skipped in Java, failed once with
"commit it" in .NET (green from the second run on) — both named in the report. In a retrofit, failures are
findings about the existing code, not bugs of this skill: point the user to `dca.rules.warn` or
`dca-add freeze` for a staged adoption, `/dca-audit` to triage, `/dca-new` for new code that complies from
the start.

## After init — for the user

The report is read from the disk, so it has the same sections and fields every time — Stack · Generator ·
DCA part · Formatter · Browser runner · Proof · Git · Open. Run from the project root, with the result of the
Phase 4 run:

```bash
python3 <this skill folder>/scripts/dca-report.py --mode init --proof architecture=passed
```

(`failed` where the run failed, left out where it did not run.) Show the output as it is. Called by `dca-new`,
skip it — `dca-new` shows the one report at its end. Otherwise add nothing after it but this line:

```
Next: run the architecture test for the baseline and tune dca-archunit.properties, never delete a rule silently — /dca-new for new code, /dca-audit to triage existing violations.
```

The Transactions choice (Phase 3, Java step 1) is the one decision the report cannot read back from a file
name alone: say it in one sentence before the report where the in-memory placeholder was added.

The report's Open section already names what is missing; the skills that close it — hint, never do:

- a web surface (templates, static pages, a frontend) and no browser runner → `dca-add browser`;
- a browser suite that only runs against an application started beforehand → `dca-add browser`, which
  changes its base test to start the application itself;
- no formatter in the build → `dca-add formatter`;
- no project description (the files `dca.profile.yaml` or the defaults name are missing) →
  `dca-describe`.

## For the other skills

`dca-new`, `dca-audit`, `dca-modelling` and `dca-discipline` read the project's conventions from the
generated `ArchitectureTest` (the `DcaLayout` builder calls: subpackage names, suffixes) and from
`dca.profile.yaml` at the project root; where it is missing or a key is absent, the defaults. There is no
constants class to consult. The resolved-configuration contract both this skill and `dca-new` write is
`reference/resolved-configuration.md`: this skill writes its keys for every project, `dca-new` reads and
refreshes them from the resolved preset before filling annotation/import placeholders; `none` uses explicit
constructor wiring without framework imports.

## Reference materials

- `reference/inspection.md`, `reference/decisions.md`, `reference/generation.md` — Phases 1 to 4 in full
- `reference/questions.md` — every question this skill may ask, word for word, with where its answer is looked
  up first; `dca-new` asks the entries that apply to an empty directory in its one pass
- `reference/own-vocabulary.md` — marker roles, own layer and context annotations, excluded packages, local
  ports, the wiring and metadata review
- `reference/module-selection-guide.md` — which rule sets to pick for which project and subdomain; also read by
  `dca-add rules`
- `reference/archunit-rule-catalog.md` — every rule of both libraries (generated from the rule catalogs;
  regenerate with `python3 scripts/render-rule-catalog.py` from the marketplace root)
- `reference/resolved-configuration.md` — the resolved-configuration keys of `dca.profile.yaml`, shared
  with `dca-new`
- `reference/placeholders.md` — the templates' placeholders, where each value comes from
- `reference/in-memory-transactions.md` — the transaction manager a Spring project without a data starter needs
- `scripts/dca-report.py` — the report of this skill and of `dca-new project`, read from the disk
  (`--self-test` checks it)

## Anti-patterns to avoid

- **Don't** write templates without inspecting the project. The point is adaptation.
- **Don't** silently overwrite. If unsure, ask.
- **Don't** hardcode package versions from memory. Look them up at init time.
- **Don't** create a build, a repository or a stack. On an empty directory, point to `dca-new`.
- **Don't** set up a browser runner or a formatter here; hint at `dca-add`.
- **Don't** hand-write ArchUnit rules that the catalog already contains. Select sets, tune with
  `off`/`warn`/`ignore`, record reasons.
- **Don't** add `dca-archunit-spring-modulith` without Spring Modulith on the class path — the base class does
  not load.
- **Don't** publish or generate a no-op `PlatformTransactionManager` silently. If the project needs one for its
  in-memory phase, it is a named file with a comment saying what replaces it.
- **Don't** let the .NET architecture test run against Release assemblies; `DcaArchitecture.Load` refuses them
  because ArchUnitNET drops the compiler's async state machines there.
- **Don't** skip context declarations. Without `@BoundedContext` / `[BoundedContext]` the context-scoped rules
  and the context map see no contexts and check nothing.
- **Don't** invent a third marker policy. A project either migrates to the package markers or aliases its own
  types onto them; rules pinned to unrelated interfaces see nothing.
- **Don't** name a skill in the `AGENTS.md` section that is not installed. A session or a stage told to use a
  missing skill improvises without saying so.
- **Don't freehand-scaffold example contexts, aggregates, use cases or ports.** Init ends at packages, the
  architecture test, context declarations and the `AGENTS.md` section; "also build a first context" is
  `/dca-new`'s, which owns the placement rules.
