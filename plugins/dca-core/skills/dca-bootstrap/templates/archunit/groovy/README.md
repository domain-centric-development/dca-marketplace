# ArchUnit Templates — Spock + Groovy

These are the canonical DCA ArchUnit governance templates. The Java port (`../java/`)
is derived from these at install time.

## Files

| Template | Type | Required? | Enforces |
|---|---|---|---|
| `BaseArchUnitTest.groovy.tmpl` | abstract base | **Required** | Configuration block + import + discovery utilities. All other tests extend it. |
| `PackageCyclesArchUnitTest.groovy.tmpl` | rule | **Required** | No cyclic dependencies between domain/application/adapter slices |
| `HexagonalArchitectureArchUnitTest.groovy.tmpl` | rule | recommended | Domain + application can't reach adapters; incoming adapters can't reach outgoing adapters; cross-context isolation |
| `LayeredArchitectureArchUnitTest.groovy.tmpl` | rule | recommended | Domain has no infrastructure dependencies; application uses ports only; sharedkernel.port.out is interface-only |
| `OnionArchitectureArchUnitTest.groovy.tmpl` | rule | recommended | Domain has no application dependencies; domain stays framework-independent (only allowlisted 3rd-party packages) |
| `NamingConventionsArchUnitTest.groovy.tmpl` | rule | recommended | `*UseCase`, `*InputPort`, `*Repository`, `*Resource`, `*Controller`, `*ViewModel`, `*Dto`, `*Converter` are in correct layers |
| `DddTacticalPatternsArchUnitTest.groovy.tmpl` | rule | DDD-specific | Aggregate Roots, Entities, Value Objects, Repositories obey Vernon's rules |
| `DddStrategicPatternsArchUnitTest.groovy.tmpl` | rule | DDD-specific | Bounded contexts isolated; sharedkernel doesn't depend on contexts; Open Host Service location; integration events location |
| `DddAdvancedPatternsArchUnitTest.groovy.tmpl` | rule | DDD-specific | Domain Events as records; version field on integration events; timestamp on domain events; Domain Services in `domain.service`; Factories stateless |
| `UseCasePatternsArchUnitTest.groovy.tmpl` | rule | **DCA-specific** | InputPort base interface location; `*Command`/`*Query`/`*Result`/`*Response` placement; DTOs not in domain/application |
| `SpringModulithVerificationTest.groovy.tmpl` | rule | conditional | Spring Modulith module structure validity (only if Spring Modulith is on classpath) |

## Cross-template dependencies

All non-base tests extend `BaseArchUnitTest` and inherit its constants and helpers.

### Constants provided by BaseArchUnitTest

| Group | Constants |
|---|---|
| **Package segments** | `BASE_PACKAGE`, `DOMAIN_SUBPKG`, `APP_SUBPKG`, `ADAPTER_SUBPKG`, `INFRASTRUCTURE_SUBPKG`, `INCOMING_SUBFOLDER`, `OUTGOING_SUBFOLDER` |
| **Pattern constants** | `DOMAIN_PACKAGE_PATTERN`, `DOMAIN_MODEL_PACKAGE_PATTERN`, `APPLICATION_PACKAGE_PATTERN`, `ADAPTER_PACKAGE_PATTERN`, `INCOMING_ADAPTER_PACKAGE_PATTERN`, `OUTGOING_ADAPTER_PACKAGE_PATTERN`, `INFRASTRUCTURE_PACKAGE`, `SHAREDKERNEL_DOMAIN_PACKAGE` |
| **Short-form aliases** | `DOMAIN_MODEL_PACKAGE` → `DOMAIN_MODEL_PACKAGE_PATTERN`, `APPLICATION_PACKAGE` → `APPLICATION_PACKAGE_PATTERN`, `ADAPTER_PACKAGE` → `ADAPTER_PACKAGE_PATTERN`, `INCOMING_ADAPTER_PACKAGE` → `INCOMING_ADAPTER_PACKAGE_PATTERN`, `OUTGOING_ADAPTER_PACKAGE` → `OUTGOING_ADAPTER_PACKAGE_PATTERN` |
| **Marker classes** | `AGGREGATE_ROOT_MARKER`, `ENTITY_MARKER`, `VALUE_MARKER`, `ID_MARKER`, `REPOSITORY_MARKER`, `USE_CASE_MARKER`, `INPUT_PORT_MARKER`, `OUTPUT_PORT_MARKER`, `DOMAIN_EVENT_MARKER`, `INTEGRATION_EVENT_MARKER`, `DOMAIN_SERVICE_MARKER`, `FACTORY_MARKER`, `SPECIFICATION_MARKER` |
| **Strategic annotations** | `BOUNDED_CONTEXT_ANNOTATION`, `SHARED_KERNEL_ANNOTATION`, `OPEN_HOST_SERVICE_ANNOTATION` |
| **Naming suffixes** | `USE_CASE_IMPL_SUFFIX` (default `"UseCase"`, configurable via `{{useCaseImplSuffix}}`), `REST_CONTROLLER_SUFFIX` (default `"Controller"`, configurable via `{{restControllerSuffix}}`) |
| **Predicates** | `INFRASTRUCTURE_IMPLEMENTATION` (DescribedPredicate for infra classes) |

