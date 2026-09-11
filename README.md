# dca-marketplace

Three Claude Code plugins for **Domain-Centric Architecture (DCA)**: the architecture method, the
craftsmanship practices around it, and a delivery pipeline that puts one story through gates
instead of through good intentions.

They also work outside Claude Code — Codex and OpenCode read the same skill folders (see
[Other tools](#other-tools)).

## Install

Add the marketplace once, then install what you need. No clone, no build step:

```
/plugin marketplace add domain-centric-development/dca-marketplace

/plugin install dca-core@dca-marketplace                 # the architecture method
/plugin install software-craftsmanship@dca-marketplace   # TDD, Clean Code, ADRs, end-user tests
/plugin install dca-factory@dca-marketplace              # the delivery pipeline
```

Check it worked: `/plugin` lists each one as *installed*, and its skills appear under the plugin's
name — `dca-core:dca-bootstrap`, `dca-factory:factory-run`, and so on. A plugin that stays absent
after `/plugin marketplace add` was added to the marketplace but never installed; install it by
name as above.

To pick up new versions later:

```
/plugin marketplace update dca-marketplace
```

Only for working *on* these plugins — a clone, so edits take effect without a release:

```
/plugin marketplace add <path-to-your-clone>
```

## Which plugin do I need?

| You want to | Install |
|---|---|
| write DDD/hexagonal code with the conventions enforced, ask what DCA says about something | `dca-core` |
| add DCA to an existing project: packages, one architecture test, conventions | `dca-core` (`/dca-bootstrap`) |
| TDD, Clean Code, ADRs and end-user tests — with or without DCA | `software-craftsmanship` |
| deliver stories through plan → test → build → tidy → judge → document with a gate between | `dca-factory` (+ `dca-core` for the method) |

`dca-core` and `software-craftsmanship` are what a developer invokes directly. `dca-factory` owns
the *process* and calls them; it carries no architecture knowledge of its own, so there is never a
second truth about how the code should look.

## Using it

### Adopt DCA in a project

```
/dca-bootstrap
```

It adds the published packages — Java `dev.domaincentric:dca-building-blocks` + `dca-archunit`
(Maven Central), .NET `DomainCentric.BuildingBlocks` + `DomainCentric.ArchRules.Xunit`
(NuGet.org) — and generates **one** architecture test that runs the whole rule catalog against
your project's layout. From then on `/dca-discipline` applies the invariants while you edit,
`/dca-review` reviews what static rules cannot, and `/dca-knowledge` answers "what does DCA say
about X" from a catalog it cites rather than from memory.

Details, skill by skill: **[dca-core/README.md](plugins/dca-core/README.md)**.

### Deliver a story through the pipeline

```
/factory-backlog          # write the epic and the story, in the contract the gate reads
/factory-run              # plan → test → build → tidy → judge → document, gated
/factory-verify           # check what that run actually did, and the pipeline itself
```

The pipeline needs two things from your project: a **stack profile**
(`.agents/factory/factory.profile.yaml` — your build and test commands) and the gate script next to
it. `factory-run` sets both up on first use, or run the installer directly:

```
bash <plugin>/skills/factory-run/scripts/factory.sh install --tool claude
```

Details, including the backlog contract and every gate check:
**[dca-factory/README.md](plugins/dca-factory/README.md)**.

### Craftsmanship on its own

```
/tdd            # red, green, refactor — with the failing test first
/clean-code     # names, function size, smells, while you edit
/adr            # record a decision so the next reader finds the reasoning
/e2e-testing    # Page Objects, stable selectors, one flow per test
```

No DCA assumptions; usable on any Java or .NET project.
Details: **[software-craftsmanship/README.md](plugins/software-craftsmanship/README.md)**.

## How the three fit together

Three layers with three owners, which is why they are three plugins:

| Layer | Owner | Where it lives |
|---|---|---|
| **method** — markers, rules, conventions, review perspectives, the knowledge catalog | the architecture | `dca-core` |
| **craft** — how a test, a name, a decision record is written | the profession | `software-craftsmanship` |
| **pipeline** — stages, gates, backlog contract, hand-over files | the delivery process | `dca-factory` |
| **project knowledge** — build commands, test source sets, glossary, context map, backlog | *your project* | files in your repository |

They change at different times and for different reasons. A new rule is a method change; a new
build command is a project change; a new stage is a process change. Nothing in the pipeline knows
your domain, and nothing in the method knows your build.

## Other tools

The pipeline's carriers are deliberately portable: `SKILL.md` folders and one dependency-free
script — no plugin manifest, no hooks, no agent frontmatter. Codex and OpenCode discover skills
from a project-local directory, so the installer writes them there:

```
bash <plugin>/skills/factory-run/scripts/factory.sh install --tool codex      # or opencode, or all
```

For those tools it links the craft skills as well, because they have no plugin mechanism to find
them by. Verified: Codex 0.153.0 and OpenCode 1.18.15 list the same skills and run the same
stages against the same gate.

## Troubleshooting

**A plugin does not appear after adding the marketplace.** Adding a marketplace makes its plugins
*available*; each still has to be installed by name (`/plugin install <name>@dca-marketplace`).

**A skill I edited in a clone does not change anything.** Installed plugins are copies taken from a
git commit, not from your working tree. Commit, then `/plugin marketplace update` — or, while
developing, add the clone as the marketplace and let the project link the skill folder directly.

**The pipeline says a command is "skipped and named".** Your stack profile does not declare it. That
is deliberate: a gate that fails on something nobody configured gets switched off, so it reports the
gap instead. Add the command to `.agents/factory/factory.profile.yaml`.

**A gate refuses a story I consider fine.** Read the check name in its output — each one states what
it refused and why. `factory-verify` shows the same checks against fixtures if you suspect the gate
rather than the story.

## Background

DCA is described in:

- [dca-guide](https://github.com/domain-centric-development/dca-guide) — compact reference
- [dca-java](https://github.com/domain-centric-development/dca-java) — `dca-building-blocks` (markers), `dca-spring` (runtime adapters), `dca-archunit` (rules) and `dca-archunit-spring-modulith` (Modulith verification) for Java
- [dca-dotnet](https://github.com/domain-centric-development/dca-dotnet) — `DomainCentric.BuildingBlocks` and `DomainCentric.ArchRules` for .NET
- [dca-ecommerce-sample-java](https://github.com/domain-centric-development/dca-ecommerce-sample-java) — reference Java/Spring implementation
- [dca-ecommerce-sample-dotnet](https://github.com/domain-centric-development/dca-ecommerce-sample-dotnet) — reference .NET implementation

This marketplace turns those principles into Claude Code tooling.

## Author

**Christoph Bloemer** — [@chbloemer](https://github.com/chbloemer)

*Written with AI assistance — drafted mainly by Claude, reviewed and directed by the author
since 2025.*

## Licence

MIT — see [LICENSE](LICENSE).

Contributions are accepted under the MIT licence, and the copyright holder may additionally publish
them under other licences (for example a documentation licence for prose).
