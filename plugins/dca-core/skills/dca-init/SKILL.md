---
name: dca-init
description: |
  Adds Domain-Centric Architecture (DCA) to an existing, runnable Java or .NET project: the published
  packages — `dev.domaincentric:dca-building-blocks` + `dca-spring` and `dca-archunit` (+
  `dca-archunit-spring-modulith` with Modulith), or `DomainCentric.BuildingBlocks` +
  `DomainCentric.ArchRules.Xunit` — one thin architecture test that runs the DCA rule catalog, the
  context declarations, the conventions file and the method's section of `AGENTS.md`. Use when the user
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
is below.

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

## Core principle: adapt, don't overwrite

Before writing anything, **inspect the project** and **ask the user** about deviations. The templates under
`templates/` are skeletons with placeholders, not a generator's output. **Never overwrite an existing file** —
if a target path is occupied, stop and ask.

## Workflow

### Phase 0 — Is there a project?

A directory without a build file (`build.gradle(.kts)`, `pom.xml`, `*.sln`, `*.slnx`, `*.csproj`) has nothing
to add DCA to. Stop, write nothing, and point to `dca-new project`, which creates the skeleton from a generator
and then runs this skill. The same holds for a directory that holds only a project description (`project/`,
`AGENTS.md`) — that is the starting point of `dca-new`, not of this skill.

### Phase 1 — Inspection

Use `Glob`, `Read`, `Grep` and `Bash` to determine:

1. **Language and build system.** `build.gradle(.kts)` / `pom.xml` → Java branch; `*.sln` / `*.csproj` → .NET
   branch. Read the Java version (`toolchain`, `sourceCompatibility`, `<java.version>`), Spring Boot version,
   whether Spring Modulith is present; or the `TargetFramework`, the test framework already in use (xUnit /
   NUnit / MSTest), and whether a `Directory.Build.props` exists. Note whether the directory is a Git
   repository (`git rev-parse --is-inside-work-tree`); this skill creates none, and the report says so where
   it is missing.

2. **Versions — look them up, never recall them.** Package versions go stale in training data. Resolve:
   - `{{dcaJavaVersion}}` — the latest release of `dev.domaincentric:dca-archunit` (Maven Central search or
     mvnrepository via `WebFetch`). The four Java artifacts are versioned independently: look up
     `dca-building-blocks` (`{{dcaBuildingBlocksVersion}}`), `dca-spring` (`{{dcaSpringVersion}}`) and
     `dca-archunit-spring-modulith` (`{{dcaModulithVersion}}`) the same way.
   - `{{dcaDotnetVersion}}` — the latest `DomainCentric.ArchRules.Xunit` on NuGet.org
     (`https://api.nuget.org/v3-flatcontainer/domaincentric.archrules.xunit/index.json` lists the versions);
     `DomainCentric.BuildingBlocks` is versioned independently — take the version the chosen `ArchRules`
     package depends on. Only when the user says they work against unreleased rules from a sibling
     `dca-dotnet` checkout, offer the conditional `ProjectReference` switch
     (`templates/dotnet/Directory.Build.props-local-fallback.tmpl`).
   Re-verify per project; do not carry a version over from another session.

3. **Source layout.** Source root, base package (Java: a few `package` declarations under `src/main/java`) or
   root namespace (.NET: `RootNamespace` or the first namespace segments of the production projects);
   multi-module (`settings.gradle` `include`, Maven modules, several `*.csproj`). In multi-module Java builds
   the module hosting `src/test-architecture` must depend on every production module —
   `DcaArchitecture.load(layout)` imports jars as well, so a sibling module reaches it as its jar, but only if
   it is on the test class path at all; in .NET, list every production project in the test project and every
   assembly in `Assemblies`. Both loaders refuse a run that imported nothing below the base package or root
   namespace, and `DCA-STR-011` fails when no package or namespace declares a bounded context — say so in the
   report instead of treating the green suite as an adoption result.

4. **Existing architecture tests.**

   ```bash
   grep -rln --include='*.java' --include='*.kt' --include='*.groovy' --include='*.cs' \
     -E 'com\.tngtech\.archunit|ArchUnitNET|extends DcaArchitectureTest|: DcaArchitectureTest' .
   ```

   Read each hit: which rules does it enforce, which conventions do its constants reveal
   (`APPLICATION_SERVICE_SUFFIX = "ApplicationService"` is a decision), which source set does it live in. A
   project that already extends `DcaArchitectureTest` has DCA — do not install a second test; refresh the
   `AGENTS.md` section (decision G) and the conventions file, and hand a further rule set to `dca-add rules`.
   Hand-written rules that a catalog set duplicates: recommend leaving that set out (`dca.rules.sets`) rather
   than enforcing the same thing twice.

