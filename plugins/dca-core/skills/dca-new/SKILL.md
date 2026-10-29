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

Creates what is new, in one of six modes — in **Java** (Spring) or **C#** (.NET). Templates exist for both:
`*.java.tmpl` and `*.cs.tmpl` side by side.

| Mode | Creates | From |
|---|---|---|
| `project` | a runnable DCA project in an empty directory | a generator, then `dca-init` and `dca-add` |
| `context` | a bounded context: package tree and its declaration | `templates/bounded-context/` |
| `usecase` | input port, command or query, result, implementation | `templates/use-case/` |
| `aggregate` | aggregate root, id, created event, repository port | `templates/aggregate/`, then `dca-modelling` |
| `store` | an operational store port | `templates/store/` |
| `domainservice` | a domain service on the `DomainService` marker | `templates/domain-service/`, then `dca-modelling` |

The code modes lay out files and wiring. The domain types themselves — the invariants, the behaviour, the
events at the right transition — are the craft of `dca-modelling`; `aggregate` and `domainservice` call it
for that part, so the building guide lives in one place. The invariants while editing are `dca-discipline`'s.

This file is the router: the mode, its steps in order, the hard rules, and for every step the reference to
read before it. The detail of each step is in `reference/`.

## Sub-operations

The user's wording determines which mode:

