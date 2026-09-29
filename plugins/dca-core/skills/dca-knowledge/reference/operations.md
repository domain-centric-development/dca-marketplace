# dca-knowledge — the operations in full

The core of the skill (`SKILL.md`) says where the catalog is, how its graph is shaped and how to cite.
This file carries what a lookup rarely needs at once: each operation with an example, the build loop,
the `save` workflow, token discipline, what to do when the catalog looks stale, how the skill pairs with
its neighbours and how to read a node's review status.

## Operations

### `/dca-knowledge ask <question>`
Default. Route → locate → read → expand → answer, grounded + cited.
> "Why must aggregate roots not reference other aggregate roots by type?"
> → reads the tactical rule + its `Applies to markers` + the marker's `Discussed in` section, answers with all three cited.

### `/dca-knowledge explain <concept>`
Concept walkthrough from the **guide** body (the teaching text), then anchor to the
concrete `marker`/`rule` nodes that realize it.
> "explain the use case pattern" → relevant section(s) + `/marker/port-in/usecase.md` + its governing rules.

### `/dca-knowledge rules-for <marker|concept>`
List the `Rule` nodes governing a marker (follow `Governed by`), with each rule's
`status` and `enforced_by` test.
> "rules-for Repository" → all rules whose `Applies to markers` includes `/marker/port-out/repository.md`.

### `/dca-knowledge why <rule | pattern>`
Pull the `Rule` node's `rule:` (the rationale — the `.because(...)` text), the markers it
`Applies to`, and those markers' `Discussed in` guide sections. Surfaces constraint +
rationale + teaching text as one answer. The catalog carries no ADR nodes, so a question
about a *specific* recorded decision has no grounded answer here — say so.

### `/dca-knowledge trace <node>`
Graph dump for one node: all inbound/outbound typed edges (marker ↔ rule ↔ section).
Use to understand how one concept is wired through the catalog before a deeper question.

### `/dca-knowledge find <text>`
Keyword locate across frontmatter `title`/`tags` (+ bodies if needed). Returns a ranked
node table (path, type, one-line). A locator, not an answer — follow with `ask`/`explain`.

### `/dca-knowledge build <thing>` (the build loop)
When the user is **constructing** DCA code ("add a use case", "create an aggregate",
"publish a cross-context event"), drive the build loop instead of just explaining:

1. **Recipe** — read the matching `/recipe/<...>.md` for ordered steps. Unsure which?
   `/recipe/build-a-dca-application.md` is the task router mapping tasks to recipes.
