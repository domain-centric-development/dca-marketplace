# AGENTS.md

Guidance for AI coding agents working in `dca-marketplace`. This file may hold cross-project
pointers; skill, agent and reference content must not link into sibling repositories.

## Repository Overview

`dca-marketplace` is a Claude Code plugin marketplace that turns Domain-Centric Architecture (DCA)
into tooling. It is the *tooling* expression of the patterns in `dca-guide/` and `dca-book/`,
demonstrated by both reference implementations and enforced by the rule libraries `dca-java` and
`dca-dotnet`. It contains no doctrine of its own: when a pattern, rule or naming convention changes
elsewhere, this repository follows.

```
dca-marketplace/
├── .claude-plugin/marketplace.json        # manifest — owner: the domain-centric-development org
├── plugins/dca-core/                      # DCA-specific skills + agents (Java/Spring and .NET/C#)
│   ├── .claude-plugin/plugin.json
│   ├── skills/dca-bootstrap/              # installs the published packages, generates one architecture test
│   │   ├── reference/archunit-rule-catalog.md   # GENERATED — see below
│   │   └── templates/                     # Spring Modulith verification test only (WP-17 replaces it)
│   ├── skills/dca-knowledge/catalog/      # GENERATED mirror of dca-knowledge-catalog/bundle — never hand-edit
│   ├── skills/{dca-discipline,dca-review,dca-scaffold,context-map,ubiquitous-language}/
│   └── agents/{ddd-expert,ddd-reviewer,hexagonal-reviewer}.md
├── plugins/software-craftsmanship/        # project-agnostic skills + agents (any Java or .NET project)
├── scripts/render-rule-catalog.py         # renders the rule catalog reference from the sibling rules.json files
└── MULTI-HARNESS-PORTABILITY.md           # notes on running the skills outside Claude Code
```

## The two plugins

- **dca-core** — `/dca-bootstrap`, `/dca-discipline`, `/ubiquitous-language`, `/context-map`, `/dca-scaffold`,
  `/dca-review`, `/dca-knowledge`; agents `ddd-expert` (builder), `ddd-reviewer`, `hexagonal-reviewer`. Every skill
  and agent speaks both languages: Java/Spring (`UseCase<I,O>`, packages, `package-info.java`) and .NET/C#
  (`IUseCase<TIn,TOut>`, namespaces, a `[BoundedContext]` marker class).
- **software-craftsmanship** — `/tdd`, `/clean-code`, `/adr`; agents `e2e-tester`, `clean-code-reviewer`. No DCA
  assumptions; usable alone.

## Generated content — never hand-edit

| Path | Source | Regenerate |
|---|---|---|
| `plugins/dca-core/skills/dca-knowledge/catalog/` | `../dca-knowledge-catalog/bundle/` | `cd ../dca-knowledge-catalog && PYTHONPATH=src python3 -m dca_catalog.generate` (mirrors here by default; the mirror drops the `resource:` frontmatter) |
| `plugins/dca-core/skills/dca-bootstrap/reference/archunit-rule-catalog.md` | `../dca-java/rules.json`, `../dca-dotnet/rules.json` | `python3 scripts/render-rule-catalog.py` |

The rendered files carry no link into a sibling repository — content travels, links do not. Check
the sources, not the copies, when a rule text looks wrong.

## How the bootstrap works

`/dca-bootstrap` installs DCA **via the published packages** and generates one thin architecture test:

- Java: `dev.domaincentric:dca-building-blocks` (markers) + `dca-spring` (Spring implementations of
  `DomainEventPublisher`/`TransactionBoundary`, auto-configured) in production, `dca-archunit` (rules) + with Modulith
  `dca-archunit-spring-modulith` (`DcaSpringModulithTest`) in the `test-architecture` source set, `ArchitectureTest extends
  DcaArchitectureTest` with the project's `DcaLayout`, and `dca-archunit.properties` for the rule selection. No
  templates for adapters or the Modulith test remain; the four artifacts are versioned independently.
- .NET: `DomainCentric.BuildingBlocks` + `DomainCentric.ArchRules.Xunit`, a `*.ArchitectureTests` project with
  `DcaArchitectureTests : DcaArchitectureTest` (Debug builds), from NuGet.org (0.1.0 since 2026-09-07). A
  conditional project reference to a sibling `dca-dotnet` checkout is offered only on request, for unreleased rules.

It ships no marker or rule templates. The single remaining template is the Spring Modulith verification test,
installed only when Modulith is present. Retrofit follows "adapt, don't overwrite": existing marker-like
interfaces are aliased to the library ones or kept and declared through `DcaLayout`.

## Sync duties

| Change elsewhere | Update here |
|---|---|
| Rule added/changed in `dca-java` / `dca-dotnet` (`rules.json`) | `python3 scripts/render-rule-catalog.py`; `dca-review/reference/checklist.md` if the rule has a semantic counterpart; `dca-discipline/SKILL.md` layer table if it names rules |
| Consumer API of the libraries (`DcaLayout` options, `DcaArchitectureTest`, `dca-archunit.properties` keys, package coordinates) | `dca-bootstrap/SKILL.md`, its templates and `reference/*` |
| Building-block marker added/renamed | `dca-scaffold` templates, `dca-discipline`, `ddd-expert`, `ddd-reviewer`, `hexagonal-reviewer` (both language examples) |
| Naming convention or package/namespace structure in the guide | `dca-review/reference/naming-conventions.md`, `dca-scaffold/SKILL.md` + templates, `dca-discipline/SKILL.md` |
| Use-case / result pattern in the guide or samples | `dca-review/reference/use-case-pattern.md`, `dca-scaffold/templates/use-case/` |
| Guide text (`dca-guide/*.md`) or authored catalog nodes | regenerate the catalog; the mirror follows |
| Context-map relationships or renderer options | `context-map/SKILL.md` |

Sync targets in the other direction: root `AGENTS.md` § 5 (plugin contents, installation), `planning/porting-status.md`
row "Marketplace bootstrap branch".

## Conventions for skill content

- Prose describes the current state, never history.
- Java and C# examples side by side where behaviour differs; one example where it does not.
- No links into sibling repositories; cite the guide by name, not by path or URL.
- Skills never invent DCA conventions — they point to `/dca-knowledge` (the vendored catalog) when unsure.
- Tool-agnostic knowledge lives in the catalog; anything about Claude Code, slash commands or plugins lives here.

## Versioning

Plugin versions live in `plugins/*/.claude-plugin/plugin.json` (SemVer). Bump the minor version for new skills or
agents, the major (pre-1.0: minor) for a breaking change in what a skill installs or expects — the switch of the
bootstrap from templates to packages was such a change.

## Test-drive

```
/plugin marketplace add <path-to-this-clone>
/plugin install dca-core@dca-marketplace
/plugin install software-craftsmanship@dca-marketplace
```

Try `/dca-bootstrap` on a fresh Spring Boot project and on a fresh .NET web project; both must end with a green
architecture test that runs the whole rule catalog. Published installation:
`/plugin marketplace add domain-centric-development/dca-marketplace`.

## Commit message format

Conventional commits, scope = plugin or skill: `feat(dca-core): …`, `docs: …`, `chore(bootstrap): …`.
