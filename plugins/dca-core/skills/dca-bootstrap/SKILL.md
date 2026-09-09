---
name: dca-bootstrap
disable-model-invocation: true
description: |
  Installs Domain-Centric Architecture (DCA) into a Java or .NET project by adding the published
  packages — `dev.domaincentric:dca-building-blocks` + `dca-spring` and `dca-archunit` (+
  `dca-archunit-spring-modulith` with Modulith), or `DomainCentric.BuildingBlocks` +
  `DomainCentric.ArchRules.Xunit` — and generating one thin architecture test that runs the DCA
  rule catalog. Use when the user wants to introduce DCA conventions into a new or existing codebase —
  e.g. "set up DCA governance", "add the DCA architecture rules", "bootstrap DCA in this project".
  Inspects the project first, maps its layout onto `DcaLayout`, migrates or aliases existing
  marker-like interfaces, and never overwrites existing files.
---

# dca-bootstrap

Installs Domain-Centric Architecture (DCA) into the current project: the **building blocks** the
production code implements (`AggregateRoot`, `UseCase`, `Repository`, `DomainEvent`, …) come from a
published package, the **rule catalog** from a second one, and the skill generates the one test
class that runs it. Java (Gradle or Maven, JUnit 5) and .NET (xUnit) are supported.

DCA = synthesis of DDD, Hexagonal Architecture and Clean Architecture. The rule libraries pin to the
package markers, so a project must implement *those* markers — the retrofit path for existing
marker-like interfaces is below.

| | Java | .NET |
|---|---|---|
| Production dependency | `dev.domaincentric:dca-building-blocks` + `dca-spring` (Spring: `SpringDomainEventPublisher`, `SpringTransactionBoundary`, auto-configured) | `DomainCentric.BuildingBlocks` (runtime adapters stay hand-written, see `/dca-scaffold`) |
| Test dependency | `dev.domaincentric:dca-archunit` (brings ArchUnit); with Spring Modulith also `dca-archunit-spring-modulith` (`DcaSpringModulithTest`) | `DomainCentric.ArchRules.Xunit` (brings `DomainCentric.ArchRules`, ArchUnitNET) |
| Base class | `dev.domaincentric.dca.archunit.junit.DcaArchitectureTest` | `DomainCentric.ArchRules.Xunit.DcaArchitectureTest` |
| Layout | `DcaLayout.forBasePackage(..)` | `DcaLayout.ForRootNamespace(..)` |
| Context declaration | `@BoundedContext` on `package-info.java` | `[BoundedContext]` on a marker class in the context root namespace |
| Rule selection | `dca-archunit.properties` on the test class path | `dca-archunit.properties` copied next to the test assembly |
| Run | `./gradlew test-architecture` / `mvn test` | `dotnet test` (Debug) |

## Core principle: adapt, don't overwrite

Before writing anything, **inspect the project** and **ask the user** about deviations. The
templates under `templates/` are skeletons with placeholders, not a generator's output. **Never
overwrite an existing file** — if a target path is occupied, stop and ask.

## Workflow

### Phase 1 — Inspection

Use `Glob`, `Read`, `Grep` and `Bash` to determine:

1. **Language and build system.** `build.gradle(.kts)` / `pom.xml` → Java branch; `*.sln` /
   `*.csproj` → .NET branch. Read the Java version (`toolchain`, `sourceCompatibility`,
   `<java.version>`), Spring Boot version, whether Spring Modulith is present; or the
   `TargetFramework`, the test framework already in use (xUnit / NUnit / MSTest), and whether a
   `Directory.Build.props` exists.

