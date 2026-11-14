# Bootstrap a new application — digest

Node: `/recipe/bootstrap-a-new-application.md` — cite it by that path; read it in full only for a decision this digest leaves open.

Stand up a fresh Domain-Centric Architecture app from nothing: the building-block dependencies, the package skeleton, the rule catalog as a test, and the first bounded context.

## Steps (first sentence each)

0. **Describe it, then generate it** — before any code, the product, the technical decisions and the designed cut ([Three parts](/guide/factory/three-parts.md), [The project description](/guide/factory/the-project-description.md)); then the skeleton from the stack's own generator, so the versions are the generator's, never recalled; then a repository.
1. **Add the building blocks** — the marker interfaces (`InputPort`, `UseCase`, `OutputPort`, `Repository`, `DomainEvent`, `Value`, `@BoundedContext`, …) are a published dependency, never project code: Java `dev.domaincentric:dca-building-blocks` (packages `ddd.tactical`, `ddd.strategic`, `hexagonal.port.in/.out`, `application`), .NET `DomainCentric.BuildingBl…
2. **Lay the package skeleton** — the four-layer template per context (`domain/`, `application/` + `shared/`, `adapter/incoming|outgoing/`, optional `infrastructure/`) and a global `infrastructure/` for cross-cutting config.
3. **Add the rule catalog as a test** — `dev.domaincentric:dca-archunit` in the architecture test source set and one class `ArchitectureTest extends DcaArchitectureTest` returning the project's `DcaLayout`; `dca-archunit.properties` scopes and tunes the rules ([Core rule categories](/guide/archunit-governance/core-rule-categories.md) explain what they check).
4. **Set up ADRs** — copy the ADR template and record the foundational decisions (hexagonal architecture, shared kernel, ArchUnit governance, pattern selection).
5. **Add the first bounded context** — classify its subdomain, then follow [Add a bounded context](/recipe/add-a-bounded-context.md) and seed one vertical slice with [Add a use case](/recipe/add-a-use-case.md).
6. **Verify** — the project's build and architecture suite (`./gradlew build && ./gradlew test-architecture`, or `dotnet build && dotnet test -c Debug` against the architecture-test project); the suite is green on an empty-but-correct skeleton.

## Templates

- `/template/project-starter-agent-instructions.md` Project starter: agent instructions for a catalog-driven DCA project: A drop-in instructions block for a **new project** so a coding agent (any LLM, any harness) builds it *from this catalog* instead of from memory.
