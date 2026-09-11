# dca-core

DCA-specific skills and reviewer agents — the **Domain-Centric Architecture**
core of the toolset. For project-agnostic craftsmanship bricks (TDD, Clean
Code, ADRs), see the companion plugin
[software-craftsmanship](../software-craftsmanship/).

## Start here

In a project that does not use DCA yet:

```
/dca-bootstrap
```

It adds the published packages and generates **one** architecture test that runs the whole rule
catalog against your layout — nothing else to wire. After that, three skills carry the daily work:
`/dca-discipline` applies the invariants while you edit, `/dca-review` reviews what a static rule
cannot (aggregate design, use-case granularity, port semantics, naming drift), and
`/dca-knowledge` answers a question about DCA from the vendored catalog and cites the node it read.

In a project that already follows the conventions, skip the bootstrap and start with
`/dca-knowledge` or `/dca-review`.

## What's inside

### Skills (10) — applied while writing

| Skill | Purpose | When it triggers |
|---|---|---|
| `/dca-discipline` | Framework-free domain, dependency inversion, bounded-context isolation, event hygiene | Editing `domain/`, `application/`, `adapter/` |
| `/ubiquitous-language` | Per-context glossary, naming consistency checks, polysemy detection | Adding/renaming a domain concept |
| `/context-map` | Strategic DDD context map: with the packages present, maintains the `@Upstream`/`@Partnership` declarations and renders `docs/context-map.md` through `ContextMapRenderer`; otherwise a hand-maintained Mermaid map with auto-detection from code | Introducing a context, changing integration |
| `/dca-bootstrap` | Adds the published packages (Java: `dca-building-blocks` + `dca-archunit`; .NET: `DomainCentric.BuildingBlocks` + `DomainCentric.ArchRules.Xunit`), generates one architecture test with the project's `DcaLayout` and a `dca-archunit.properties`, and wires the project's `CLAUDE.md` to the knowledge catalog | Introducing DCA conventions into a new or existing Java or .NET codebase |
| `/dca-scaffold` | Scaffolds bounded contexts, use cases (Command/Query + InputPort + Result + Impl), aggregate roots — Java or C# | Creating new DCA structure for a feature |
| `/dca-review` | Semantic review of Java or .NET code against DCA conventions (aggregate design, use-case granularity, port semantics, result shape, event hygiene) — complements the rule catalog | Auditing a diff or path set for DCA compliance |
| `/ddd-modelling` | The tactical-modelling craft: aggregates, entities, values, ids, domain and integration events, domain services, factories, specifications, repositories and stores, in both language spellings | Designing or implementing a domain concept |
| `/review-domain` | The **domain** review perspective: real invariants vs. anemic records, entity vs. value, aggregate boundaries, ubiquitous language, event hygiene, repository vs. store | Reviewing a change from the model's point of view |
| `/review-boundaries` | The **boundaries** review perspective: dependency direction, port granularity, adapter direction, framework leaks, input-port shape, translation at the edge | Reviewing a change from the ports-and-adapters point of view |
| `/dca-knowledge` | Grounded Q&A + recipe-driven **build loop** over the OKF knowledge catalog — traverses marker↔rule↔ADR↔section links, cites the source `resource:`, and `save` promotes answers into permanent catalog nodes | Asking what DCA says about X, why an ADR was made, or constructing DCA code ("add a use case") from recipes + rule checklists |

### Agents (3) — the same craft in an isolated context

| Agent | Applies | Adds |
|---|---|---|
| `ddd-expert` | `/ddd-modelling` | own context, write tools — for a long modelling session |
| `ddd-reviewer` | `/review-domain` | own context, read-only tools — no "fix" slips into a review |
| `hexagonal-reviewer` | `/review-boundaries` | same, for the boundaries perspective |

**Knowledge lives in the skill, isolation in the agent.** Each agent is a thin wrapper that applies
its skill and adds nothing to it. That split is deliberate: an agent only exists in a tool that has
agents, so knowledge held in an agent alone would be unavailable everywhere else. A project on
another agent tool loads the same skills and works to the same standard; where agents exist, the
reviewers can also run in parallel, each in its own context.

Builder and reviewer stay complementary: `/ddd-modelling` *writes*, `/review-domain` *audits*. Use
the first when designing an aggregate, the reviewers (alongside `/review-craft` from
`software-craftsmanship`) for PR-style review.

## Recommended companion

Install [software-craftsmanship](../software-craftsmanship/) alongside for:

- `/tdd` — Red-Green-Refactor workflow that pairs naturally with
  `/dca-discipline`
- `/adr` — records DCA-rule exceptions when `/dca-discipline` allows
  bending a rule
- `/clean-code` + `clean-code-reviewer` — for readability concerns the
  DCA reviewers explicitly leave out of scope

## Conventions overlay

The project's conventions live in its architecture test: the `DcaLayout` passed
to `DcaArchitectureTest` (base package or root namespace, layer folder names
such as `incoming` vs `in`, suffixes such as `*UseCase` vs `*ApplicationService`
and `*Resource` vs `*Controller`) and the rule selection in
`dca-archunit.properties`. Skills and agents read those first. The optional
overlay

```
<project-root>/.claude/dca/conventions.md
```

adds what the test cannot express:
- Glossary and context-map paths
- `catalog_path` — location of the OKF knowledge bundle for `/dca-knowledge`
- Naming decisions the team made beyond the layout (e.g. part-record suffixes)

Falls back to `<project-root>/CLAUDE.md`, then to DCA defaults from
[dca-guide](https://github.com/domain-centric-development/dca-guide).

## Composability matrix (within dca-core)

| Combination | What happens |
|---|---|
| `/context-map` + `/ubiquitous-language` | Shared terms across contexts trigger ACL/Published-Language suggestions |
| `/dca-discipline` + `ddd-reviewer` | Discipline catches violations while writing; reviewer catches what slipped through |
| `ddd-reviewer` ∥ `hexagonal-reviewer` (parallel) | Two perspectives, two reports — overlaps = real findings, divergences = judgment calls |
| `/dca-knowledge` + `/dca-review` | Review flags a violation; `/dca-knowledge` explains the rule's rationale (ADR) and cites the source |

## The vendored knowledge catalog

`/dca-knowledge` ships a **vendored copy of the OKF knowledge catalog**
(`skills/dca-knowledge/catalog/`, ~350 markdown nodes): the full DCA
implementation guide anchored to the building-block marker contracts and the
rule catalog of both libraries, plus the authored extensible zone (recipes,
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
/plugin marketplace add domain-centric-development/dca-marketplace
/plugin install dca-core@dca-marketplace
/plugin install software-craftsmanship@dca-marketplace   # recommended companion
```

## Author

**Christoph Bloemer** — [@chbloemer](https://github.com/chbloemer)
