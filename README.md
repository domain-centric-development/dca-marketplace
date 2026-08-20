# dca-marketplace

A Claude Code marketplace hosting two complementary plugins for **Domain-Centric
Architecture (DCA)** practice and general **software craftsmanship**.

## Plugins

### [dca-core](plugins/dca-core/)

DCA-specific skills and agents:

- **Skills:** `/dca-discipline`, `/ubiquitous-language`, `/context-map`, `/dca-bootstrap`, `/dca-scaffold`, `/dca-review`, `/dca-knowledge`
- **Agents:** `ddd-expert` (builder), `ddd-reviewer`, `hexagonal-reviewer`
- **Knowledge:** a vendored OKF knowledge catalog (~740 markdown nodes: DCA guide
  text, marker contracts, ArchUnit rules, ADRs, recipes, decisions, pitfalls,
  templates) ships inside `/dca-knowledge`, so grounded Q&A and the recipe-driven
  build loop work in any project with zero setup

For projects that follow Domain-Driven Design + Hexagonal Architecture
conventions. `/dca-bootstrap` installs the marker interfaces + ArchUnit suite
into a fresh or existing project and wires its `CLAUDE.md` to the catalog, so a
coding agent builds from recipes and rule checklists instead of from memory.

### [software-craftsmanship](plugins/software-craftsmanship/)

Project-agnostic craftsmanship — usable on any Java/Spring project:

- **Skills:** `/tdd`, `/clean-code`, `/adr`
- **Agents:** `e2e-tester` (builder), `clean-code-reviewer`

No DCA assumptions. Pairs naturally with `dca-core`.

## Why two plugins?

Craftsmanship practices (TDD, Clean Code, ADRs) are valuable independent of
architecture style. Splitting them out means:

- Teams not using DCA can still adopt `software-craftsmanship`
- DCA-using teams install both for a complete daily-practice setup
- Updates and versioning evolve at their own pace per plugin

## Installation

```
/plugin marketplace add chbloemer/dca-marketplace

/plugin install dca-core@dca-marketplace
/plugin install software-craftsmanship@dca-marketplace
```

Working from a local clone instead (e.g. for plugin development):

```
/plugin marketplace add <path-to-your-clone>
```

## Background

DCA is described in:

- [implementing-domain-centric-architecture](https://github.com/chbloemer/domain-centric-architecture) — compact reference
- [dca-ecommerce-sample](https://github.com/chbloemer/dca-ecommerce-sample) — reference Java/Spring implementation

This marketplace turns those principles into Claude Code tooling.

## Author

Christoph Bloemer