5. **Existing structure conventions.** Layer-like folders (`domain/`, `application/`, `adapter/`,
   `infrastructure/`, or `service/`, `controller/`, `repository/`, `usecase/`, `port/`); records vs Lombok;
   `@RestController` vs `@Controller`; existing `package-info.java` / context marker classes with
   `@BoundedContext` / `@SharedKernel` (reuse, never duplicate); the root packages of the bounded contexts if
   none are declared yet. Where `AGENTS.md` carries the `dca-describe` section, read the designed domain it
   names (`project/domain.md` by default) — its contexts are the first proposal for the context roots.

6. **Existing marker-like interfaces and annotations (critical).**

   ```bash
   # Tactical / port markers
   grep -rln --include='*.java' --include='*.cs' -E '\b(public\s+)?interface\s+I?(AggregateRoot|Aggregate|BaseAggregateRoot|Entity|Value|ValueObject|Id|Identifier|Repository|UseCase|InputPort|OutputPort|DomainEvent|IntegrationEvent|DomainService|Factory|Specification)\b' .
   # Strategic markers
   grep -rln --include='*.java' --include='*.cs' -E '(@interface\s+|class\s+)(BoundedContext|SharedKernel|OpenHostService|Upstream|Partnership)(Attribute)?\b' .
   ```

   Read each hit and verify its role (a class named `Entity` may be a JPA `@Entity`). Look for near-empty
   interfaces under `common/`, `core/`, `shared/`, `sharedkernel/`. Keep scanning after the first find —
   projects have partial sets. The rule libraries recognise **only their own markers**; every hit becomes a
   migrate-or-alias decision in Phase 2.

7. **Installed skills.** Which of the skills the `AGENTS.md` section names by role are installed: the session
   lists them, or a project skill directory holds them (`.claude/skills/`, `.agents/skills/`,
   `.codex/skills/`, `.opencode/skills/`). The roles are build (`dca-modelling`), guard (`dca-discipline`),
   glossary (`ubiquitous-language`), map (`context-map`), browser tests (`e2e-testing`) and review
   (`review-ddd`, `review-hexagonal`, `review-clean-code`, `dca-review`). A skill that is not installed is
   left out of the section, never named.

8. **Summarize** to the user before asking anything:
   > Found: Gradle 9, Java 25, Spring Boot 4.0, Spring Modulith present · base package `com.acme.shop`
   > · contexts `order`, `customer`, `product` (no `package-info.java`) · existing marker
   > `com.acme.shop.common.BaseAggregate` (8 subclasses), `com.acme.shop.common.Identifier` · no
   > architecture tests · Lombok, no records · skills: dca-core and dca-craft installed.

### Phase 2 — Decisions (ask the user)

`reference/questions.md` is the catalogue of every question this skill may ask, each with where its answer is
looked up first and when it is asked at all. After the summary, look every answer up and ask **only the open
ones — all at once, in catalogue order, word for word**, with the options and the default the catalogue gives;
through a structured question tool where the harness has one, in prose otherwise. Ask nothing the catalogue
does not list. Called by `dca-new`, take the answers it hands over; they were asked in its one pass. What the
decisions below mean — the knowledge behind each question — follows; the catalogue holds the wording.

A. **Marker policy** (INIT-MARKERS) — per existing marker-like type:
   - `Migrate` — replace it with the package marker (`extends BaseAggregateRoot<T, ID>`, `implements Value`,
     …); mechanical, the old type is deleted.
   - `Alias` — keep the type, make it extend or implement the package marker
     (`interface Aggregate<T, ID> extends AggregateRoot<T, ID>`); existing code compiles unchanged and the
     rules see every implementor. Recommend this for large code bases; note that the rules still report the
     class by *its* markers, so an alias must carry the same generics.