2. **Versions — look them up, never recall them.** Package and framework versions go stale in
   training data. At bootstrap time resolve:
   - `{{dcaJavaVersion}}` — the latest release of `dev.domaincentric:dca-archunit` (Maven Central
     search or mvnrepository via `WebFetch`). The four Java artifacts are versioned independently:
     look up `dca-building-blocks` (`{{dcaBuildingBlocksVersion}}`), `dca-spring` (`{{dcaSpringVersion}}`)
     and `dca-archunit-spring-modulith` (`{{dcaModulithVersion}}`) the same way.
   - `{{dcaDotnetVersion}}` — the latest `DomainCentric.ArchRules.Xunit` on NuGet.org
     (`https://api.nuget.org/v3-flatcontainer/domaincentric.archrules.xunit/index.json` lists the
     versions); `DomainCentric.BuildingBlocks` is versioned independently — take the version the chosen
     `ArchRules` package depends on. Only when the user says they work against unreleased rules from a
     sibling `dca-dotnet` checkout, offer the conditional `ProjectReference` switch
     (`templates/dotnet/Directory.Build.props-local-fallback.tmpl`) — the .NET counterpart of the Java
     sample's `-PwithDcaJava`.
   - Greenfield projects: also the current stable Spring Boot / .NET line (spring.io, dotnet.microsoft.com),
     offered as the recommended default with the previous stable line as fallback. For a fresh Spring Boot
     4 build, follow `reference/greenfield-java-build.md` — Boot 4 renamed the web starter, split the
     test starters per slice and moved the slice annotations into technology packages; training data
     has the Boot 3 names.
   Re-verify per project; do not carry a version over from another session.

3. **Source layout.** Source root, base package (Java: a few `package` declarations under
   `src/main/java`) or root namespace (.NET: `RootNamespace` or the first namespace segments of the
   production projects); multi-module (`settings.gradle` `include`, Maven modules, several
   `*.csproj`). In multi-module Java builds the module hosting `src/test-architecture` must depend
   on every production module, or `DcaArchitecture.load(layout)` imports only part of the base
   package; in .NET, list every production project in the test project and every assembly in
   `Assemblies`.

4. **Existing architecture tests.**

   ```bash
   grep -rln --include='*.java' --include='*.kt' --include='*.groovy' --include='*.cs' \
     -E 'com\.tngtech\.archunit|ArchUnitNET|extends DcaArchitectureTest|: DcaArchitectureTest' .
   ```

   Read each hit: which rules does it enforce, which conventions do its constants reveal
   (`APPLICATION_SERVICE_SUFFIX = "ApplicationService"` is a decision), which source set does it
   live in. A project that already extends `DcaArchitectureTest` is bootstrapped — switch to
   tuning its `dca-archunit.properties` instead of installing a second test. Hand-written rules
   that a catalog set duplicates: recommend leaving that set out (`dca.rules.sets`) rather than
   enforcing the same thing twice.

5. **Existing structure conventions.** Layer-like folders (`domain/`, `application/`, `adapter/`,
   `infrastructure/`, or `service/`, `controller/`, `repository/`, `usecase/`, `port/`); records vs
   Lombok; `@RestController` vs `@Controller`; existing `package-info.java` / context marker classes
   with `@BoundedContext` / `@SharedKernel` (reuse, never duplicate); the root packages of the
   bounded contexts if none are declared yet.

6. **Existing marker-like interfaces and annotations (critical).**

   ```bash
   # Tactical / port markers
   grep -rln --include='*.java' --include='*.cs' -E '\b(public\s+)?interface\s+I?(AggregateRoot|Aggregate|BaseAggregateRoot|Entity|Value|ValueObject|Id|Identifier|Repository|UseCase|InputPort|OutputPort|DomainEvent|IntegrationEvent|DomainService|Factory|Specification)\b' .
   # Strategic markers
   grep -rln --include='*.java' --include='*.cs' -E '(@interface\s+|class\s+)(BoundedContext|SharedKernel|OpenHostService|Upstream|Partnership)(Attribute)?\b' .
   ```

   Read each hit and verify its role (a class named `Entity` may be a JPA `@Entity`). Look for
   near-empty interfaces under `common/`, `core/`, `shared/`, `sharedkernel/`. Keep scanning after
   the first find — projects have partial sets. The rule libraries recognise **only their own
   markers**; every hit becomes a migrate-or-alias decision in Phase 2.

