# Phase 1 — Inspection

Part of the `dca-init` skill: what its *Phase 1 — Inspection* step points to — what to determine about the project, in order, before any question is asked, and the summary shown before asking.

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
   A start-up module below the base package named like a layer makes the base package a module root beside
   the contexts — thousands of findings about nothing: INIT-EXCLUDE.

4. **Existing architecture tests.**

   ```bash
   grep -rln --include='*.java' --include='*.kt' --include='*.groovy' --include='*.cs' \
     -E 'com\.tngtech\.archunit|ArchUnitNET|extends DcaArchitectureTest|: DcaArchitectureTest' .
   ```

   Read each hit: which rules does it enforce, which conventions do its constants reveal
   (`APPLICATION_SERVICE_SUFFIX = "ApplicationService"` is a decision), which source set does it live in. A
   project that already extends `DcaArchitectureTest` has DCA — do not install a second test; refresh the
   `AGENTS.md` section (decision G) and `dca.profile.yaml`, and hand a further rule set to `dca-add rules`.
   Hand-written rules that a catalog set duplicates: recommend leaving that set out (`dca.rules.sets`) rather
   than enforcing the same thing twice.

5. **Existing structure conventions.** Layer-like folders (`domain/`, `application/`, `adapter/`,
   `infrastructure/`, or `service/`, `controller/`, `repository/`, `usecase/`, `port/`); records vs Lombok;
   `@RestController` vs `@Controller`; existing `package-info.java` / context marker classes with
   `@BoundedContext` / `@SharedKernel` (reuse, never duplicate); the root packages of the bounded contexts if
   none are declared yet. Read the designed domain where `dca.profile.yaml` puts it (`domain:`, by default
   `product/domain.md`) — its contexts are the first proposal for the context roots.

6. **Existing marker-like interfaces and annotations (critical).**

   ```bash
   # Tactical / port markers
   grep -rln --include='*.java' --include='*.cs' -E '\b(public\s+)?interface\s+I?(AggregateRoot|Aggregate|BaseAggregateRoot|Entity|Value|ValueObject|Id|Identifier|Repository|UseCase|InputPort|OutputPort|DomainEvent|IntegrationEvent|DomainService|Factory|Specification)\b' .
   # Strategic markers
   grep -rln --include='*.java' --include='*.cs' -E '(@interface\s+|class\s+)(BoundedContext|SharedKernel|OpenHostService|Upstream|Partnership)(Attribute)?\b' .
   ```

   Read each hit and verify its role (a class named `Entity` may be a JPA `@Entity`). Look for near-empty
   interfaces under `common/`, `core/`, `shared/`, `sharedkernel/`. Keep scanning after the first find —
   projects have partial sets. The rules select every building block through a *role* (`DcaMarkers`), by
   default the library's own marker; every hit becomes an alias, role or migrate decision in Phase 2 — own
   context annotations included (`reference/own-vocabulary.md`).

7. **Installed skills.** Which of the skills the `AGENTS.md` section names by role are installed: the session
   lists them, or a project skill directory holds them (`.claude/skills/`, `.agents/skills/`,
   `.codex/skills/`, `.opencode/skills/`). The roles are build (`dca-modelling`), guard (`dca-discipline`),
   glossary (`ubiquitous-language`), map (`context-map`), browser tests (`e2e-testing`) and review
   (`review-ddd`, `review-hexagonal`, `review-clean-code`, `dca-audit`). A skill that is not installed is
   left out of the section, never named.

8. **Summarize** to the user before asking anything:
   > Found: Gradle 9, Java 25, Spring Boot 4.0, Spring Modulith present · base package `com.acme.shop`
   > · contexts `order`, `customer`, `product` (no `package-info.java`) · existing marker
   > `com.acme.shop.common.BaseAggregate` (8 subclasses), `com.acme.shop.common.Identifier` · no
   > architecture tests · Lombok, no records · skills: dca-core and dca-craft installed.