B. **Layout** (INIT-LAYOUT where folders cannot be mapped) — every deviation from the DCA defaults becomes a `DcaLayout` builder call (Java / .NET):
   - `adapter/in`, `adapter/out` → `withIncomingSubpackage("in")`, `withOutgoingSubpackage("out")` /
     `WithIncomingSegment("In")`, `WithOutgoingSegment("Out")`
   - published contract package other than `api` / `events` → `withApiSubpackage`, `withEventsSubpackage` /
     `WithApiSegment`, `WithEventsSegment`
   - third-party packages the domain may use → `allowingInDomain("org.jmolecules..")` /
     `AllowingInDomain("NodaTime")`
   - framework (Java): write **no** preset call — `DcaLayout.forBasePackage` detects Spring, Jakarta EE,
     Quarkus or Micronaut from the test class path and the report's first line shows the choice
     (`framework annotations: quarkus (detected)`). Name a preset only when detection cannot decide (mixed
     class paths, a hand-wired application → `dca.framework=none` in `dca-archunit.properties`) or when a role
     differs from the preset (`withFrameworkAnnotations(FrameworkAnnotations.jakarta().withRestController("..."))`).
     A company platform ships its preset as a `FrameworkAnnotationsProvider` library; then
     `dca.framework=<name>`.
   - framework (.NET): `WithFrameworkTypes(FrameworkTypes.None())` for a hand-hosted application, otherwise the
     ASP.NET Core default, adjusted with a `with` expression where a role differs
   Folder names the layout cannot express (`service/` instead of `application/`, flat
   `controller/`–`service/`–`repository/`) are a migration, not a configuration: offer `Adopt DCA naming` (the
   user moves code later; expect violations until then) or leaving the affected sets out for now.

C. **Rule sets** (INIT-RULES) — multi-select; the answer is the `dca.rules.sets` line:
   - **Always:** `cycles`
   - **Recommended:** `layered`, `onion`, `hexagonal`, `naming`
   - **DDD-specific:** `tactical`, `strategic`, `contextmap`, `advanced`
   - **DCA-specific:** `usecase`, `errors`
   - **.NET only, always on the .NET branch:** `dotnet`
   Share `reference/module-selection-guide.md` for the recommendation by project profile and subdomain type.
   It is the one place for that knowledge: `dca-add rules` reads the same file when a set is added later.
   Strictness varies by subdomain: core contexts run the full catalog, supporting and generic contexts may run
   the structural baseline only — record that in a pattern-selection ADR. The subdomain types come from the
   designed map (the `- domain:` line of the `dca-describe` section, `project/domain.md` by default); where it
   has none, ask. A single rule the team rejects
   becomes `dca.rules.off` + `dca.rule.<id>.reason`; one they are working towards `dca.rules.warn`. Both stay
   visible in the report — prefer that over a silent gap. Existing violations the team accepts as a baseline
   are `dca-add freeze`, after this skill.

D. **Suffix conventions** (INIT-SUFFIX where the code uses two) — DCA's defaults are `*UseCase` for the use-case class, `*InputPort` for its
   interface, `*Controller` for MVC (server-rendered) controllers and `*Resource` for REST adapters (.NET
   default `Controller` for both). `*ApplicationService` / `*Service` → `withUseCaseSuffix(...)`; `*Page` /
   `*Handler` for MVC controllers → `withControllerSuffix(...)`; `*Controller` / `*Endpoint` for REST →
   `withRestControllerSuffix(...)`. The `naming` set then holds the project to *its* convention.

E. **Spring Modulith** (INIT-MODULITH; Java, only when detected) — add `dev.domaincentric:dca-archunit-spring-modulith` and a
   second thin test, `class ModulithTest extends DcaSpringModulithTest` with the same layout? It runs
   Modulith's own analyzer (not an ArchUnit rule) and excludes the architecture tests in the base package from
   Modulith's root module. Requires `spring-modulith-starter-test` on the class path.

F. **Context map** (INIT-CONTEXT-MAP, never asked) — `ContextMapDocumentationTest` renders
   `docs/architecture/context-map.md` from the `@BoundedContext` / `@Upstream` / `@Partnership` declarations and
   fails when the committed file is stale. Installed when more than one context is declared. Java and .NET alike. That file is the map *as built*; the
   designed map is the project description's (`dca-describe`, through `context-map`), and a difference
   between the two is a finding.

G. **Project instructions (`AGENTS.md`)** (INIT-CATALOG, never asked) — the method's section, read by every
   tool, always written. `dca-knowledge` resolves the catalog vendored with this plugin; a live catalog is
   `catalog_path:` in the conventions file, set by hand, pointing at a locally regenerable
   `dca-knowledge-catalog/bundle` (verify it holds `index.md` and `log.md`).