7. **Summarize** to the user before asking anything:
   > Found: Gradle 9, Java 25, Spring Boot 4.0, Spring Modulith present · base package `com.acme.shop`
   > · contexts `order`, `customer`, `product` (no `package-info.java`) · existing marker
   > `com.acme.shop.common.BaseAggregate` (8 subclasses), `com.acme.shop.common.Identifier` · no
   > architecture tests · Lombok, no records.

### Phase 2 — Decisions (ask the user)

Use `AskUserQuestion`; bundle related questions.

A. **Marker policy** — per existing marker-like type:
   - `Migrate` — replace it with the package marker (`extends BaseAggregateRoot<T, ID>`,
     `implements Value`, …); mechanical, the old type is deleted.
   - `Alias` — keep the type, make it extend or implement the package marker
     (`interface Aggregate<T, ID> extends AggregateRoot<T, ID>`); existing code compiles unchanged and
     the rules see every implementor. Recommend this for large code bases; note that the rules
     still report the class by *its* markers, so an alias must carry the same generics.

B. **Layout** — every deviation from the DCA defaults becomes a `DcaLayout` builder call
   (Java / .NET):
   - `adapter/in`, `adapter/out` → `withIncomingSubpackage("in")`, `withOutgoingSubpackage("out")` /
     `WithIncomingSegment("In")`, `WithOutgoingSegment("Out")`
   - published contract package other than `api` / `events` → `withApiSubpackage`, `withEventsSubpackage`
     / `WithApiSegment`, `WithEventsSegment`
   - third-party packages the domain may use → `allowingInDomain("org.jmolecules..")` / `AllowingInDomain("NodaTime")`
   - framework (Java): write **no** preset call — `DcaLayout.forBasePackage` detects Spring, Jakarta EE, Quarkus or
     Micronaut from the test class path and the report's first line shows the choice
     (`framework annotations: quarkus (detected)`). Name a preset only when detection cannot decide (mixed class
     paths, a hand-wired application → `dca.framework=none` in `dca-archunit.properties`) or when a role differs
     from the preset (`withFrameworkAnnotations(FrameworkAnnotations.jakarta().withRestController("..."))`). A
     company platform ships its preset as a `FrameworkAnnotationsProvider` library; then `dca.framework=<name>`.
   - framework (.NET): `WithFrameworkTypes(FrameworkTypes.None())` for a hand-hosted application, otherwise the
     ASP.NET Core default, adjusted with a `with` expression where a role differs
   Folder names the layout cannot express (`service/` instead of `application/`, flat
   `controller/`–`service/`–`repository/`) are a migration, not a configuration: offer `Adopt DCA
   naming` (the user moves code later; expect violations until then) or leaving the affected sets
   out for now.

C. **Rule sets** — multi-select; the answer is the `dca.rules.sets` line:
   - **Always:** `cycles`
   - **Recommended:** `layered`, `onion`, `hexagonal`, `naming`
   - **DDD-specific:** `tactical`, `strategic`, `contextmap`, `advanced`
   - **DCA-specific:** `usecase`
   - **.NET only, always on the .NET branch:** `dotnet`
   Share `reference/module-selection-guide.md` for the recommendation by project profile and
   subdomain type. Strictness varies by subdomain: core contexts run the full catalog, supporting
   and generic contexts may run the structural baseline only — record that in a pattern-selection
   ADR. A single rule the team rejects becomes `dca.rules.off` + `dca.rule.<id>.reason`; one they
   are working towards `dca.rules.warn`. Both stay visible in the report — prefer that over a
   silent gap.

D. **Suffix conventions** — DCA's defaults are `*UseCase` for the use-case class, `*InputPort` for its
   interface, `*Controller` for MVC (server-rendered) controllers and `*Resource` for REST adapters (.NET
   default `Controller` for both). `*ApplicationService` / `*Service` → `withUseCaseSuffix(...)`; `*Page` /
   `*Handler` for MVC controllers → `withControllerSuffix(...)`; `*Controller` / `*Endpoint` for REST →
   `withRestControllerSuffix(...)`. The `naming` set then holds the project to *its* convention.

