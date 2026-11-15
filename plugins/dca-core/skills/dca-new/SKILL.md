---
name: dca-new
disable-model-invocation: true
description: |
  Creates new Domain-Centric Architecture (DCA) code in Java/Spring or .NET/C#, in six modes: `project` (an
  empty directory becomes a runnable DCA project — skeleton from Spring Initializr or `dotnet new`, git,
  then dca-init and dca-add), `context` (a bounded context), `usecase` (Command/Query + InputPort + Result +
  implementation), `aggregate` (aggregate root with Id, Repository and Created event), `store` (an
  operational store port) and `domainservice` (a domain service on the DomainService marker). Use when the
  user asks to "start a new DCA project", "create a new bounded context", "scaffold a use case", "add an
  aggregate root", "add a domain service", or "/dca-new". Adapts to existing project conventions: reads the
  project's DcaLayout (architecture test) and `dca.profile.yaml`, plus existing code style. Never overwrites
  files.
---

# dca-new

Six modes, Java (Spring) and C# (.NET); templates are twins `*.java.tmpl` / `*.cs.tmpl`.

| Mode | Creates | From | Wording |
|---|---|---|---|
| `project` | a runnable DCA project in an empty directory | a generator, then `dca-init`, `dca-add` | "new project", "start a DCA project", empty directory |
| `context` | a bounded context: package tree + declaration | `templates/bounded-context/` | "new bounded context X", "scaffold X module" |
| `usecase` | input port, command/query, result, implementation | `templates/use-case/` | "use case X" |
| `aggregate` | root, id, created event, repository port | `templates/aggregate/`, then `dca-modelling` | "aggregate (root) X", "domain entity X" |
| `store` | an operational store port | `templates/store/` | "store for X", "operational store" |
| `domainservice` | a domain service on the `DomainService` marker | `templates/domain-service/`, then `dca-modelling` | "domain service X", "a rule across X and Y" |

- Unclear mode → ask (structured question tool where the harness has one, else prose).
- Code modes lay out files and wiring only. Domain types (invariants, behaviour, events at the transition) are
  `dca-modelling`'s; editing invariants are `dca-discipline`'s.
- **Never overwrite an existing file.** Target exists → ask "{path} already exists. Overwrite / skip / abort?",
  default skip.

---

## Mode project

Only for a directory without a build file (`build.gradle(.kts)`, `pom.xml`, `*.sln`, `*.slnx`, `*.csproj`); it may
hold a description, `AGENTS.md` or `.git`. Build file present → point to `dca-init`.

Read `reference/project-mode.md` before step 1 (every step in full) and `reference/questions.md` (the catalogue).

1. **The decisions come from the project description** — stack, frontend approach, surfaces, persistence.
   **Every question in one pass, from the catalogue**: only the open ones, all at once, before the generator, in
   catalogue order, word for word; nothing later. Each answer goes where the catalogue says.
2. **The skeleton comes from a generator** — Spring Initializr (metadata first) or `dotnet new`; versions,
   dependency ids, layout never from memory. Java offline: `reference/greenfield-java-build.md`.
3. **Git** — `git init` if none, `.gitignore` for build outputs; commit nothing.
4. **The DCA part: `dca-init`** — `DCA-STR-012` on `warn`, handed the contexts the designed domain names.
5. **The formatter: `dca-add formatter`** — now, on the bare skeleton.
6. **The browser runner: `dca-add browser`** — when the product names a surface with pages.
6a. **The integration level: `dca-add integration-tests`** — always, with one smoke test.
7. **Proof** — it starts, every suite green, the browser smoke test can fail; show each.

**Report:** `dca-init`'s `dca-report.py --mode new …` (call in `reference/project-mode.md`), shown as is, then the
one `Next:` line given there.

---

## Convention discovery (run before every code mode)

Follow `reference/convention-discovery.md`: the architecture test's `DcaLayout` is the convention list (every
`with…`/`With…` a deviation), `dca.profile.yaml` and `dca-archunit.properties` may override, no test → scan the
code. Build a `conventions` summary, confirm ambiguities, generate to match.

The code modes are carried in full by `reference/element-modes.md` (parameters, placement, files per language,
wiring, decision tables). Read the mode's section before writing a file.

- Respect `withOperationContainers(...)` / `WithOperationContainers(...)`; one normalized operation depth per
  context. A port used by one operation sits beside it; shared is the reuse default.
- Resolved configuration: read `dca-init`'s reference `resolved-configuration.md` (keys `dca-init` writes into
  `dca.profile.yaml`); refresh them from the resolved preset before filling annotation/import placeholders.
  `none` = explicit constructor wiring and `Configuration.java.tmpl`, no framework imports.

---

## Mode context

Read the subdomain type in the designed map; check for a pattern-selection ADR before a full DDD context. A
context the map lacks is a question for `dca-describe`, never added silently. Per `reference/element-modes.md`
§ Mode context:

