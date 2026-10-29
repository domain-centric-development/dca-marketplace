# Phase 3 — Generation

Part of the `dca-init` skill: what its *Phase 3 — Generation* step points to — the files written per language, step by step, and the `dca.profile.yaml` and `AGENTS.md` section both languages share.

Only after Phase 2. Placeholders use `{{name}}`; `{{#if}}` / `{{#each}}` blocks are resolved by you. Before
each write: if the target exists, ask *overwrite / skip / abort* (default skip). The skill changes no build
file outside the DCA part: dependencies, the architecture source set or project, and nothing else.

**Java**

1. `templates/gradle/build-snippet.gradle.tmpl` → add `dca-building-blocks` and (Spring) `dca-spring` to the
   production `dependencies` (Groovy or Kotlin DSL as the build uses). Maven: `templates/maven/pom-snippet.xml.tmpl`
   (all dependencies; the test then lives in `src/test/java` and `src/test/resources`).
   **Transactions in an in-memory start:** without a data starter there is no `PlatformTransactionManager`,
   so `@Transactional` is silently inert and after-commit listeners never fire while every rule stays green.
   Read `reference/in-memory-transactions.md` and add what it names — the dependency, the placeholder bean
   from `templates/java/InMemoryTransactionManagerConfiguration.java.tmpl` in the package `DCA-LAY-004`
   allows, with Modulith the events API. Say so in the summary.
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
8. `dca.profile.yaml` and the `AGENTS.md` section, as below (`{{verifyCommand}}` = `./gradlew
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
8. `dca.profile.yaml` and the `AGENTS.md` section, as below (`{{verifyCommand}}` = `dotnet test
   tests/{{solutionName}}.ArchitectureTests`).

**`dca.profile.yaml` and `AGENTS.md` section (both languages)**

- `templates/dca.profile.yaml.tmpl` → `dca.profile.yaml` at the project root: flat `key: value` lines, every
  key optional, a missing key takes its default. Write the template's keys and keep every other line
  already there — other skills record their keys in the same file. Its `building_blocks_api:` line points a
  session at the catalog node that documents the markers, so no session hunts for the library's jar; the
  resolved configuration (`reference/resolved-configuration.md`) carries the suffixes from decision D or the
  existing `DcaLayout`; `catalog_path` only with decision G's live catalog. A file that lacks the suffix lines
  gets them on the next run, read from its `DcaLayout`.
- **Migration.** A project with the old conventions file (`.agents/dca/conventions.md`, or
  `.claude/dca/conventions.md`) gets its `key: value` lines moved into `dca.profile.yaml` on this run — a key
  already in `dca.profile.yaml` keeps its value, headings and blank lines are dropped — then the old file is
  removed and the `AGENTS.md` line ``- conventions: `<path>` `` becomes ``- configuration: `dca.profile.yaml` ``.
  A delivery pipeline's `factory.sh update` does the same in code. Say in the summary that the file moved.
- **Glossaries beside the code.** A context's glossary lives in the spec, `<spec>/<context>/glossary.md`
  (`spec:` in `dca.profile.yaml`, `product/spec` by default; `<context>` the context's name in lowercase,
  words joined by `-`). One still beside the domain code (`…/domain/glossary.md`, `…/Domain/glossary.md`) is
  named in the report's Open section; a migration moves it — `factory.sh update` in a project with a
  delivery pipeline, otherwise `git mv` to its place in the spec on the person's confirmation.
- `templates/agents/AGENTS-dca-section.md.tmpl` → the block between `<!-- dca-core: start -->` and
  `<!-- dca-core: end -->` in `AGENTS.md`: added where there is none, replaced where there is one, never
  duplicated. Only this block is the skill's; the rest of `AGENTS.md` — the `dca-describe` section, a delivery
  pipeline's block, the project's own text — stays as it is. Create `AGENTS.md` where the project has none.
- The section carries the line the general skills read — ``- configuration: `dca.profile.yaml` ``, a fixed
  name, the agents' pointer to the file — and the skills by
  role from Phase 1 item 7, each only where it is installed; a role with nothing installed is left out.
  `{{reviewSkills}}` lists the installed ones of `review-ddd`, `review-hexagonal`, `review-clean-code` and
  `dca-audit`. The `- configuration:` and `- <role>:` lines are read by other tools (general skills find the
  configuration through them, a delivery pipeline its carrier names), so keep their form.
- Why the section exists: a person developing by hand in a session has the same information and the same
  means as a stage of a delivery pipeline — the conventions, the skill that carries each craft, the check.
  The pipeline's own configuration is its view of the same installed skills, so the two never name
  different skills.
- Where the project keeps a `CLAUDE.md` without `@AGENTS.md`, say that Claude Code does not read the section
  then, and offer to add the `@AGENTS.md` line.

## Phase 4 — Verification

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