E. **Spring Modulith** (Java, only when detected) — add `dev.domaincentric:dca-archunit-spring-modulith`
   and a second thin test, `class ModulithTest extends DcaSpringModulithTest` with the same layout? It runs
   Modulith's own analyzer (not an ArchUnit rule) and excludes the architecture tests in the base
   package from Modulith's root module. Requires `spring-modulith-starter-test` on the class path.

F. **Context map** — install `ContextMapDocumentationTest`, which renders `docs/context-map.md`
   from the `@BoundedContext` / `@Upstream` / `@Partnership` declarations and fails when the committed
   file is stale? Recommend yes for more than one context.

G. **Catalog wiring (`CLAUDE.md`)** — wire the project's coding agent to the DCA knowledge catalog?
   - `Yes, vendored catalog` (default) — append the DCA section to `CLAUDE.md`; `/dca-knowledge`
     resolves the catalog vendored with this plugin.
   - `Yes, live catalog` — additionally write `.claude/dca/conventions.md` with a `catalog_path:`
     pointing at a locally regenerable `dca-knowledge-catalog/bundle` (verify it holds `index.md` and `log.md`).
   - `No`.

### Phase 3 — Generation

Only after Phase 2. Placeholders use `{{name}}`; `{{#if}}` / `{{#each}}` blocks are resolved by you.
Before each write: if the target exists, ask *overwrite / skip / abort* (default skip).

**Java**

1. `templates/gradle/build-snippet.gradle.tmpl` → add `dca-building-blocks` and (Spring) `dca-spring` to
   the production `dependencies` (Groovy or Kotlin DSL as the build uses). Maven:
   `templates/maven/pom-snippet.xml.tmpl` (all dependencies; the test then lives in `src/test/java` and
   `src/test/resources`). A build that has no Spring Boot yet gets the skeleton from
   `reference/greenfield-java-build.md` first (Boot plugin, BOM as a platform, Boot 4 starters).
   **Transactions in an in-memory start:** without a data starter there is no `PlatformTransactionManager`
   and not even Boot's `TransactionAutoConfiguration` (`spring-boot-transaction`); `@Transactional` is then
   silently inert and after-commit listeners never fire while every rule stays green. Add
   `org.springframework.boot:spring-boot-transaction`, a small `PlatformTransactionManager` bean **in the
   project** (a visible placeholder until a database arrives — `dca-spring` publishes none on purpose) and,
   with Modulith, `spring-modulith-events-api` for `@ApplicationModuleListener`. Say so in the summary.
2. `templates/gradle/test-architecture.gradle.tmpl` → `gradle/plugins/test-architecture.gradle`, plus
   `apply from: "gradle/plugins/test-architecture.gradle"` in `build.gradle`. Creates the
   `testArchitecture` source set and the `test-architecture` task, wired into `check`.
3. `templates/java/ArchitectureTest.java.tmpl` → `src/test-architecture/java/{{basePackagePath}}/ArchitectureTest.java`
   with the `DcaLayout` calls from decisions B and D (`{{layoutCalls}}` — none for a default layout).
4. `templates/java/dca-archunit.properties.tmpl` → `src/test-architecture/resources/dca-archunit.properties`
   with `dca.rules.sets` from decision C (omit the key when every set was chosen).
5. `templates/java/package-info.java.tmpl` → one per bounded-context root package
   (`@BoundedContext(name, description)`) and one for the shared kernel (`@SharedKernel`; with
   Modulith also `@ApplicationModule(type = OPEN)`, otherwise Modulith closes the kernel and the
   markers it re-exports become invisible). Skip where a `package-info.java` exists.
6. Decision A: apply the migrate/alias edits to the existing marker types.
7. Decision F: `templates/java/ContextMapDocumentationTest.java.tmpl` (`{{contextMapPath}}`, default
   `docs/context-map.md`). Decision E: no template — write the four-line subclass of
   `dev.domaincentric.dca.archunit.springmodulith.DcaSpringModulithTest` next to `ArchitectureTest`, overriding
   `layout()` the same way; the dependency comes from the `test-architecture.gradle` / `pom` snippet.
