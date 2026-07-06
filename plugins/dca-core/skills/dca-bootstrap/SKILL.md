---
name: dca-bootstrap
disable-model-invocation: true
description: |
  Installs the Domain-Centric Architecture (DCA) marker interfaces and ArchUnit governance
  test suite into a Java/Spring project. Use when the user wants to introduce DCA conventions
  into a new or existing codebase — e.g. "add ArchUnit tests for DCA", "set up DCA governance",
  "install DCA marker interfaces", "bootstrap DCA in this project". Adapts to the project's
  existing structure: detects existing marker-like interfaces, parameterizes test constants
  to the real package layout, and never overwrites existing files.
---

# dca-bootstrap

Installs Domain-Centric Architecture (DCA) **marker interfaces** + **ArchUnit governance suite** into the current Java/Spring project. Works for both greenfield and retrofit.

DCA = synthesis of DDD, Hexagonal Architecture, and Clean Architecture. The marker interfaces (`AggregateRoot`, `UseCase`, `Repository`, `DomainEvent`, etc.) are what the ArchUnit rules pin to.

## Core principle: adapt, don't overwrite

This skill ships **templates and rules**, not a deterministic generator. Before writing anything, you (Claude) **inspect the project** and **ask the user** about deviations. Templates are extracted verbatim from the DCA reference implementation but must be adapted to the project's real package layout, naming, and stack.

**Never overwrite an existing file.** If a target path is occupied, stop and ask.

## Workflow

Follow these phases in order. Do not skip the inspection phase.

### Phase 1 — Inspection

Use `Glob`, `Read`, `Grep`, and `Bash` (for `find`) to determine:

1. **Build tool & versions:**
   - `build.gradle` / `build.gradle.kts` / `pom.xml`?
   - Java version (look for `sourceCompatibility`, `<java.version>`, `toolchain`)?
   - Spring Boot version? Spring Modulith already present?
   - Existing test plugins (Spock? JUnit5?)

2. **Source layout:**
   - Source root (usually `src/main/java`, but could be `app/src/...` in Android-style multi-module)
   - Top-level base package (read a few `package` declarations under `src/main/java`)
   - Existing modules / multi-project setup (`settings.gradle`)

2b. **Multi-module project structure:**
   - Check `settings.gradle` / `settings.gradle.kts` for `include` statements
   - Identify which modules contain production source code vs. test-only code
   - Check if modules publish `testArtifacts` (test JARs) — these affect ImportOption configuration
   - In multi-module projects, the `ClassFileImporter` must include project module JARs but exclude third-party JARs and test JARs. The standard `DO_NOT_INCLUDE_JARS`/`DO_NOT_INCLUDE_ARCHIVES` ImportOptions will break bounded context discovery because they exclude all JARs, including sibling module JARs.

