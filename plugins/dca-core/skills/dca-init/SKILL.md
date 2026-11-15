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

The DCA part only. Stack, build skeleton, repository: the project's (`dca-new` creates them). Browser runner,
formatter, frozen baseline: `dca-add`. Project description: `dca-describe`. Rules pin to the package markers,
so the project must implement those (retrofit path: decision A).

| | Java (Gradle/Maven, JUnit 5) | .NET (xUnit) |
|---|---|---|
| Production | `dev.domaincentric:dca-building-blocks` + `dca-spring` (Spring: `SpringDomainEventPublisher`, `SpringTransactionBoundary`, auto-configured) | `DomainCentric.BuildingBlocks` (runtime adapters hand-written) |
| Test | `dev.domaincentric:dca-archunit` (brings ArchUnit); with Spring Modulith also `dca-archunit-spring-modulith` (`DcaSpringModulithTest`) | `DomainCentric.ArchRules.Xunit` (brings `DomainCentric.ArchRules`, ArchUnitNET) |
| Base class | `dev.domaincentric.dca.archunit.junit.DcaArchitectureTest` | `DomainCentric.ArchRules.Xunit.DcaArchitectureTest` |
| Layout | `DcaLayout.forBasePackage(..)` | `DcaLayout.ForRootNamespace(..)` |
| Context declaration | `@BoundedContext` on `package-info.java` | `[BoundedContext]` on a marker class in the context root namespace |
| Rule selection | `dca-archunit.properties` on the test class path | `dca-archunit.properties` copied next to the test assembly |
| Run | `./gradlew test-architecture` / `mvn test` | `dotnet test` (Debug) |

Read each phase's reference when the phase comes, not before.

**Adapt, don't overwrite.** Inspect, then ask about deviations. `templates/` are skeletons with placeholders.
Never overwrite an existing file: occupied target → ask.

## Workflow

### Phase 0 — Is there a project?

No build file (`build.gradle(.kts)`, `pom.xml`, `*.sln`, `*.slnx`, `*.csproj`), or only a project description
(`product/`, `AGENTS.md`) → write nothing, point to `dca-new project` (creates the skeleton, then runs this skill).

### Phase 1 — Inspection

Read `reference/inspection.md`. Determine, in order:

1. Language and build system — branch, versions, Spring Modulith, test framework, git.
2. Versions — look up every DCA package version (Maven Central, NuGet.org), never recall; re-verify per project.
3. Source layout — source root, base package / root namespace, multi-module. Both loaders refuse a run that
   imported nothing; a start-up module named like a layer is INIT-EXCLUDE.
4. Existing architecture tests — already extends `DcaArchitectureTest` → refresh, no second test.
5. Structure conventions — layer-like folders, records vs Lombok, existing context declarations (reuse, never
   duplicate), the designed domain (`domain:` in `dca.profile.yaml`).
6. Marker-like interfaces and annotations (critical) — each hit becomes an alias/role/migrate decision; keep
   scanning after the first.
7. Installed skills — those the `AGENTS.md` section names by role; one not installed is left out, never named.
8. Summarize to the user before asking, in the reference's shape.

### Phase 2 — Decisions (ask the user)

`reference/questions.md` holds every question, with where its answer is looked up first and when it is asked.
Look every answer up; ask **only the open ones — all at once, in catalogue order, word for word**, with its
options and default; structured question tool where available, else prose. Ask nothing it does not list.
Called by `dca-new`: take the answers it hands over.

Read `reference/decisions.md` (what each decision means) before asking:

- **A. Marker policy** (INIT-MARKERS) — per marker-like type: `Migrate`, `Alias` (recommended for large code
  bases) or `Role` (`reference/own-vocabulary.md`).
- **B. Layout** (INIT-LAYOUT) — each deviation a `DcaLayout` builder call; framework preset detected, written
  only when detection cannot decide; INIT-EXCLUDE, INIT-LOCAL-PORTS, undeclared shared kernel →
  `reference/own-vocabulary.md`; folders the layout cannot express are a migration, not configuration.
- **C. Rule sets** (INIT-RULES) — the `dca.rules.sets` line; recommendation by profile and subdomain type in
  `reference/module-selection-guide.md`. Rejected rule → `dca.rules.off` + reason; worked towards →
  `dca.rules.warn`; accepted baseline → `dca-add freeze`.
- **D. Suffix conventions** (INIT-SUFFIX) — use case, input port, controller, REST adapter, failure suffix;
  recorded in `dca.profile.yaml`.
- **E. Spring Modulith** (INIT-MODULITH; Java, only when detected) — the second thin test.
- **F. Context map** (INIT-CONTEXT-MAP, never asked) — `ContextMapDocumentationTest`, when more than one
  context is declared.
- **G. Project instructions** (INIT-CATALOG, never asked) — the `AGENTS.md` section, always written.

### Phase 3 — Generation

Only after Phase 2. Read `reference/generation.md` (steps per language); `reference/placeholders.md` says where
each `{{name}}` comes from; resolve `{{#if}}` / `{{#each}}` yourself. Target exists → ask *overwrite / skip /
abort* (default skip). No build-file change outside the DCA part.

