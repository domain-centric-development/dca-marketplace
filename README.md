# dca-marketplace

A Claude Code marketplace hosting two complementary plugins for **Domain-Centric
Architecture (DCA)** practice and general **software craftsmanship**.

## Plugins

### [dca-core](plugins/dca-core/)

DCA-specific skills and agents:

- **Skills:** `/dca-discipline`, `/ubiquitous-language`, `/context-map`, `/dca-bootstrap`, `/dca-scaffold`, `/dca-review`, `/dca-knowledge`, `/ddd-modelling`, `/review-domain`, `/review-boundaries`
- **Agents:** `ddd-expert`, `ddd-reviewer`, `hexagonal-reviewer` — thin wrappers that apply those
  skills in an isolated context
- **Knowledge:** a vendored OKF knowledge catalog (~350 markdown nodes: DCA guide
  text, marker contracts, architecture rules, recipes, decisions, pitfalls,
  templates) ships inside `/dca-knowledge`, so grounded Q&A and the recipe-driven
  build loop work in any project with zero setup

For projects that follow Domain-Driven Design + Hexagonal Architecture
conventions, in Java/Spring or .NET/C#. `/dca-bootstrap` adds the published
packages — `dev.domaincentric:dca-building-blocks` + `dca-spring` and `dca-archunit`
(+ `dca-archunit-spring-modulith`), or `DomainCentric.BuildingBlocks` + `DomainCentric.ArchRules.Xunit` — generates one
architecture test that runs the whole rule catalog against the project's layout,
and wires its `CLAUDE.md` to the catalog, so a coding agent builds from recipes
and rule checklists instead of from memory.

### [software-craftsmanship](plugins/software-craftsmanship/)

Project-agnostic craftsmanship — usable on any Java or .NET project:

- **Skills:** `/tdd`, `/clean-code`, `/adr`, `/e2e-testing`, `/review-craft`
- **Agents:** `e2e-tester`, `clean-code-reviewer` — thin wrappers that apply those skills in an
  isolated context

No DCA assumptions. Pairs naturally with `dca-core`.

### [dca-factory](plugins/dca-factory/)

The delivery pipeline: one backlog story from plan to verdict.

- **Skills:** `factory-run` (orchestrator), `stage-plan`, `stage-test`, `stage-build`, `stage-tidy`,
  `stage-judge`, `stage-document`; `factory-backlog` writes the backlog a run reads and `factory-scope`
  answers what a run may not decide for itself (a new context, a new relationship, a missing surface); `factory-verify`
  checks the pipeline itself against throwaway fixtures rather than on an agent's word
- **Gate:** `story-gate.py` — a dependency-free script, copied into the project, run between stages

Carries no architecture method — that stays in `dca-core`. What a project contributes lives in one
stack profile it owns: build and test commands, the reviewer for a perspective, the skill that
carries a stage's craft.

## Why three plugins?

Craftsmanship practices (TDD, Clean Code, ADRs, end-user testing) are valuable independent of
architecture style, and a delivery process is a third concern again — methodology, craft and
pipeline change at different times and belong to different owners. Splitting them means:

- Teams not using DCA can still adopt `software-craftsmanship`
- DCA-using teams install `dca-core` plus `software-craftsmanship` for daily practice, and
  `dca-factory` when they want stories delivered through gates
- Updates and versioning evolve at their own pace per plugin

## Installation

```
/plugin marketplace add domain-centric-development/dca-marketplace

/plugin install dca-core@dca-marketplace
/plugin install software-craftsmanship@dca-marketplace
/plugin install dca-factory@dca-marketplace
```

Acceptance: bootstrapping a fresh project ends with the DCA rule catalog running from the published
packages — Java against `dev.domaincentric:dca-archunit` 0.4.0 on Maven Central, .NET against
`DomainCentric.ArchRules.Xunit` 0.4.0 on NuGet.org (both released 2026-09-10, together with the markers
`dca-building-blocks` 0.2.0 and `DomainCentric.BuildingBlocks` 0.1.1). The bootstrap resolves the latest
version itself rather than carrying these numbers.

Working from a local clone instead (e.g. for plugin development):

```
/plugin marketplace add <path-to-your-clone>
```

## Background

DCA is described in:

- [dca-guide](https://github.com/domain-centric-development/dca-guide) — compact reference
- [dca-java](https://github.com/domain-centric-development/dca-java) — `dca-building-blocks` (markers), `dca-spring` (runtime adapters), `dca-archunit` (rules) and `dca-archunit-spring-modulith` (Modulith verification) for Java
- [dca-dotnet](https://github.com/domain-centric-development/dca-dotnet) — `DomainCentric.BuildingBlocks` and `DomainCentric.ArchRules` for .NET
- [dca-ecommerce-sample-java](https://github.com/domain-centric-development/dca-ecommerce-sample-java) — reference Java/Spring implementation
- [dca-ecommerce-sample-dotnet](https://github.com/domain-centric-development/dca-ecommerce-sample-dotnet) — reference .NET implementation

This marketplace turns those principles into Claude Code tooling.

## Author

Christoph Bloemer

*Written with AI assistance — drafted mainly by Claude, reviewed and directed by the author
since 2025.*

## Licence

MIT — see [LICENSE](LICENSE).

Contributions are accepted under the MIT licence, and the copyright holder may additionally publish
them under other licences (for example a documentation licence for prose).
