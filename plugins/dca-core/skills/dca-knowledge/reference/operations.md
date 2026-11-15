# dca-knowledge — the operations in full

## Operations

### `/dca-knowledge ask <question>`
Default. Route → locate → read → expand → answer, cited.
> "Why must aggregate roots not reference other aggregate roots by type?" → the tactical rule + its
> `Applies to markers` + the marker's guide section, all three cited.

### `/dca-knowledge explain <concept>`
Guide body (teaching text) first, then the `marker`/`rule` nodes that realize it.

### `/dca-knowledge rules-for <marker|concept>`
The `Rule` nodes via `Governed by`, each with `status` and `enforced_by` — all rules whose `Applies to markers`
includes the marker.

### `/dca-knowledge why <rule | pattern>`
The rule's `rule:` (the `.because(...)` rationale), the markers it `Applies to`, their guide sections. No ADR
nodes exist: a question about a specific recorded decision has no grounded answer — say so.

### `/dca-knowledge trace <node>`
All inbound/outbound typed edges of one node (marker ↔ rule ↔ section).

### `/dca-knowledge find <text>`
Keyword locate over front matter `title`/`tags` (bodies if needed) → ranked table (path, type, one line). A
locator, not an answer; follow with `ask`/`explain`.

### `/dca-knowledge build <thing>` (the build loop)
For constructing DCA code ("add a use case", "create an aggregate", "publish a cross-context event"):

1. **Recipe** — the matching `/recipe/<...>.md`. Unsure → `/recipe/build-a-dca-application.md` routes tasks to recipes.
2. **Decide** — any `decision/` the recipe gates on, first (e.g. sync vs async).
3. **Template** — emit from the linked `/template/<...>.md`.
4. **Checklist** — satisfy the recipe's "Rules to satisfy" while generating; each links a `rule/` node whose
   `constraint:` is the precondition (read `selects`/`checks` before the Java/ArchUnit or C# evidence).
5. **Verify** — the architecture suite: `./gradlew test-architecture` (Java), `dotnet test -c Debug` (.NET).

No recipe → build from the `marker/` and its `Governed by` rules; offer to `save` a `recipe/`.

### `/dca-knowledge save [note|decision|pitfall|recipe|template] <title>`
Promote an answer into an extensible-zone node: `note` (a synthesis), `decision` (design-fork guide), `pitfall`
(anti-pattern + the rule forbidding it), `recipe` (ordered playbook), `template` (domain-free skeleton).

- Write a proposal in the consuming project's notes, or as `authored/<type>/<slug>.md` in the owning catalog
  repository when that checkout is available. Include type/title/tags, evidence, bundle-relative links.
- Never write into the resolved mirror, plugin cache or `bundle/`. The owner reviews, regenerates, tests, lints,
  then updates the mirror. A proposal is not authoritative.
- Offer `save` after an `ask`/`explain` that took real traversal or settled a non-obvious question; not for
  trivial lookups one node covers.

## Token discipline

- `index.md` files before bodies; filter on `type`/`tags`/`status` first.
- One section, not the chapter. Check a large guide node's size; read the relevant subsection, keep its caveats.
- Broad fan-out questions → a read-only research subagent over the catalog where the harness has one; keep only
  its conclusion.

## When the catalog looks stale

The shipped catalog is generated and read-only; its sources are not installed. Never hand-edit a node. The node
body is the source of truth when citing. Looks out of date against the project's libraries → say so and report
to the catalog's maintainers with the node path and `manifest.json`'s `bundle_sha256` (that digest, not the
plugin version, identifies the catalog). Do not regenerate; regeneration, linting and saving are the catalog
repository's workflow (its `AGENTS.md`).

## Relationship to other skills

| Skill | Pairing |
|---|---|
| `/dca-discipline`, `/dca-audit` | apply the rules; this skill explains and cites them. Auditing code is `/dca-audit`, never this |
| `/dca-init` | installs markers and the suite; this skill says what each rule means and why |
| `/dca-new` | lays out structure; ask here which marker/pattern applies, cited |
| `/dca-modelling` | builds domain types from the recipe, template and rules supplied here |
| `/adr` | records a project's decision; the catalog ingests no ADRs, it carries `process/creating-an-adr.md` |
| `/context-map`, `/ubiquitous-language` | strategic/naming views of live code; this is the documented-pattern view |

## What this skill does NOT do

- Edit mirrors, plugin cache or bundle output. Read current counts from `index.md` / `log.md` when needed.
- Answer from memory: no node, no grounded answer.
- Fetch remote catalogs: it reads a local bundle; pointing at a remote copy is the user's setup.

## Review status and retrieval order

1. `manifest.json` for snapshot and library versions; `rule/index-compact.md` for exact id lookup.
2. A target node's `selects`/`checks`, status, implementations and resolved framework before its evidence.
3. Authored `review:` says how far it was checked, not whether usable:
   - `reviewed` — owner and evidence verified; cite as the answer.
   - `draft` (majority) — use it, say once the guidance is a draft. Never over a generated node; disagrees with a
     rule's `selects`/`checks` → the rule is right.
   - `superseded` — cite only to explain what changed; follow `superseded_by`, check that node's status; nothing
     is promoted automatically.
   - missing — `draft`.
4. Prefer the requested language's evidence (`.NET reading` / C# expression for .NET). Large nodes have
   `Evidence slices`: read the relevant slice with the parent's selection, check and caveats.
5. `Governed by` and `Applies to markers` are reviewed mappings. Every `Related mentions` link is heuristic
   navigation (including those derived from `selects`), not proof of applicability.
6. No Spring dependencies in .NET or framework-neutral projects. Verify Java with its architecture task, .NET
   with `dotnet test -c Debug`.
