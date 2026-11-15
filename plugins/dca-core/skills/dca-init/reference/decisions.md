# Phase 2 — Decisions

What each decision A–G means; the wording of the questions is `reference/questions.md`.

A. **Marker policy** (INIT-MARKERS) — per existing marker-like type:
   - `Migrate` — replace it with the package marker (`extends BaseAggregateRoot<T, ID>`, `implements Value`,
     …); mechanical, the old type is deleted.
   - `Alias` — keep the type, make it extend or implement the package marker
     (`interface Aggregate<T, ID> extends AggregateRoot<T, ID>`); existing code compiles unchanged and the
     rules see every implementor. Recommended for large code bases; an alias must carry the same generics
     (rules report the class by *its* markers).
   - `Role` — keep the type, name it in the layout's marker roles (`reference/own-vocabulary.md`, with limits).

B. **Layout** (INIT-LAYOUT where folders cannot be mapped) — every deviation from the DCA defaults becomes a `DcaLayout` builder call (Java / .NET):
   - `adapter/in`, `adapter/out` → `withIncomingSubpackage("in")`, `withOutgoingSubpackage("out")` /
     `WithIncomingSegment("In")`, `WithOutgoingSegment("Out")`
   - published contract package other than `api` / `events` → `withApiSubpackage`, `withEventsSubpackage` /
     `WithApiSegment`, `WithEventsSegment`
   - third-party packages the domain may use → `allowingInDomain("org.jmolecules..")` /
     `AllowingInDomain("NodaTime")`
   - INIT-EXCLUDE, INIT-LOCAL-PORTS, an undeclared shared kernel → `reference/own-vocabulary.md`
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
   Recommendation by project profile and subdomain type: `reference/module-selection-guide.md` (the one place;
   `dca-add rules` reads it too). Core contexts run the full catalog, supporting and generic may run the
   structural baseline only — record it in a pattern-selection ADR. Subdomain types from the designed map
   (`domain:` in `dca.profile.yaml`, default `product/domain.md`); none there → ask. Rejected rule →
   `dca.rules.off` + `dca.rule.<id>.reason`; worked towards → `dca.rules.warn` — both visible in the report,
   preferred over a silent gap. Accepted baseline → `dca-add freeze`, after this skill.

D. **Suffix conventions** (INIT-SUFFIX where the code uses two) — DCA's defaults are `*UseCase` for the use-case class, `*InputPort` for its
   interface, `*Controller` for MVC (server-rendered) controllers and `*Resource` for REST adapters (.NET
   default `Controller` for both). `*ApplicationService` / `*Service` → `withUseCaseSuffix(...)`; `*Page` /
   `*Handler` for MVC controllers → `withControllerSuffix(...)`; `*Controller` / `*Endpoint` for REST →
   `withRestControllerSuffix(...)`; input-port interfaces not named `*InputPort` → `withInputPortSuffix(...)`. The `naming` set then holds the project to *its* convention, and
   `dca.profile.yaml` records the resolved suffixes (`use_case_suffix:` and the others) so that whoever names a
   new element reads them there, before the suite runs.
   The failure suffix is the project's choice, not the suite's: a domain or use-case failure is named by the
   rule it breaks, and `failure_suffix:` says what follows — `Exception` by default, as Java
   and .NET expect, `none` where the team names failures without it (`InsufficientStock`). On a retrofit,
   read it from the existing failures; where they use both, ask.

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
   `catalog_path:` in `dca.profile.yaml`, set by hand, pointing at a locally regenerable
   `dca-knowledge-catalog/bundle` (verify it holds `index.md` and `log.md`).