- **"new project"** / "start a DCA project" / an empty directory → [Mode project](#mode-project)
- **"new bounded context X"** / "create context X" / "scaffold X module" → [Mode context](#mode-context)
- **"use case X"** / "create X use case" → [Mode usecase](#mode-usecase)
- **"aggregate X"** / "aggregate root X" / "create domain entity X" → [Mode aggregate](#mode-aggregate)
- **"store for X"** / "operational store" → [Mode store](#mode-store)
- **"domain service X"** / "a rule across X and Y" → [Mode domainservice](#mode-domainservice)

If unclear, ask the user — through a structured question tool where the harness has one, in prose otherwise.

**Never overwrite an existing file.** If a target path exists, stop and ask.

---

## Mode project

**User intent:** "Start a new DCA project here."

Only for a directory without a build file (`build.gradle(.kts)`, `pom.xml`, `*.sln`, `*.slnx`, `*.csproj`). It
may already hold a project description, an `AGENTS.md` or a `.git`. A directory with a build file is an
existing project: point to `dca-init` instead.

Read `reference/project-mode.md` before the first step — it carries every step below in full — and
`reference/questions.md` before step 1. The steps, in order:

1. **The decisions come from the project description** — the stack, the frontend approach, the surfaces and
   the persistence from the description where `dca.profile.yaml` puts it; **every question in one pass, from
   the catalogue** (`reference/questions.md`): ask only the open ones, all at once, before the generator runs,
   in catalogue order, word for word; nothing later in the run. An answer goes where the catalogue says.
2. **The skeleton comes from a generator** — Spring Initializr (read its metadata first) or `dotnet new`;
   versions, dependency ids and project layout come from the generator, never from memory. Offline fallback
   for Java: `reference/greenfield-java-build.md`.
3. **Git** — `git init` where there is no repository, a `.gitignore` for the build's outputs; commit nothing.
4. **The DCA part: `dca-init`** — on the fresh skeleton, with `DCA-STR-012` on `warn`, handed the contexts the
   designed domain names.
5. **The formatter: `dca-add formatter`** — now, while the code base is only the skeleton.
6. **The browser runner: `dca-add browser`** — when the product description names a surface with pages.
6a. **The integration level: `dca-add integration-tests`** — every project gets it, with one smoke test.
7. **Proof** — it starts, every suite is green, the browser smoke test can fail; show each.

**Report:** read from the disk through `dca-init`'s report script (`dca-report.py --mode new …`, the call is in
`reference/project-mode.md`), shown as it is, followed by the one `Next:` line the reference gives.

---

## Convention discovery (run before every code mode)

Read `reference/convention-discovery.md` and follow it before every code mode: the project's `DcaLayout`
in the architecture test is the convention list (every `with…`/`With…` call a deviation from the DCA
default), `dca.profile.yaml` and `dca-archunit.properties` may override it, and without an architecture
test the code itself is scanned. Build a `conventions` summary and (if anything is ambiguous) confirm with
the user before generating. Generate code that matches what's already there.

The five code modes below are carried in full by `reference/element-modes.md` — the parameters, the
placement, the generated files per language, the wiring and the decision tables. Read its section for the
mode before writing a file.

---

## Mode context

**User intent:** "Add a new bounded context called `orders`."

Read the subdomain type in the designed map and check for a pattern-selection ADR before creating a full
DDD context; a context the designed map does not carry is a question about the description (`dca-describe`),
not something to add silently. Then, per `reference/element-modes.md` § Mode context:

1. **Validate** the name (lowercase, single word; a hyphen is a question).
2. **Decide the install location** — single-module package, multi-module Gradle sub-project, or one .NET
   project per context.
3. **Generate the directory tree** per `templates/bounded-context/` (C#: PascalCase segments).
4. **Declare the context** — `package-info.java` with `@BoundedContext`; C#: the `{Context}Context` marker
   class and the `Add{Context}Context()` DI extension.
5. **Add the Gradle module** if multi-module.
6. **Move the context's glossary** from the designed domain into `<spec>/<context>/glossary.md` through
   `ubiquitous-language` — moved, not copied.
7. **Verify:** run the architecture tests if they exist.

---

## Mode usecase

**User intent:** "Add a `placeOrder` use case to the `orders` context."

Required parameters (ask if not given): the context, the use-case name in lowerCamelCase, the type (Command
or Query), the output ports needed. Then, per `reference/element-modes.md` § Mode usecase:

1. **Placement: flat or feature-grouped context** — look at the packages below `{context}/application/`
   first; never mix the two forms (`DCA-USE-014`), `application/shared/` stays context-wide, a vertical
   slice is not a feature.
2. **Generated files** — input port, command or query, result (values only, `DCA-USE-015`), implementation
   with the `ImplSuffix` from convention discovery; the table is in the reference.
3. **Wiring** — constructor injection of the output ports, a `// TODO: implement` body, the project's
   constructor style; C#: the `AddScoped` line in `Add{Context}Context()`. Missing output ports are created
   in `application/shared/`.
4. **Naming check** — warn on a name outside the project's verb pattern, proceed with what was asked.
5. **DTO mapping at the adapter boundary** — read `reference/dto-mapping.md` before writing an adapter's
   mapping; mapping happens at the adapter boundary only, never in the use case, never in the domain.

---

## Mode aggregate

**User intent:** "Create an `Order` aggregate root in the `orders` context."

Required parameters: the context, the aggregate name in PascalCase (a term of the context's glossary — a new
term enters it through `ubiquitous-language` first), the ID type (ask), optional initial fields. Then, per
`reference/element-modes.md` § Mode aggregate:

1. **Generated files** — the root, its id and its `{Name}Created` event in `domain/model/` and
   `domain/event/`, the repository port in `application/shared/`; lombok or explicit accessors per
   convention.
2. **The domain type itself is `dca-modelling`'s** — where the user names invariants and behaviour, call it;
   this mode generates no business method, no setter and no exception type of its own.

---

## Mode store

**User intent:** "Add a `LoginProtection` store to the `customeraccount` context."

A **Store** is the second persistence-shaped output port in DCA, used instead of the aggregate mode's
Repository when the data being persisted has no aggregate lifecycle. Per `reference/element-modes.md`
§ Mode store:

1. **Decision: Store or Repository?** — confirm with the user from the table; choose by lifecycle, lookup by
   id does not decide between them.
2. **Required parameters** — the context, the store name, the stored type, the query methods.
3. **Generated files** — `{Name}Store` / `I{Name}Store` in `application/shared/` with `record(...)` and the
   query methods; no aggregate `save` or `delete`.
4. **Anti-pattern guard** — a `*Repository` for a value object, or a Store for an aggregate root, is
   redirected to the other mode.

---

## Mode domainservice

**User intent:** "Add a `TransferPolicy` domain service to the `accounts` context."

A domain service is part of the domain, framework-free, named in the ubiquitous language; it exists for a
rule that spans several aggregates — **the application calls it**, and it **takes the aggregates as
parameters**. Per `reference/element-modes.md` § Mode domainservice:

1. **Decision: is it a domain service?** — confirm from the table (across aggregates: yes; one aggregate: a
   method, `dca-modelling`; facts the model must ask for: a domain gateway; a long use case: split it).
   `*Manager`/`*Helper` is a technical bucket — ask for the domain's word.
2. **Required parameters** — the context, the name from the glossary, the operation with the aggregates it
   takes and its result type.
3. **Generated files** — `{Name}` on the project's `DomainService` marker in `domain/service/`: stateless, no
   framework annotation, synchronous in C#, one operation with a TODO body.
4. **Wiring** — the use case calls it after loading and before saving; never annotated; no aggregate, entity
   or value object constructs or calls it.
5. **The rule itself is `dca-modelling`'s** — call it for the operation's body.

---

## Templates and substitutions

See `templates/` for the actual `.java.tmpl` and `.cs.tmpl` files — one twin per artefact, pick by language.

The placeholders the templates carry, and what fills each, are listed in `reference/placeholders.md`;
read it before filling a template.

## Idempotency check

Before any write:
```
if Path(target).exists():
    ask user: "{path} already exists. Overwrite / skip / abort?"
    default action: skip
```

## After a code mode

Run the architecture tests if they exist:
```bash
./gradlew test-architecture     # Java (the source set dca-init installs), otherwise ./gradlew :{context}:test
dotnet test tests/*.ArchitectureTests   # .NET (Debug build — ArchUnitNET needs it)
```

When this run created the project's first `domain`, `application` or `adapter` package and
`dca-archunit.properties` carries `dca-init`'s `dca.rules.warn = DCA-STR-012` entry, remove that entry and its
comment block before running the tests, so the rule is enforced from now on. Leave any other `warn` entries
untouched.

Any failures should be findings, not skill bugs. Print:
```
✓ Created {N} files for {mode}
  - Files: {list}
  - Tests: {pass count} / {total}

Next:
  - Implement business logic in {primary file} (dca-modelling for domain types)
  - Wire output ports in the use case impl (look for TODO comments)
```

## Anti-patterns

- **Don't write business logic.** The skill lays out structure; `dca-modelling` and the user's domain expertise fill it.
- **Don't impose conventions** the project doesn't follow. If they use `*ApplicationService`, create `*ApplicationService` — not `*UseCase`.
- **Don't auto-generate Repository methods beyond `findById`/`save`.** Specific finders are project decisions.
- **Don't add Spring `@Component` to domain classes.** Domain stays framework-free (DCA invariant). Same in C#: no
  `[Table]`, no ASP.NET or EF Core attribute in `Domain/`.
- **Don't generate package-info.java for sub-packages** (only for the bounded context root) — keeps the tree clean.
  C#: one `{Context}Context` marker class per context, never per layer.
- **Don't make the C# domain async.** Ports are `Task`-based; aggregates, value objects and domain services stay
  synchronous — a rule of the .NET catalog enforces it.
- **Don't create a domain service that takes values pulled out of an aggregate.** That moves the rule out of the
  domain by the back door; it takes the aggregate.
- **Don't write a project skeleton from memory** while a generator is reachable, and don't take a version from
  memory at all.

Respect `withOperationContainers(...)` / `WithOperationContainers(...)` when a layout
configures organisational folders. Keep one normalized operation depth per context.
Place a port used by one operation beside it; shared is the reuse default.

## Resolved configuration

Read the shared resolved-configuration contract — `dca-init`'s reference `resolved-configuration.md`. `dca-init`
writes those keys into `dca.profile.yaml` for every project; this skill reads and refreshes them from the resolved preset before filling
annotation/import placeholders. `none` uses explicit constructor wiring and `Configuration.java.tmpl`, without
framework imports.