2. **Decide** — follow any `decision/` link the recipe gates on first (e.g. sync-vs-async).
3. **Template** — emit from the linked `/template/<...>.md` skeleton.
4. **Checklist** — satisfy the recipe's "Rules to satisfy" *while generating* — each links a
   `rule/` node whose `constraint:` is the one-line precondition (read `selects`/`checks` before the Java/ArchUnit or C# evidence).
5. **Verify** — run the project's architecture test suite (`./gradlew test-architecture` for Java, `dotnet test -c Debug` for .NET).

If no recipe covers the task, build from the relevant `marker/` (+ its `Governed by` rules)
and offer to `save` a new `recipe/` so the next build is covered.

### `/dca-knowledge save [note|decision|pitfall|recipe|template] <title>`
**Compound** — promote a query answer (this turn's, or one just given) into a permanent
**extensible-zone** node so the wiki grows instead of re-deriving. Pick the type:
- `note` — a synthesis worth keeping ("domain vs integration events in an outbox")
- `decision` — a design-fork guide ("sync vs async event delivery")
- `pitfall` — an anti-pattern + the rule that forbids it
- `recipe` — an ordered task playbook · `template` — a domain-free code skeleton

Prepare a proposal in the consuming project's notes, or in the owning catalog repository's `authored/<type>/<slug>.md`
source workflow when that checkout is available. Include type/title/tags, evidence and bundle-relative links.
The resolved mirror, installed plugin cache and `bundle/` are read-only: never write a save there.
The owner reviews the source and regenerates/tests/lints the canonical bundle before updating the mirror.
Saving a proposal does not make it authoritative.

> **When to offer it:** after any `ask`/`explain` that took real graph traversal or
> resolved a non-obvious question, offer to `save` it. That is the Query→page loop — the
> catalog compounds. Don't save trivial lookups (a single rule/marker already covers them).

## Token discipline

- Lead with `index.md` files (small) before node bodies.
- Filter on frontmatter (`type`/`tags`/`status`) before reading bodies.
- Sections are atomic — read the one section, not the whole chapter.
- Inspect file size before reading large guide nodes; read the relevant subsection and retain its caveats.
- For broad/fan-out questions across many nodes, delegate to a read-only research subagent over the
  bundle dir where the harness has one, and keep only its conclusion in main context.

## When the catalog looks stale

The bundle shipped with this plugin is a **generated, derived artifact** and is read-only here:
the sources it was generated from are not installed with it. Never hand-edit a node — an edit
survives until the next plugin update and nothing else.

When citing, the node body is the source of truth. If an answer looks out of date against the
libraries the project actually uses, say so in the answer and report it to the catalog's
maintainers, together with the node path and `manifest.json`'s `bundle_sha256` — that digest, not
the plugin version, identifies which catalog you read. Do not try to regenerate.

Regenerating, linting and saving new authored nodes are the catalog repository's own workflow and
are documented in its `AGENTS.md`.

## Relationship to other skills

| Skill | How it pairs |
|---|---|
| `/dca-discipline`, `/dca-audit` | They *apply* the rules while editing/reviewing; this skill *explains and cites* the rule + its rationale on demand. |
| `/dca-init` | Init installs the markers/ArchUnit suite; this skill answers "what does each installed rule mean and why". |
| `/dca-new` | New lays out structure; ask this skill which marker/pattern a new use case should follow, with citation. |
| `/dca-modelling` | Builds the domain types; this skill supplies the recipe, template and rules it builds from. |
| `/adr` | Records a new decision in the consuming project. The catalog does not ingest ADRs — it carries `process/creating-an-adr.md`, the how-to. |
| `/context-map`, `/ubiquitous-language` | Strategic/naming views of the live code; this skill is the canonical-knowledge view of the documented patterns. |

## What this skill does NOT do

- **Doesn't edit mirrors, plugin cache or bundle output.** `save` prepares an owning-source proposal;
  generation and review publish knowledge. Read current counts from `index.md` / `log.md` when needed.
- **Doesn't answer from memory.** No catalog node = no grounded answer. It says so rather
  than guessing.
- **Doesn't replace `/dca-audit`.** It explains rules; it doesn't audit your code against them.
- **Doesn't fetch remote catalogs.** It reads a local bundle (in-repo or vendored); pointing
  at a remote copy is the user's setup step.

## Review status and retrieval order

1. Read `manifest.json` to identify the snapshot and library versions, then use `rule/index-compact.md` for exact id lookup.
2. Read the target node's `selects`/`checks`, status, implementations and resolved framework before its evidence.
3. For authored nodes, `review:` says how far the node has been checked, not whether it is usable.
   - `reviewed` — an owner and evidence have been verified. Cite it as the answer.
   - `draft` (the majority today) — written and wired into the graph, not yet through a review
     pass. Use it, and say once that the construction guidance is a draft. Never let it override a
     generated node: the rules, markers and guide text are derived from the code and win on every
     contradiction. If it disagrees with a rule's `selects`/`checks`, the rule is right.
   - `superseded` — history. Cite it only to explain what changed, follow `superseded_by`, and
     inspect that node's own status; nothing is promoted automatically.
   - missing — treat as `draft`.
4. Prefer the requested language's evidence (`.NET reading` / C# expression for .NET). Large nodes offer `Evidence slices`; read the relevant slice together with the parent selection/check and caveats. Full nodes remain available.
5. `Governed by` and `Applies to markers` are reviewed mappings. Every `Related mentions` link is heuristic navigation, including mentions derived from `selects`; it does not prove applicability.
6. Do not add Spring dependencies to .NET or framework-neutral projects. Verify Java with its architecture task and .NET with `dotnet test -c Debug`.