### Helper methods provided by BaseArchUnitTest

| Method | Used by |
|---|---|
| `discoverBoundedContextPackages()` | Hexagonal, Layered, Onion, UseCase, Strategic |
| `discoverSharedKernelPackage()` | Strategic |
| `extractContextName(String)` | Strategic (extracts short BC name from package) |
| `extractRootContextPackage(String)` | internal (BC discovery) |
| `getPackageAnnotation(String, Class)` | internal (BC discovery) |
| `getBoundedContextDomainPatterns()` | Tactical, Advanced, Strategic |
| `getBoundedContextDomainModelPatterns()` | Tactical, Advanced |
| `getBoundedContextApplicationPatterns()` | Hexagonal, NamingConventions, UseCase |
| `getBoundedContextAdapterPatterns()` | Tactical |
| `allDomainPatternsWithSharedKernel()` | Layered, Onion, UseCase |
| `allDomainModelPatternsWithSharedKernel()` | Onion, Advanced |
| `allApplicationPatterns()` | Layered, UseCase |
| `allAdapterPatterns()` | NamingConventions |
| `allIncomingAdapterPatterns()` | UseCasePatterns (`*Response` rule) — includes the `@SharedKernel`-annotated module's adapter |
| `allOutgoingAdapterPatterns()` | available for future rules that span all outgoing adapters |

### Per-template dependency matrix

| Template | Markers | Annotations | Short-form aliases | Discovery methods | Naming suffixes |
|---|---|---|---|---|---|
| PackageCycles | — | — | — | — | — |
| HexagonalArchitecture | `OUTPUT_PORT_MARKER` | `BOUNDED_CONTEXT_ANNOTATION` | `DOMAIN_MODEL_PACKAGE`, `APPLICATION_PACKAGE`, `ADAPTER_PACKAGE`, `INCOMING_ADAPTER_PACKAGE`, `OUTGOING_ADAPTER_PACKAGE` | `discoverBoundedContextPackages()` | — |
| LayeredArchitecture | `VALUE_MARKER` | — | — | `allDomainPatternsWithSharedKernel()`, `allApplicationPatterns()` | — |
| OnionArchitecture | — | — | — | `allDomainPatternsWithSharedKernel()`, `allDomainModelPatternsWithSharedKernel()`, `getBoundedContextApplicationPatterns()` | — |
| NamingConventions | `USE_CASE_MARKER`, `INPUT_PORT_MARKER`, `REPOSITORY_MARKER` | — | `APPLICATION_PACKAGE`, `INCOMING_ADAPTER_PACKAGE`, `ADAPTER_PACKAGE` | `allApplicationPatterns()`, `allAdapterPatterns()` | `USE_CASE_IMPL_SUFFIX`, `REST_CONTROLLER_SUFFIX` |
| DddTacticalPatterns | `AGGREGATE_ROOT_MARKER`, `ENTITY_MARKER`, `VALUE_MARKER`, `REPOSITORY_MARKER`, `FACTORY_MARKER` | — | `DOMAIN_MODEL_PACKAGE` | `allDomainModelPatternsWithSharedKernel()`, `allDomainPatternsWithSharedKernel()`, `getBoundedContextApplicationPatterns()`, `getBoundedContextAdapterPatterns()` | — |
| DddStrategicPatterns | `INTEGRATION_EVENT_MARKER` | `BOUNDED_CONTEXT_ANNOTATION`, `OPEN_HOST_SERVICE_ANNOTATION` | — | `discoverBoundedContextPackages()`, `discoverSharedKernelPackage()`, `extractContextName()` | — |
| DddAdvancedPatterns | `DOMAIN_EVENT_MARKER`, `INTEGRATION_EVENT_MARKER`, `DOMAIN_SERVICE_MARKER`, `FACTORY_MARKER`, `SPECIFICATION_MARKER` | — | — | `allDomainPatternsWithSharedKernel()`, `allDomainModelPatternsWithSharedKernel()` | — |
| UseCasePatterns | `VALUE_MARKER` | `BOUNDED_CONTEXT_ANNOTATION` | — | `discoverBoundedContextPackages()`, `allDomainPatternsWithSharedKernel()`, `allApplicationPatterns()` | — |
| SpringModulith | — | — | — | — | — |

