# dca-core

The **Domain-Centric Architecture** method as skills, for Java/Spring and .NET/C#. For the craft
around it that holds in any architecture style — TDD, Clean Code, ADRs, end-user tests, the glossary,
the context map and three general review perspectives — see the companion plugin
[dca-craft](../dca-craft/).

## Start here

The verbs follow one another — describe → new → init → add:

| Where you start | Skill |
|---|---|
| nothing written yet | `/dca-describe` — the project description under `project/`, with you |
| an empty directory | `/dca-new` — a running skeleton from the stack's generator, then git, the DCA part, a formatter, and a browser runner where there are pages |
| an existing project | `/dca-init` — the DCA part only |
| one capability later | `/dca-add rules <module>` · `freeze` · `formatter` · `browser` · `http-stub` |

`/dca-init` adds the published packages and generates **one** architecture test that runs the whole
rule catalog against your layout — nothing else to wire — and writes the method's section into
`AGENTS.md`: the conventions file and the installed skills by role, so a person developing by hand
has what a pipeline stage has. After that the daily work: `/dca-modelling` builds the domain types,
`/dca-discipline` applies the invariants while you edit, `/dca-review` reviews what a static rule
cannot (aggregate design, use-case granularity, port semantics, naming drift), and `/dca-knowledge`
answers a question about DCA from the vendored catalog and cites the node it read.

The same start gives the same questions and the same report. `/dca-describe`, `/dca-new project` and
`/dca-init` each ask from a question catalogue (`reference/questions.md`): every answer is looked up first,
and only the open ones are asked — all at once, in the catalogue's order, word for word. `/dca-new project`
asks the description's, its own and `/dca-init`'s open questions in one pass before the generator runs.
Both end with a report read from the disk (`dca-init/scripts/dca-report.py`) — Stack, Generator, DCA part,
Formatter, Browser runner, Proof, Git, Open — with every field present and `—` where there is nothing.

## What's inside

### Skills (8)

| Skill | Purpose | When it triggers |
|---|---|---|
| `/dca-describe` | Writes the project description with the person — `project/product.md`, `project/tech.md`, `project/domain.md` (through `/context-map`) — and the `AGENTS.md` line that makes every implementation read them first; drafts from the code where there is code, never invents an answer | Before the first code or story, or when the description is missing |
| `/dca-new` | `project` from an empty directory (generator, git, `/dca-init`, `/dca-add formatter`, `/dca-add browser`); `context`, `usecase`, `aggregate`, `store`, `domainservice` lay out one more element, Java or C#. Invoked by a person only | Starting a project; adding DCA structure |
| `/dca-init` | Adds the published packages (Java: `dca-building-blocks` + `dca-archunit`; .NET: `DomainCentric.BuildingBlocks` + `DomainCentric.ArchRules.Xunit`), one architecture test with the project's `DcaLayout`, a `dca-archunit.properties`, and the method's section in `AGENTS.md` | Introducing DCA into an existing Java or .NET codebase |
| `/dca-add` | One capability into an existing setup: another rule module, freezing existing violations, a formatter (formatted once, whole), a browser runner | A capability the project gains later |
| `/dca-modelling` | The tactical-modelling craft: aggregates, entities, values, ids, domain and integration events, domain services, factories, specifications, repositories and stores, in both language spellings; a new term goes through `/ubiquitous-language`; ends with a report | Designing or implementing a domain concept |
| `/dca-discipline` | The invariants, in one place: framework-free domain, dependency inversion, bounded-context isolation, event hygiene, named failures | Editing `domain/`, `application/`, `adapter/` |
| `/dca-review` | Semantic review against DCA conventions the rules cannot check (aggregate design, use-case granularity, port semantics, result shape, event hygiene, declarations against the map); a delivery pipeline's judge runs it as the added `dca` perspective | Auditing a diff or path set for DCA compliance |
| `/dca-knowledge` | Grounded Q&A + recipe-driven **build loop** over the OKF knowledge catalog — traverses marker↔rule↔ADR↔section links, cites the source `resource:`, and `save` promotes answers into permanent catalog nodes | Asking what DCA says about X, or constructing DCA code from recipes + rule checklists |

dca-core has no agents. A long modelling session may run in a subagent where the tool has them; the
reviewer agents live in dca-craft beside the perspectives they apply.

## Recommended companion

Install [dca-craft](../dca-craft/) alongside: `/ubiquitous-language` and `/context-map` keep the
glossary and the designed map the method's skills write through, `/e2e-testing` carries the browser
runner `/dca-add browser` sets up, and `/review-ddd`, `/review-hexagonal`, `/review-clean-code` give
the outside view beside `/dca-review`.

## Conventions overlay

The project's conventions live in its architecture test: the `DcaLayout` passed
to `DcaArchitectureTest` (base package or root namespace, layer folder names
such as `incoming` vs `in`, suffixes such as `*UseCase` vs `*ApplicationService`
and `*Resource` vs `*Controller`) and the rule selection in
`dca-archunit.properties`. Skills read those first. The conventions file
`/dca-init` names in `AGENTS.md` (by default `.agents/dca/conventions.md`)
adds what the test cannot express:
- Glossary paths
- `catalog_path` — location of the OKF knowledge bundle for `/dca-knowledge`
- Naming decisions the team made beyond the layout (e.g. part-record suffixes)

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

- **Craft independent of the architecture style** (TDD, Clean Code, ADRs, end-user tests, glossary,
  context map, the general review perspectives) — see dca-craft.
- **Event Storming / Discovery workshops** — those are facilitated activities,
  not tooling.

## Installation

```
/plugin marketplace add domain-centric-development/dca-marketplace
/plugin install dca-core@dca-marketplace
/plugin install dca-craft@dca-marketplace   # recommended companion
```

## Author

**Christoph Bloemer** — [@chbloemer](https://github.com/chbloemer)