8. Decision G: `templates/claude/CLAUDE-dca-section.md.tmpl` **appended** to `CLAUDE.md`
   (`{{verifyCommand}}` = `./gradlew test-architecture` or `mvn test`); idempotent — skip when a line
   starting with `## Architecture: Domain-Centric Architecture` exists. `conventions.md.tmpl` →
   `.claude/dca/conventions.md` only for `live catalog`.

**.NET**

1. `dotnet add package DomainCentric.BuildingBlocks` in every production project (the conditional
   `ProjectReference` pair from `templates/dotnet/Directory.Build.props-local-fallback.tmpl` only on
   request, for work against an unreleased sibling `dca-dotnet` checkout).
2. `templates/dotnet/ArchitectureTests.csproj.tmpl` → `tests/{{solutionName}}.ArchitectureTests/`
   with a `ProjectReference` per production project; add it to the solution (`dotnet sln add`).
   Test SDK / xUnit versions: look them up like every other version.
3. `templates/dotnet/ArchitectureTest.cs.tmpl` — `Layout` with the calls from decisions B and D,
   `Assemblies` with one `typeof(<ContextMarkerClass>).Assembly` per production assembly.
4. `templates/dotnet/dca-archunit.properties.tmpl` next to the csproj (the csproj copies it to the
   output directory).
5. `templates/dotnet/Context.cs.tmpl` → `{{ContextClassName}}.cs` in each context's root namespace,
   `templates/dotnet/SharedKernelContext.cs.tmpl` for the shared kernel. Skip where a class with
   `[BoundedContext]` / `[SharedKernel]` exists.
6. Decision A as for Java (`: IAggregateRoot<T, TId>`, `: IValue`, …). Decision G as for Java with
   `{{verifyCommand}}` = `dotnet test tests/{{solutionName}}.ArchitectureTests`.

### Phase 4 — Verification

```bash
./gradlew test-architecture          # Java, Gradle
mvn test -Dtest='ArchitectureTest'   # Java, Maven
dotnet test tests/<Solution>.ArchitectureTests   # .NET — Debug; the rules refuse Release builds
```

Report which rules passed and which failed. In a retrofit, failures are findings about the existing
code, not bootstrap bugs: point the user to `dca.rules.warn` / `dca.rules.freeze` (Java) for a
staged adoption, `/dca-review` to triage, `/dca-scaffold` for new code that complies from the start.

## Placeholders

| Placeholder | Source | Example |
|---|---|---|
| `{{basePackage}}` / `{{basePackagePath}}` | detected | `com.acme.shop` / `com/acme/shop` |
| `{{rootNamespace}}`, `{{solutionName}}` | detected | `Acme.Shop`, `AcmeShop` |
| `{{dcaJavaVersion}}`, `{{dcaDotnetVersion}}` | looked up at bootstrap time | `0.1.0` |
| `{{junitVersion}}`, `{{testSdkVersion}}`, `{{xunitVersion}}`, `{{xunitRunnerVersion}}`, `{{targetFramework}}` | looked up / detected | `5.11.4`, `net10.0` |
| `{{springBootVersion}}`, `{{javaVersion}}` | looked up / detected (greenfield Java build only) | `4.0.2`, `25` |
| `{{layoutCalls}}` | decisions B, D | `withIncomingSubpackage("in")`, `withUseCaseSuffix("ApplicationService")` |
| `{{ruleSets}}` | decision C | `cycles,layered,hexagonal,naming` |
| `{{springModulithEnabled}}` | detected | `true` / `false` |
| `{{contextName}}`, `{{description}}`, `{{packageName}}` / `{{contextNamespace}}`, `{{contextClassName}}` | detected contexts | `Shopping Cart`, `com.acme.shop.cart`, `CartContext` |
| `{{productionProjects}}`, `{{assemblyAnchors}}` | detected (.NET) | `../../src/Acme.Shop.Cart/Acme.Shop.Cart.csproj`, `Cart.CartContext` |
| `{{contextMapPath}}` | decision F | `docs/context-map.md` |
| `{{verifyCommand}}` | build system | `./gradlew test-architecture` |
| `{{catalogPath}}` | decision G (`live catalog`) | `~/…/dca-knowledge-catalog/bundle` |