### Phase 3 — Generation

Only after Phase 2. Placeholders use `{{name}}`; `{{#if}}` / `{{#each}}` blocks are resolved by you. Before
each write: if the target exists, ask *overwrite / skip / abort* (default skip). The skill changes no build
file outside the DCA part: dependencies, the architecture source set or project, and nothing else.

**Java**

1. `templates/gradle/build-snippet.gradle.tmpl` → add `dca-building-blocks` and (Spring) `dca-spring` to the
   production `dependencies` (Groovy or Kotlin DSL as the build uses). Maven: `templates/maven/pom-snippet.xml.tmpl`
   (all dependencies; the test then lives in `src/test/java` and `src/test/resources`).
   **Transactions in an in-memory start:** without a data starter there is no `PlatformTransactionManager` and
   not even Boot's `TransactionAutoConfiguration` (`spring-boot-transaction`); `@Transactional` is then
   silently inert and after-commit listeners never fire while every rule stays green. Add
   `org.springframework.boot:spring-boot-transaction`, a small `PlatformTransactionManager` bean **in the
   project** (a visible placeholder until a database arrives — `dca-spring` publishes none on purpose) and,
   with Modulith, `spring-modulith-events-api` for `@ApplicationModuleListener`. Say so in the summary. The
   bean comes from `templates/java/InMemoryTransactionManagerConfiguration.java.tmpl` →
   `src/main/java/{{basePackagePath}}/infrastructure/config/InMemoryTransactionManagerConfiguration.java`. The
   package is not a style choice: `DCA-LAY-004` allows transaction-manager wiring in the global infrastructure
   package and below it (`<base>.infrastructure..`, `infrastructure/config/` included, where the conventions
   put `@Configuration` classes) and in `<base>.sharedkernel.infrastructure..` — a top-level `<base>.config`
   package or a context's own package fails the rule. The template steps aside by itself once `spring-jdbc` is
   on the class path (`@ConditionalOnMissingClass`), so adding a data starter cannot leave the placeholder in
   charge of real writes — verified: with `spring-boot-starter-jdbc` Boot's `JdbcTransactionManager` is the
   one bean, without it the placeholder. Delete the class then anyway.
2. `templates/gradle/test-architecture.gradle.tmpl` → `gradle/plugins/test-architecture.gradle`, plus
   `apply from: "gradle/plugins/test-architecture.gradle"` in `build.gradle`. Creates the `testArchitecture`
   source set and the `test-architecture` task, wired into `check`.
3. `templates/java/ArchitectureTest.java.tmpl` → `src/test-architecture/java/{{basePackagePath}}/ArchitectureTest.java`
   with the `DcaLayout` calls from decisions B and D (`{{layoutCalls}}` — none for a default layout).
4. `templates/java/dca-archunit.properties.tmpl` → `src/test-architecture/resources/dca-archunit.properties`
   with `dca.rules.sets` from decision C (omit the key when every set was chosen). Set `{{noLayeredModuleYet}}`
   when no package below the base package has a `domain`, `application` or `adapter` subpackage yet — always
   on a project `dca-new` has just created. `DCA-STR-012` would otherwise fail the first run by construction;
   on `warn` it stays in the report until `dca-new` creates the first layered module and removes the entry.
   Empty means green: a project with no domain code yet passes the whole selection, with that one entry
   named in the report.
5. `templates/java/package-info.java.tmpl` → one per bounded-context root package
   (`@BoundedContext(name, description)`) and one for the shared kernel (`@SharedKernel`; with Modulith also
   `@ApplicationModule(type = OPEN)`, otherwise Modulith closes the kernel and the markers it re-exports
   become invisible). Skip where a `package-info.java` exists.
6. Decision A: apply the migrate/alias edits to the existing marker types.
7. Decision F: `templates/java/ContextMapDocumentationTest.java.tmpl` (`{{contextMapPath}}`, default
   `docs/architecture/context-map.md`). The first run creates the file and reports the test as skipped; the
   map belongs in the user's next commit, after which the test fails whenever the map is stale. Decision E: no
   template — write the four-line subclass of
   `dev.domaincentric.dca.archunit.springmodulith.DcaSpringModulithTest` next to `ArchitectureTest`,
   overriding `layout()` the same way; the dependency comes from the `test-architecture.gradle` / `pom`
   snippet.
8. The conventions file and the `AGENTS.md` section, as below (`{{verifyCommand}}` = `./gradlew
   test-architecture` or `mvn test`).