### Multi-module ImportOptions

`BaseArchUnitTest` provides custom `ImportOption` implementations for multi-module Gradle projects:

- **`DoNotIncludeTestCode`** — excludes test JARs (`*-test.jar`) and test class directories (`build/classes/**/test*/`)
- **`OnlyProjectJars`** — excludes third-party JARs from Gradle caches/wrapper directories while keeping project module JARs

These replace the standard `DO_NOT_INCLUDE_JARS` / `DO_NOT_INCLUDE_ARCHIVES` which would exclude project module JARs in multi-module setups, preventing bounded context discovery across modules.

## Substitution placeholders

Filled in by the dca-bootstrap skill during install. See `../../../SKILL.md` for the full table.
The most important ones inside these templates:

- `{{basePackage}}` — root package of the project (`com.acme.shop`)
- `{{boundedContextAnnotationFqn}}` and `{{sharedKernelAnnotationFqn}}` — annotation imports
- `{{aggregateRootMarkerFqn}}` and friends — marker FQNs (project-existing or DCA-installed)
- `{{domainSubpackage}}`, `{{appSubpackage}}`, `{{adapterSubpackage}}`, `{{infrastructureSubpackage}}` — layer folder names
- `{{sharedKernelRoot}}` — sharedkernel root folder (typically `sharedkernel`, but the project may use `common`/`shared`)
- `{{extraApplicationPackages}}`, `{{extraAdapterPackages}}` — comma-separated quoted strings for non-context modules (e.g. `"${BASE_PACKAGE}.backoffice.application.."`)

## Things to know about the templates

- **No rule names a bounded context.** Two mechanisms, and the choice matters:
  - *Layer rules* — anything that applies to a layer regardless of which context owns it — use the
    wildcard patterns (`DOMAIN_PACKAGE` = `${BASE_PACKAGE}.*.domain..`, and its siblings). A wildcard
    needs no list at all, and it covers a module that carries the same layering without being a
    bounded context (an operational or backoffice module).
  - *Context rules* — the ones that need the boundary as a concept, such as cross-context isolation —
    use `discoverBoundedContextPackages()` and `discoverSharedKernelPackage()`, so they apply to
    whatever contexts the project declares via `@BoundedContext` / `@SharedKernel`.
  Several layer rules in these templates still take the discovery route, which is why
  `{{extraApplicationPackages}}` exists — a list of non-context modules to patch back in. Converting
  those rules to wildcards would remove the need for that placeholder entirely.
- **Marker classes via constants.** Templates never `import` marker classes by FQN; they reference `BaseArchUnitTest`'s `*_MARKER` static fields. This lets the bootstrap skill point those at the user's existing markers (decision A in the SKILL.md workflow).
- **`@SharedKernel`-annotated package is also discovered**, not hardcoded. So if the user's sharedkernel lives at `com.acme.shop.common` instead of `.../sharedkernel`, the rules still find it via the package-info annotation.

## Known caveats

- `BACKOFFICE_*` from the original dca-ecommerce-sample is replaced with literal patterns inside `EXTRA_APPLICATION_PACKAGES` / `EXTRA_ADAPTER_PACKAGES` in `BaseArchUnitTest`. If the user's project doesn't have a backoffice module, leave those lists empty and the rules collapse cleanly.
- `SpringModulithVerificationTest` will fail to compile if `spring-modulith-starter-test` isn't on the classpath. Only install when Spring Modulith is in use.
- The templates assume Java 21+ for record support. On older Java, a few rules ("must be a record") will fail with informative errors — adjust by removing those specific rules.