1. **Validate** the name: lowercase, one word; a hyphen is a question.
2. **Decide the install location** — single-module package, Gradle sub-project, or one .NET project per context.
3. **Generate the directory tree** from `templates/bounded-context/` (C#: PascalCase).
4. **Declare the context** — `package-info.java` with `@BoundedContext`; C#: `{Context}Context` marker class +
   `Add{Context}Context()` DI extension.
5. **Add the Gradle module** if multi-module.
6. **Move the context's glossary** from the designed domain into `<spec>/<context>/glossary.md` via
   `ubiquitous-language` — moved, not copied.
7. **Verify:** run the architecture tests if they exist.

---

## Mode usecase

Ask for what is missing: context, name (lowerCamelCase), Command or Query, output ports, expected refusals (or
none). Per `reference/element-modes.md` § Mode usecase:

1. **Refusal style** — `Refusals (<context>): …`, else `Refusals: …` in the technical description, else the
   context's existing use cases; neither → ask (thrown or returned, equal) and write the line via `dca-describe`.
2. **Placement: flat or feature-grouped context** — inspect `{context}/application/` first; never mix
   (`DCA-USE-014`); `application/shared/` stays context-wide; a vertical slice is not a feature.
3. **Generated files** — input port, command/query, result (values only, `DCA-USE-015`; closed with one `Refusal`
   case per refusal where the context returns them; the success case never carries it), implementation with the
   discovered `ImplSuffix`.
4. **Wiring** — constructor injection, `// TODO: implement` body, the project's constructor style; C#: `AddScoped`
   in `Add{Context}Context()`. Missing output ports go to `application/shared/`.
5. **Naming check** — warn on a name outside the project's verb pattern; proceed as asked.
6. **DTO mapping at the adapter boundary** — read `reference/dto-mapping.md` before an adapter's mapping; never in
   the use case or domain.

---

## Mode aggregate

Parameters: context, name in PascalCase (a glossary term — a new one enters via `ubiquitous-language` first), ID
type (ask), optional fields. Per `reference/element-modes.md` § Mode aggregate:

1. **Generated files** — root, id, `{Name}Created` in `domain/model/` and `domain/event/`; repository port in
   `application/shared/`; lombok or explicit accessors per convention.
2. **The domain type itself is `dca-modelling`'s** — call it where invariants/behaviour are named; this mode writes
   no business method, setter or exception type.

---

## Mode store

A Store replaces a Repository when the persisted data has no aggregate lifecycle. Per `reference/element-modes.md`
§ Mode store:

1. **Decision: Store or Repository?** — confirm from the table; by lifecycle, never by lookup-by-id.
2. **Required parameters** — context, store name, stored type, query methods.
3. **Generated files** — `{Name}Store` / `I{Name}Store` in `application/shared/` with `record(...)` + query
   methods; no `save`/`delete`.
4. **Anti-pattern guard** — `*Repository` for a value object, or a Store for an aggregate root → the other mode.

---

## Mode domainservice

Domain, framework-free, named in the ubiquitous language, for a rule spanning several aggregates; **the
application calls it** and it **takes the aggregates as parameters**. Per `reference/element-modes.md`
§ Mode domainservice:

1. **Decision: is it a domain service?** — across aggregates: yes; one aggregate: a method (`dca-modelling`);
   facts the model must ask for: a domain gateway; a long use case: split it. `*Manager`/`*Helper` → ask for the
   domain's word.
2. **Required parameters** — context, glossary name, the operation with its aggregates and result type.
3. **Generated files** — `{Name}` on the `DomainService` marker in `domain/service/`: stateless, no framework
   annotation, synchronous in C#, one operation with a TODO body.
4. **Wiring** — the use case calls it after loading, before saving; never annotated; no aggregate, entity or value
   object constructs or calls it.
5. **The rule itself is `dca-modelling`'s** — call it for the body.

---

## Templates and substitutions

`templates/` holds one `.java.tmpl` / `.cs.tmpl` twin per artefact. Read `reference/placeholders.md` before
filling one.

## After a code mode

```bash
./gradlew test-architecture     # Java (the source set dca-init installs), otherwise ./gradlew :{context}:test
dotnet test tests/*.ArchitectureTests   # .NET (Debug build — ArchUnitNET needs it)
```

If this run created the first `domain`, `application` or `adapter` package and `dca-archunit.properties` has
`dca-init`'s `dca.rules.warn = DCA-STR-012` entry, remove that entry and its comment block before the run. Leave
other `warn` entries. Failures are findings, not skill bugs. Print:
```
✓ Created {N} files for {mode}
  - Files: {list}
  - Tests: {pass count} / {total}

Next:
  - Implement business logic in {primary file} (dca-modelling for domain types)
  - Wire output ports in the use case impl (look for TODO comments)
```

## Anti-patterns

- No business logic — `dca-modelling` and the user fill it.
- No imposed conventions: project uses `*ApplicationService` → create `*ApplicationService`.
- Repository methods only `findById`/`save`; finders are project decisions.
- Domain framework-free: no `@Component`; C# no `[Table]`, ASP.NET or EF Core attribute in `Domain/`.
- `package-info.java` only at the context root; C# one `{Context}Context` marker per context, never per layer.
- C# domain synchronous: ports are `Task`-based; aggregates, value objects, domain services not (a .NET rule
  enforces it).
- A domain service takes the aggregate, never values pulled out of it.
- No skeleton from memory while a generator is reachable; no version from memory at all.