## After bootstrap — for the user

```
✓ DCA bootstrap complete
  - Packages: dev.domaincentric:dca-building-blocks + dca-spring, dca-archunit (+ dca-archunit-spring-modulith) {versions}   (or DomainCentric.*)
  - Architecture test: {path}; rule sets: {dca.rules.sets or "all"}
  - Contexts declared: {N} (@BoundedContext), shared kernel: {yes|no}
  - Markers: {migrated|aliased|none found}
  - Extras: {ContextMapDocumentationTest | ModulithTest (DcaSpringModulithTest) | —}
  - Transactions: {data starter present | in-memory: spring-boot-transaction + PlatformTransactionManager bean added, replace with a real manager when persistence arrives}
  - Catalog wiring: {CLAUDE.md section appended | + conventions.md (live) | skipped}

Next steps:
  - Run {verifyCommand} for the baseline; tune dca-archunit.properties, never delete a rule silently.
  - Build with the catalog: /dca-knowledge build <thing>.
  - /dca-scaffold adds contexts and use cases; /dca-review triages existing violations.
```

## For the other skills

`/dca-scaffold`, `/dca-review` and `/dca-discipline` read the project's conventions from the
generated `ArchitectureTest` (the `DcaLayout` builder calls: subpackage names, suffixes) and from
`.claude/dca/conventions.md` when present. There is no constants class to consult.

## Reference materials

- `reference/archunit-rule-catalog.md` — every rule of both libraries (generated from the rule
  catalogs; regenerate with `python3 scripts/render-rule-catalog.py` from the marketplace root)
- `reference/module-selection-guide.md` — which rule sets to pick for which project and subdomain
- `reference/greenfield-java-build.md` — a Spring Boot 4 Gradle build from scratch: plugin, BOM as a
  platform, the renamed and split starters, the moved slice-annotation packages

## Anti-patterns to avoid

- **Don't** write templates without inspecting the project. The point is adaptation.
- **Don't** silently overwrite. If unsure, ask.
- **Don't** hardcode package or framework versions from memory. Look them up at bootstrap time.
- **Don't** write a Boot 4 build from Boot 3 memory: `spring-boot-starter-web` is deprecated, `@WebMvcTest`
  and its siblings each have their own `spring-boot-starter-<technology>-test` starter and package
  (`org.springframework.boot.webmvc.test.autoconfigure`), and `io.spring.dependency-management` is
  optional — see `reference/greenfield-java-build.md`.
- **Don't** hand-write ArchUnit rules that the catalog already contains. Select sets, tune with
  `off`/`warn`/`ignore`, record reasons.
- **Don't** add `dca-archunit-spring-modulith` without Spring Modulith on the class path — the base
  class does not load.
- **Don't** publish or generate a no-op `PlatformTransactionManager` silently. If the project needs one
  for its in-memory phase, it is a named file with a comment saying what replaces it.
- **Don't** let the .NET architecture test run against Release assemblies; `DcaArchitecture.Load`
  refuses them because ArchUnitNET drops the compiler's async state machines there.
- **Don't** skip context declarations. Without `@BoundedContext` / `[BoundedContext]` the context-scoped
  rules and the context map see no contexts and check nothing.
- **Don't** invent a third marker policy. A project either migrates to the package markers or aliases
  its own types onto them; rules pinned to unrelated interfaces see nothing.
- **Don't freehand-scaffold example bounded contexts, aggregates, use cases or ports.** Bootstrap
  ends at packages + architecture test + context declarations. Hand "also build me a first context"
  to `/dca-scaffold`, which owns the placement rules (output ports in `application/shared/`, never
  `domain/model/`, the shared-vs-local port decision). Writing example domain code inline here is how
  structural mistakes ship even though the freshly installed suite passes.