**.NET**

1. `dotnet add package DomainCentric.BuildingBlocks` in every production project (the conditional
   `ProjectReference` pair from `templates/dotnet/Directory.Build.props-local-fallback.tmpl` only on request,
   for work against an unreleased sibling `dca-dotnet` checkout).
2. `templates/dotnet/ArchitectureTests.csproj.tmpl` → `tests/{{solutionName}}.ArchitectureTests/` with a
   `ProjectReference` per production project; add it to the solution (`dotnet sln add`). Test SDK / xUnit
   versions: look them up like every other version.
3. `templates/dotnet/ArchitectureTest.cs.tmpl` — `Layout` with the calls from decisions B and D, `Assemblies`
   with one `typeof(<ContextMarkerClass>).Assembly` per production assembly.
4. `templates/dotnet/dca-archunit.properties.tmpl` next to the csproj (the csproj copies it to the output
   directory); `{{noLayeredModuleYet}}` as in Java step 4.
5. `templates/dotnet/Context.cs.tmpl` → `{{ContextClassName}}.cs` in each context's root namespace,
   `templates/dotnet/SharedKernelContext.cs.tmpl` for the shared kernel. Skip where a class with
   `[BoundedContext]` / `[SharedKernel]` exists.
6. Decision A as for Java (`: IAggregateRoot<T, TId>`, `: IValue`, …).
7. Decision F: `templates/dotnet/ContextMapDocumentationTest.cs.tmpl` → next to `ArchitectureTest.cs`, with
   the same assemblies (`{{assemblyAnchors}}`), `{{contextMapPath}}` and the solution file that marks the
   repository root (`{{solutionName}}.slnx`, or `.sln` before .NET 10). xUnit 2 cannot skip at run time, so
   where Java reports the first run as skipped, the .NET test writes the map and fails once with "commit it";
   the report names that.
8. The conventions file and the `AGENTS.md` section, as below (`{{verifyCommand}}` = `dotnet test
   tests/{{solutionName}}.ArchitectureTests`).

**Conventions file and `AGENTS.md` section (both languages)**

- `templates/agents/conventions.md.tmpl` → `.agents/dca/conventions.md` (`{{conventionsPath}}`), with the
  resolved-configuration section; `catalog_path` only with decision G's live catalog. A project that already
  has `.claude/dca/conventions.md` keeps that file and writes to it; the section then names that path.
- `templates/agents/AGENTS-dca-section.md.tmpl` → the block between `<!-- dca-core: start -->` and
  `<!-- dca-core: end -->` in `AGENTS.md`: added where there is none, replaced where there is one, never
  duplicated. Only this block is the skill's; the rest of `AGENTS.md` — the `dca-describe` section, a delivery
  pipeline's block, the project's own text — stays as it is. Create `AGENTS.md` where the project has none.
- The section carries the line the general skills read — ``- conventions: `<path>` `` — and the skills by
  role from Phase 1 item 7, each only where it is installed; a role with nothing installed is left out.
  `{{reviewSkills}}` lists the installed ones of `review-ddd`, `review-hexagonal`, `review-clean-code` and
  `dca-review`. The `- conventions:` and `- <role>:` lines are read by other tools (general skills take the
  conventions file from them, a delivery pipeline its carrier names), so keep their form.
- Why the section exists: a person developing by hand in a session has the same information and the same
  means as a stage of a delivery pipeline — the conventions, the skill that carries each craft, the check.
  The pipeline's own configuration is its view of the same installed skills, so the two never name
  different skills.
- Where the project keeps a `CLAUDE.md` without `@AGENTS.md`, say that Claude Code does not read the section
  then, and offer to add the `@AGENTS.md` line.

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
`dca-add freeze` for a staged adoption, `/dca-review` to triage, `/dca-new` for new code that complies from
the start.

## Placeholders