3. **Existing ArchUnit setup:**

   ```bash
   # Find existing ArchUnit tests so we don't overwrite or duplicate them
   grep -rln --include='*.java' --include='*.groovy' -E '\b(import com\.tngtech\.archunit|extends BaseArchUnitTest|new ClassFileImporter)' .
   ```

   For each hit, `Read` the file. Extract:
   - What rules does it already enforce? (parse `@Test` method names + `@DisplayName`)
   - What constants does it use? (e.g. `APPLICATION_SERVICE_SUFFIX = "ApplicationService"` reveals the project's use-case-impl convention)
   - Which test source set does it live in?

   **Use this map in Phase 2:** if a DCA module would duplicate existing rules, recommend SKIP for that module. Don't install rules the user already has — they likely encode project-specific decisions you'd be silently overriding.

4. **Existing structure conventions:**
   - Does the project already have layer-like folders? Look for: `domain/`, `application/`, `adapter/`, `infrastructure/`, `service/`, `controller/`, `repository/`, `usecase/`, `port/`
   - Does it use `Records` or Lombok `@Value`?
   - Does it use `@RestController`, `@Controller`, or both?
   - Are there `package-info.java` files anywhere?
   - If `package-info.java` files exist with `@BoundedContext` or `@SharedKernel` annotations, record them — the bootstrap should NOT create new ones.
   - If no `package-info.java` files exist, identify the root packages of each bounded context (one level below `basePackage`) — these will need `package-info.java` with `@BoundedContext` annotations for the ArchUnit tests to discover contexts at runtime.

4. **Existing marker-like interfaces and annotations (critical):**

   Run these greps separately — markers can be either `interface` (tactical/port markers) OR `@interface` (strategic annotations like `@BoundedContext`):

   ```bash
   # Tactical / port markers (Java interfaces)
   grep -rln --include='*.java' -E '\b(public\s+)?interface\s+(AggregateRoot|Aggregate|BaseAggregateRoot|Entity|IEntity|Value|ValueObject|Id|Identifier|Repository|UseCase|NoResultUseCase|InputPort|OutputPort|DomainEvent|IntegrationEvent|DomainService|Factory|Specification)\b' .

   # Strategic markers (Java annotations)
   grep -rln --include='*.java' -E '\b(public\s+)?@interface\s+(BoundedContext|SharedKernel|OpenHostService|Aggregate|DomainEvent|ValueObject|Module|NamedInterface)\b' .
   ```

   For each hit, `Read` the file. Don't assume — verify the role by looking at the contents (a class named `Entity` could be a JPA `@Entity` instead of a DCA marker).

   **Also check the project's existing strategic-marker FQNs.** Annotations like `@BoundedContext` may have been placed on `package-info.java` files; if they exist, the bootstrap should reuse them rather than installing new ones.

   **Strong-signal heuristic:** find empty or near-empty interfaces / annotations under a `common/`, `core/`, `foundation/`, `shared/`, or `sharedkernel/` package — these are likely existing markers.

   **Don't stop early.** Even if some markers are found, keep scanning — projects often have a partial set (e.g. tactical markers but not strategic, or one role missing). Phase 2 needs to know which roles are filled and which aren't.

5. Summarize findings to the user **before** asking questions. Example:
   > Found:
   > - Build: Gradle 8.5, Java 21, Spring Boot 3.3.4, no Spring Modulith
   > - Base package: `com.acme.shop`
   > - Source layout: `src/main/java/com/acme/shop/{order,customer,product}/...` — looks like bounded contexts already
   > - Existing markers: `com.acme.shop.common.BaseAggregate` (8 classes extend it), `com.acme.shop.common.Identifier`
   > - No ArchUnit setup yet
   > - Lombok in use; no records

### Phase 2 — Decisions (ask the user)

Use `AskUserQuestion` for each decision that has more than one reasonable answer. Bundle related questions in one call.

**Required decisions:**

A. **Marker policy** — for each existing marker found:
   - `Adopt` (DCA tests reference the user's existing interface)
   - `Install alongside` (DCA marker added in a separate package, both coexist)
   - `Migrate` (DCA marker becomes new standard; tests warn but don't fail on the old one — optional, only if user asks)

B. **Sharedkernel location** — where do new marker interfaces go?
   - `{basePackage}.sharedkernel.marker` (DCA default) — recommend this if no existing `common`/`shared` package
   - `{basePackage}.{existingCommonPkg}` — if the project already has one

C. **Test style** — Spock+Groovy or JUnit5+Java? No default; ask explicitly. Mention trade-offs:
   - Spock+Groovy: 1:1 with the DCA reference; readable BDD-style; needs Groovy plugin
   - JUnit5+Java: zero extra setup; verbose

D. **ArchUnit modules** — multi-select from:
   - **Always installed:** `BaseArchUnitTest`, `PackageCyclesArchUnitTest`
   - **Recommended defaults:** `LayeredArchitectureArchUnitTest`, `OnionArchitectureArchUnitTest`, `HexagonalArchitectureArchUnitTest`, `NamingConventionsArchUnitTest`
   - **DDD-specific:** `DddTacticalPatternsArchUnitTest`, `DddStrategicPatternsArchUnitTest`, `DddAdvancedPatternsArchUnitTest`
   - **DCA-specific:** `UseCasePatternsArchUnitTest`
   - **Conditional:** `SpringModulithVerificationTest` — auto-include if Spring Modulith detected; otherwise ask

   See `reference/module-selection-guide.md` for guidance to share with the user.

   **Rule strictness varies by subdomain type:** core contexts get the full tactical
   rule set; supporting/generic contexts may run only the structural baseline (skip
   DDD-Tactical/Advanced). Record the choice in a pattern-selection ADR (cf. ADR-025
   in the reference implementation).

E. **Layer-folder naming** — if the project uses different folder names (e.g. `service/` instead of `application/`):
   - `Adopt DCA naming` (skill writes `application/`, asks user to migrate manually later)
   - `Match existing` (skill writes constants `APP_SUBPACKAGE = "service"` so rules apply to existing folders)

   Common deviations to detect and ask about:
   - `adapter.in` / `adapter.out` (vs DCA's `adapter.incoming` / `adapter.outgoing`)
   - `application/service` + `application/port/in,out` (vs DCA's `application/{usecasename}/`)
   - Sharedkernel under `shared/` or `common/` (vs DCA's `sharedkernel/`)

F. **Use-case class-suffix convention** — DCA's default is `*UseCase` for the implementing class and `*InputPort` for the interface. Some teams flip this:
   - `*ApplicationService` (impl) + `*UseCase` (interface) — common in Hombergs-style hexagonal
   - `*Service` (impl) + `*UseCase` (interface) — Spring-tradition
   - `*UseCase` (impl) + `*InputPort` (interface) — DCA default

   If `NamingConventionsArchUnitTest` is selected, the rule must match the project's convention. Add a `{{useCaseImplSuffix}}` placeholder (default `UseCase`) that the user can override. If the project's convention differs and the user doesn't want to migrate, suggest skipping `NamingConventionsArchUnitTest` rather than installing a rule that will fail.

G. **REST controller class-suffix convention** — DCA's default is `*Resource` (JAX-RS style). Many Spring projects use `*Controller`:
   - `*Resource` — DCA default (JAX-RS convention)
   - `*Controller` — Spring convention

   If `NamingConventionsArchUnitTest` is selected, this suffix determines which naming rule applies to REST endpoint classes. Add a `{{restControllerSuffix}}` placeholder (default `Resource`) that the user can override.

H. **Catalog wiring (CLAUDE.md)** — wire the project's coding agent to the DCA knowledge catalog?
   - `Yes, vendored catalog` (default) — append the DCA architecture section to the project's
     `CLAUDE.md`; `/dca-knowledge` resolves the catalog vendored with this plugin, works for
     every teammate/CI with no extra setup
   - `Yes, live catalog` — additionally write `.claude/dca/conventions.md` with a
     `catalog_path:` pointing at a locally regenerable `dca-knowledge-catalog/bundle` (ask
     for the path; verify it exists and contains `index.md` + `log.md`)
   - `No` — skip; the user wires it later (point them to the catalog template
     `template/project-starter-claude-md.md` via `/dca-knowledge`)

### Phase 3 — Generation

Generate files **only after** Phase 2 decisions. Substitution rules:

- `{{basePackage}}` → the detected base package (e.g. `com.acme.shop`)
- `{{sharedKernelPackage}}` → chosen sharedkernel location (e.g. `com.acme.shop.sharedkernel.marker` or `com.acme.shop.common`)
- `{{aggregateRootMarkerFqn}}`, `{{entityMarkerFqn}}`, ... → either the DCA-installed FQN or the user's existing one (from decision A)
- `{{domainSubpackage}}`, `{{appSubpackage}}`, `{{adapterSubpackage}}` → from decision E

**Generation order:**

1. **Marker interfaces** (`templates/markers/`) — copy as `.java` to `src/main/java/{{sharedKernelPackage path}}/...`. Skip any whose role was filled by an existing user marker (decision A = `Adopt`).
1a. **Universal identity VO** — if the `IdentityProvider` marker is installed (its `Identity`
   interface returns a `UserId`), also install `templates/valueobjects/UserId.java.tmpl` to
   `{{basePackage}}.{{sharedKernelRoot}}.domain.model`. Skip when decision A adopted an existing
   identity type — then substitute that type into the IdentityProvider template instead.
1b. **`package-info.java` files for bounded context discovery** — For each identified bounded context root package, generate a `package-info.java` with `@BoundedContext(name = "...", description = "...")`. For the shared kernel root package, generate one with `@SharedKernel(description = "...")`. These annotations are required for runtime discovery by `BaseArchUnitTest.discoverBoundedContextPackages()`. Place them in the correct source module (each module's `src/main/java/...`). **Skip if `package-info.java` already exists** at that location.
2. **Gradle plugin** (`templates/gradle/test-architecture.gradle.tmpl`) — write to `gradle/plugins/test-architecture.gradle`. Add `apply from: "gradle/plugins/test-architecture.gradle"` to `build.gradle`. (Maven: insert profile/dependency block into `pom.xml` instead — see `templates/maven/`.)
3. **`BaseArchUnitTest`** — generate first. This file holds the central constants block:
   ```groovy
   static final String BASE_PACKAGE = "{{basePackage}}"
   static final Class<?> AGGREGATE_ROOT_MARKER = {{aggregateRootMarkerFqn}}.class
   // ... etc.
   ```
4. **Other ArchUnit test classes** (only those selected in decision D). All reference the constants from `BaseArchUnitTest`; no class-FQN should be hardcoded inside them.
5. **Catalog wiring** (decision H, unless `No`) — from `templates/claude/`:
   - `CLAUDE-dca-section.md.tmpl` → **append** to the project's `CLAUDE.md` (create the file
     if missing). `{{verifyCommand}}` = the project's architecture-test command
     (`./gradlew test-architecture` or the Maven equivalent from step 2).
     **Idempotent:** if `CLAUDE.md` already contains a line starting with
     `## Architecture: Domain-Centric Architecture`, skip and say so — never duplicate or
     rewrite the user's existing section.
   - `conventions.md.tmpl` → `.claude/dca/conventions.md` **only** for decision H =
     `live catalog`, with `{{catalogPath}}` = the validated bundle path. Skip if the file
     exists (ask: overwrite / skip).

**Critical: `allowEmptyShould(true)` on every rule.** Since ArchUnit 1.4.0, rules fail by default when `that()` matches no classes. In a project with sparse bounded contexts or during early adoption, many rules will match zero classes. Every generated rule MUST include `.allowEmptyShould(true)` before `.check(allClasses)`. This is not optional — without it, rules produce false-positive failures that look like skill bugs, not architecture findings.

**Idempotency check before each write:**
```
if Path(target).exists():
    ask user: "{path} already exists. Overwrite / skip / abort?"
    default action: skip
```

### Phase 4 — Verification

After generation, run:
```bash
./gradlew test-architecture --info  # or: mvn test -Dtest='*ArchUnitTest'
```

Report:
- Which tests passed
- Which failed (and why — usually because existing code violates DCA rules; that's a finding, not a skill bug)
- Suggest follow-up: `dca-scaffold` for new contexts, `dca-review` to triage existing violations

## Template substitution

Templates use `{{placeholder}}` syntax. Available placeholders:

| Placeholder | Source | Example |
|---|---|---|
| `{{basePackage}}` | detected | `com.acme.shop` |
| `{{basePackagePath}}` | derived | `com/acme/shop` |
| `{{sharedKernelPackage}}` | decision B | `com.acme.shop.sharedkernel.marker` |
| `{{sharedKernelPackagePath}}` | derived | `com/acme/shop/sharedkernel/marker` |
| `{{aggregateRootMarkerFqn}}` | decision A | `com.acme.shop.sharedkernel.marker.tactical.AggregateRoot` |
| `{{entityMarkerFqn}}`, `{{valueMarkerFqn}}`, `{{idMarkerFqn}}`, `{{repositoryMarkerFqn}}`, `{{storeMarkerFqn}}`, `{{useCaseMarkerFqn}}`, `{{inputPortMarkerFqn}}`, `{{outputPortMarkerFqn}}`, `{{domainEventMarkerFqn}}`, `{{integrationEventMarkerFqn}}`, `{{domainServiceMarkerFqn}}`, `{{factoryMarkerFqn}}`, `{{specificationMarkerFqn}}` | decision A | analogous |
| `{{boundedContextAnnotationFqn}}`, `{{sharedKernelAnnotationFqn}}` | decision A | `com.acme.shop.sharedkernel.marker.strategic.BoundedContext` |
| `{{domainSubpackage}}`, `{{appSubpackage}}`, `{{adapterSubpackage}}`, `{{infrastructureSubpackage}}` | decision E | `domain` / `application` / `adapter` / `infrastructure` |
| `{{incomingSubfolder}}`, `{{outgoingSubfolder}}` | decision E | `incoming` / `outgoing` (DCA default) or `in` / `out` (Hombergs-style) |
| `{{useCaseImplSuffix}}` | decision F | `UseCase` (DCA default) or `ApplicationService` or `Service` |
| `{{restControllerSuffix}}` | decision G | `Resource` (DCA default) or `Controller` (Spring) |
| `{{sharedKernelRoot}}` | derived from decision B | `shared` or `sharedkernel` — the root package name (not FQN) used in `SHAREDKERNEL_DOMAIN_PACKAGE` |
| `{{openHostServiceAnnotationFqn}}` | decision A | `com.acme.shop.sharedkernel.marker.strategic.OpenHostService` |
| `{{archunitVersion}}` | reference (1.4.1+) | `1.4.1` |
| `{{springModulithEnabled}}` | detected | `true` / `false` |
| `{{verifyCommand}}` | detected build tool | `./gradlew test-architecture` |
| `{{catalogPath}}` | decision H (`live catalog` only) | `~/…/dca-knowledge-catalog/bundle` |

## After bootstrap — for the user

Print this final summary:

```
✓ DCA bootstrap complete
  - Marker interfaces installed: {N} (skipped {M} — existing)
  - ArchUnit modules installed: {list}
  - Gradle task: ./gradlew test-architecture
  - Test style: {spock-groovy|junit5-java}
  - Catalog wiring: {CLAUDE.md section appended | + conventions.md (live catalog) | skipped}

Next steps:
  - Run ./gradlew test-architecture to see the current baseline.
  - Build with the catalog: /dca-knowledge build <thing> (task router + recipes + rule checklists).
  - Use /dca-scaffold to add bounded contexts and use cases following DCA conventions.
  - Use /dca-review to audit existing code against DCA conventions.
```

## Test-style note: Java port is on-the-fly

When the user picks `junit5-java`:
- Use `templates/archunit/java/BaseArchUnitTest.java.tmpl` as-is (substituted).
- For each selected ArchUnit module, **read the Groovy template** from `templates/archunit/groovy/`
  and translate it to Java per `templates/archunit/java/PORTING_GUIDE.md`.
- After writing, run `./gradlew compileTestArchitectureJava` to verify the port compiles.

This avoids shipping ~3000 lines of pre-baked Java twins and keeps the canonical rules in one place.

### Multi-module ImportOption handling

In multi-module projects, the `BaseArchUnitTest` must use custom `ImportOption` implementations instead of `DO_NOT_INCLUDE_JARS`:

- **`DoNotIncludeTestCode`**: Excludes test JARs (pattern: `.*-test\\.jar!.*`) and test build output (pattern: `.*/build/classes/([^/]+/)?test.*/.*`)
- **`OnlyProjectJars`**: Excludes third-party JARs from Gradle caches (pattern: `.*/caches|wrapper/.*\\.jar!.*`) while allowing project module JARs

The Java template already has a `DoNotIncludeArchitectureTests` ImportOption — in multi-module projects, replace it with both custom ImportOptions above. The Groovy templates that create their own `ClassFileImporter` (OnionArchitecture, LayeredArchitecture) must be updated to use the shared `allClasses` instance instead.

## Reference materials

- `reference/archunit-rule-catalog.md` — every rule, what it enforces, and why
- `reference/module-selection-guide.md` — which ArchUnit modules to pick for which project type

## Anti-patterns to avoid

- **Don't** write templates verbatim without inspecting the project. The whole point is adaptation.
- **Don't** silently overwrite. If unsure, ask.
- **Don't** hardcode FQNs in generated test classes. They must reference `BaseArchUnitTest` constants.
- **Don't** install `SpringModulithVerificationTest` if Spring Modulith is not on the classpath — it will fail to compile.
- **Don't** assume the project follows DCA's idealized package layout. Many projects mix layers (`controller/`, `service/`, `repository/` flat). Either adapt the rules to that layout (option E = `Match existing`) or document the mismatch as findings.
- **Don't** use `DO_NOT_INCLUDE_JARS` or `DO_NOT_INCLUDE_ARCHIVES` in multi-module projects. These exclude sibling module JARs and break bounded context discovery. Instead, use custom `ImportOption` implementations that exclude only third-party JARs (from Gradle caches/wrapper) and test JARs (matching `*-test.jar`).
- **Don't** omit `allowEmptyShould(true)` from any rule. Without it, rules produce false-positive failures when no classes match the `that()` predicate — common during early adoption or in projects with sparse bounded contexts.
- **Don't** skip `package-info.java` generation. Without `@BoundedContext` annotations on package-info files, `discoverBoundedContextPackages()` returns an empty map and all context-scoped rules silently pass (no classes checked = no findings).
- **Don't** hardcode bounded context package names in templates. Use `discoverBoundedContextPackages()` for dynamic discovery. Hardcoded names break when applied to any project that doesn't share those exact context names.
- **Don't** use `Package.getPackage()` or `Class.forName()` for loading `package-info` classes. Use `Thread.currentThread().getContextClassLoader().loadClass()` — this works reliably in multi-module Gradle builds where the classloader hierarchy differs from single-module projects.