- **Java** — production dependencies (+ in-memory transaction manager where `reference/in-memory-transactions.md`
  says so), `test-architecture` source set and task, `ArchitectureTest` with B/D layout calls,
  `dca-archunit.properties` from C (`{{noLayeredModuleYet}}` without a layered module), one `package-info.java`
  per context root + one for the shared kernel, A's edits, F's and E's tests.
- **.NET** — `DomainCentric.BuildingBlocks` in every production project, `*.ArchitectureTests` project
  referencing each, `ArchitectureTest.cs` with `Layout` and `Assemblies`, properties file next to the csproj,
  one context marker class per context root + one for the shared kernel, A's edits, F's test.
- **Both** — `dca.profile.yaml` at the root (template keys; keep every other line; migrate the old conventions
  file; name glossaries beside the code for the spec) and the block between `<!-- dca-core: start -->` and
  `<!-- dca-core: end -->` in `AGENTS.md`: the `- configuration:` line and installed skills by role. Other tools
  read these lines — keep their form.

### Phase 4 — Verification

```bash
./gradlew test-architecture          # Java, Gradle
mvn test -Dtest='ArchitectureTest'   # Java, Maven
dotnet test tests/<Solution>.ArchitectureTests   # .NET — Debug; the rules refuse Release builds
```

Report passed and failed rules. Without domain code, two entries are expected, not failures — name both:
`DCA-STR-012` on `warn` (no layered module yet); with F, `ContextMapDocumentationTest` having generated
`{{contextMapPath}}` (Java: skipped; .NET: fails once with "commit it", green from the second run). Retrofit
failures are findings about existing code: point to `dca.rules.warn` or `dca-add freeze` (staged adoption),
`/dca-audit` (triage), `/dca-new` (compliant new code).

## After init — for the user

The report is read from disk, same sections every time (Stack · Generator · DCA part · Formatter · Browser
runner · Proof · Git · Open). From the project root, with the Phase 4 result:

```bash
python3 <this skill folder>/scripts/dca-report.py --mode init --proof architecture=passed
```

(`failed` if it failed; omit if it did not run.) Show the output as is. Called by `dca-new`: skip it. Otherwise
add only this line after it:

```
Next: run the architecture test for the baseline and tune dca-archunit.properties, never delete a rule silently — /dca-new for new code, /dca-audit to triage existing violations.
```

Where the in-memory placeholder was added (Phase 3, Java step 1), say so in one sentence before the report — the
report cannot read it back.

Hint, never do, for what Open names:

- web surface (templates, static pages, a frontend) without browser runner → `dca-add browser`;
- browser suite needing an application started beforehand → `dca-add browser` (base test starts it);
- no formatter → `dca-add formatter`;
- no project description (files `dca.profile.yaml` or the defaults name missing) → `dca-describe`.

## For the other skills

`dca-new`, `dca-audit`, `dca-modelling`, `dca-discipline` read conventions from the generated `ArchitectureTest`
(`DcaLayout` calls: subpackages, suffixes) and `dca.profile.yaml`; missing file or key → defaults. No constants
class. Resolved-configuration contract (written here for every project, read and refreshed by `dca-new` before
filling annotation/import placeholders; `none` = explicit constructor wiring, no framework imports):
`reference/resolved-configuration.md`.

## Reference materials

- `reference/inspection.md`, `decisions.md`, `generation.md` — Phases 1–3 in full
- `reference/questions.md` — every question, word for word; `dca-new` asks those for an empty directory
- `reference/own-vocabulary.md` — marker roles, own layer/context annotations, excluded packages, local ports,
  wiring and metadata review
- `reference/module-selection-guide.md` — rule sets per project and subdomain; also read by `dca-add rules`
- `reference/archunit-rule-catalog.md` — every rule of both libraries (generated:
  `python3 scripts/render-rule-catalog.py` from the marketplace root)
- `reference/resolved-configuration.md` — resolved-configuration keys of `dca.profile.yaml`, shared with `dca-new`
- `reference/placeholders.md` — template placeholders and their sources
- `reference/in-memory-transactions.md` — transaction manager for a Spring project without a data starter
- `scripts/dca-report.py` — report of this skill and `dca-new project`, read from disk (`--self-test`)

## Don't

- write templates without inspecting; overwrite silently.
- hardcode package versions from memory.
- create a build, repository or stack, a browser runner or formatter (→ `dca-new`, `dca-add`).
- hand-write ArchUnit rules the catalog has — select sets, tune with `off`/`warn`/`ignore`, record reasons.
- add `dca-archunit-spring-modulith` without Spring Modulith on the class path — the base class does not load.
- add a no-op `PlatformTransactionManager` silently: a named file with a comment saying what replaces it.
- run the .NET architecture test against Release — `DcaArchitecture.Load` refuses (ArchUnitNET drops async state
  machines).
- skip context declarations — without `@BoundedContext` / `[BoundedContext]` context-scoped rules and the map
  check nothing.
- invent a third marker policy: migrate, or alias onto the package markers (or a role).
- name an uninstalled skill in the `AGENTS.md` section — a session told to use it improvises silently.
- scaffold example contexts, aggregates, use cases or ports — that is `/dca-new`.
