# dca-core

DCA-specific skills and reviewer agents — the **Domain-Centric Architecture**
core of the toolset. For project-agnostic craftsmanship bricks (TDD, Clean
Code, ADRs), see the companion plugin
[software-craftsmanship](../software-craftsmanship/).

## What's inside

### Skills (7) — applied while writing

| Skill | Purpose | When it triggers |
|---|---|---|
| `/dca-discipline` | Framework-free domain, dependency inversion, bounded-context isolation, event hygiene | Editing `domain/`, `application/`, `adapter/` |
| `/ubiquitous-language` | Per-context glossary, naming consistency checks, polysemy detection | Adding/renaming a domain concept |
| `/context-map` | Strategic DDD context map with Mermaid + auto-detection from code (Spring Modulith, events, ACL mappers) | Introducing a context, changing integration |
| `/dca-bootstrap` | Installs DCA marker interfaces + ArchUnit governance suite into a Java/Spring project, and wires the project's `CLAUDE.md` to the knowledge catalog | Introducing DCA conventions into a new or existing codebase |
| `/dca-scaffold` | Scaffolds bounded contexts, use cases (Command/Query + InputPort + Result + Impl), aggregate roots | Creating new DCA structure for a feature |
| `/dca-review` | Semantic review against DCA conventions (aggregate design, use-case granularity, port semantics, event hygiene) — complements ArchUnit | Auditing a diff or path set for DCA compliance |
| `/dca-knowledge` | Grounded Q&A + recipe-driven **build loop** over the OKF knowledge catalog — traverses marker↔rule↔ADR↔section links, cites the source `resource:`, and `save` promotes answers into permanent catalog nodes | Asking what DCA says about X, why an ADR was made, or constructing DCA code ("add a use case") from recipes + rule checklists |

### Agents (3) — builder + review-time perspectives

| Agent | Role | Perspective / Sources |
|---|---|---|
| `ddd-expert` | **Builder** — designs and implements tactical DDD code (aggregates, events, repositories, value objects, services, factories, specifications) | Evans, Vernon |
| `ddd-reviewer` | **Reviewer** — checks finished code for DDD compliance | Evans, Vernon |
| `hexagonal-reviewer` | **Reviewer** — dependency direction, port granularity, adapter direction, framework leaks, use-case shape | Cockburn, Palermo, Hombergs |

`ddd-expert` and `ddd-reviewer` are complementary: the expert *writes*, the
reviewer *audits*. Invoke the expert when designing a new aggregate; invoke
the reviewer (alongside `hexagonal-reviewer` and `clean-code-reviewer`) for
PR-style review.

## Recommended companion

Install [software-craftsmanship](../software-craftsmanship/) alongside for:

- `/tdd` — Red-Green-Refactor workflow that pairs naturally with
  `/dca-discipline`
- `/adr` — records DCA-rule exceptions when `/dca-discipline` allows
  bending a rule
- `/clean-code` + `clean-code-reviewer` — for readability concerns the
  DCA reviewers explicitly leave out of scope

## Conventions overlay

All skills and agents in this plugin read this optional file if present:

```
<project-root>/.claude/dca/conventions.md
```

It can override:
- Base package and marker FQNs
- Layer folder names (`incoming` vs `in`, `outgoing` vs `out`)
- Suffix conventions (`*UseCase` vs `*ApplicationService`, `*Resource` vs
  `*Controller`)
- Glossary, context-map paths
- `catalog_path` — location of the OKF knowledge bundle for `/dca-knowledge`

Falls back to `<project-root>/CLAUDE.md`, then to DCA defaults from
[implementing-domain-centric-architecture](https://github.com/chbloemer/domain-centric-architecture).

## Composability matrix (within dca-core)

| Combination | What happens |
|---|---|
| `/context-map` + `/ubiquitous-language` | Shared terms across contexts trigger ACL/Published-Language suggestions |
| `/dca-discipline` + `ddd-reviewer` | Discipline catches violations while writing; reviewer catches what slipped through |
| `ddd-reviewer` ∥ `hexagonal-reviewer` (parallel) | Two perspectives, two reports — overlaps = real findings, divergences = judgment calls |
| `/dca-knowledge` + `/dca-review` | Review flags a violation; `/dca-knowledge` explains the rule's rationale (ADR) and cites the source |

## The vendored knowledge catalog

`/dca-knowledge` ships a **vendored copy of the OKF knowledge catalog**
(`skills/dca-knowledge/catalog/`, ~740 markdown nodes): the full DCA book and
implementation guide anchored to the reference implementation's marker
contracts, ArchUnit rules and ADRs, plus the authored extensible zone (recipes,
design-fork decisions, pitfalls, code templates, notes). It is regenerated from
the sources on every catalog build, so it never drifts — and it makes grounded
answers and the build loop work in any project with no setup. An in-repo or `catalog_path`-configured catalog takes precedence
over the vendored snapshot.

## What this plugin deliberately does NOT include

- **Generic craftsmanship** (TDD, Clean Code, ADRs) — see
  software-craftsmanship.
- **Event Storming / Discovery workshops** — those are facilitated activities,
  not tooling.

## Installation

```
/plugin marketplace add chbloemer/dca-marketplace
/plugin install dca-core@dca-marketplace
/plugin install software-craftsmanship@dca-marketplace   # recommended companion
```

## Author

Christoph Bloemer