| Placeholder | Source | Example |
|---|---|---|
| `{{basePackage}}` / `{{basePackagePath}}` | detected | `com.acme.shop` / `com/acme/shop` |
| `{{rootNamespace}}`, `{{solutionName}}` | detected | `Acme.Shop`, `AcmeShop` |
| `{{dcaJavaVersion}}`, `{{dcaDotnetVersion}}` | looked up at init time | `0.5.0` |
| `{{junitVersion}}`, `{{testSdkVersion}}`, `{{xunitVersion}}`, `{{xunitRunnerVersion}}`, `{{targetFramework}}` | looked up / detected | `5.11.4`, `net10.0` |
| `{{layoutCalls}}` | decisions B, D | `withIncomingSubpackage("in")`, `withUseCaseSuffix("ApplicationService")` |
| `{{ruleSets}}` | decision C | `cycles,layered,hexagonal,naming` |
| `{{noLayeredModuleYet}}` | detected: no `domain`/`application`/`adapter` package below the base package | `true` / `false` |
| `{{springModulithEnabled}}` | detected | `true` / `false` |
| `{{contextName}}`, `{{description}}`, `{{packageName}}` / `{{contextNamespace}}`, `{{contextClassName}}` | detected contexts | `Shopping Cart`, `com.acme.shop.cart`, `CartContext` |
| `{{productionProjects}}`, `{{assemblyAnchors}}` | detected (.NET) | `../../src/Acme.Shop.Cart/Acme.Shop.Cart.csproj`, `Cart.CartContext` |
| `{{contextMapPath}}` | decision F | `docs/architecture/context-map.md` |
| `{{verifyCommand}}` | build system | `./gradlew test-architecture` |
| `{{conventionsPath}}` | existing file or default | `.agents/dca/conventions.md` |
| `{{build}}`, `{{guard}}`, `{{glossary}}`, `{{map}}`, `{{browserTests}}`, `{{review}}`, `{{reviewSkills}}` | Phase 1 item 7 | `true`; `` `review-ddd`, `dca-review` `` |
| `{{catalogPath}}` | decision G (`live catalog`) | `~/…/dca-knowledge-catalog/bundle` |

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
Next: run the architecture test for the baseline and tune dca-archunit.properties, never delete a rule silently — /dca-new for new code, /dca-review to triage existing violations.
```

The Transactions choice (Phase 3, Java step 1) is the one decision the report cannot read back from a file
name alone: say it in one sentence before the report where the in-memory placeholder was added.

The report's Open section already names what is missing; the skills that close it — hint, never do:

- a web surface (templates, static pages, a frontend) and no browser runner → `dca-add browser`;
- no formatter in the build → `dca-add formatter`;
- no project description (`AGENTS.md` has no `dca-describe` section, or the files it names are missing) →
  `dca-describe`.

## For the other skills

`dca-new`, `dca-review`, `dca-modelling` and `dca-discipline` read the project's conventions from the
generated `ArchitectureTest` (the `DcaLayout` builder calls: subpackage names, suffixes) and from the
conventions file the `AGENTS.md` section names — `.agents/dca/conventions.md` by default, falling back to
`.claude/dca/conventions.md`. There is no constants class to consult.

## Reference materials

- `reference/archunit-rule-catalog.md` — every rule of both libraries (generated from the rule catalogs;
  regenerate with `python3 scripts/render-rule-catalog.py` from the marketplace root)
- `reference/module-selection-guide.md` — which rule sets to pick for which project and subdomain; also read by
  `dca-add rules`
- `reference/resolved-configuration.md` — the resolved-configuration section of the conventions file, shared
  with `dca-new`
- `reference/questions.md` — every question this skill may ask, word for word, with where its answer is looked
  up first; `dca-new` asks the entries that apply to an empty directory in its one pass
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
- **Don't freehand-scaffold example bounded contexts, aggregates, use cases or ports.** Init ends at packages +
  architecture test + context declarations + the `AGENTS.md` section. Hand "also build me a first context" to
  `/dca-new`, which owns the placement rules (output ports in `application/shared/`, never `domain/model/`,
  the shared-vs-local port decision). Writing example domain code inline here is how structural mistakes ship
  even though the freshly installed suite passes.

### Wiring and metadata review

Check how operations are registered: a stereotype or configuration is equally valid.
Static references cannot prove runtime wiring; NAM-002 is informational only.
Presets also configure member roles (`injectionSite`, `persistenceMapping` in Java;
attribute namespace roles in .NET). Review prohibited roles on types and members,
including composed annotations/derived attributes; unknown metadata is unclassified
and allowed by these checks. Outgoing adapters can reuse own/global infrastructure,
while another module’s infrastructure remains private.

## Resolved configuration

Read the shared resolved-configuration contract, `reference/resolved-configuration.md`. This skill writes the
section for every project; `dca-new` reads and refreshes it from the resolved preset before filling
annotation/import placeholders. `none` uses explicit constructor wiring and `Configuration.java.tmpl`, without
framework imports.
