# Phase 2 — Decisions

Part of the `dca-init` skill: what its *Phase 2 — Decisions* step points to — the knowledge behind every decision A–G; `reference/questions.md` holds the wording of the questions.

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
   Share `reference/module-selection-guide.md` for the recommendation by project profile and subdomain type.
   It is the one place for that knowledge: `dca-add rules` reads the same file when a set is added later.
   Strictness varies by subdomain: core contexts run the full catalog, supporting and generic contexts may run
   the structural baseline only — record that in a pattern-selection ADR. The subdomain types come from the
   designed map (`domain:` in `dca.profile.yaml`, `product/domain.md` by default); where it
   has none, ask. A single rule the team rejects
   becomes `dca.rules.off` + `dca.rule.<id>.reason`; one they are working towards `dca.rules.warn`. Both stay
   visible in the report — prefer that over a silent gap. Existing violations the team accepts as a baseline
   are `dca-add freeze`, after this skill.

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
