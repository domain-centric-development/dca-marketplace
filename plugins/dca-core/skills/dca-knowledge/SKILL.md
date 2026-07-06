---
name: dca-knowledge
description: |
  Answers Domain-Centric Architecture questions grounded in the generated OKF
  knowledge catalog (`dca-knowledge-catalog/bundle/`) — the full book + guide text
  anchored to marker contracts, ArchUnit rules, and ADRs as one cross-linked graph.
  Loads `index.md`, traverses typed links (governed-by / applies-to / enforced-by /
  referenced-by), and cites the source `resource:` for every claim. Use when the user
  asks "what does DCA say about X", "which rule governs this marker", "why this
  decision (ADR)", "explain <DCA concept>", "/dca-knowledge", or wants an answer
  grounded in the canonical catalog rather than the model's own recollection.
disable-model-invocation: false
---

# /dca-knowledge — Grounded Q&A over the OKF catalog

The OKF bundle is the **canonical, machine-readable DCA knowledge base**: ~690 atomic
markdown nodes, each with typed frontmatter and bundle-relative cross-links forming a
graph. Two zones:

- **Generated** (book chapters/sections, implementation-guide sections, 22 marker
  contracts, 87 ArchUnit rules, 26 ADRs, 1 process) — derived from the sources.
- **Extensible** (`recipe/`, `decision/`, `pitfall/`, `template/`, `note/`) — authored
  by a human or an LLM, preserved across regeneration. May be empty until populated.

This skill answers DCA questions **from that bundle** — not from the model's own
memory — and **cites** the node + its `resource:` (the live source file) for every
claim. It is the read/query counterpart to the catalog generator in
`dca-knowledge-catalog/`.

> **Grounding rule (non-negotiable):** Answer only from nodes you actually read in the
> bundle. If the bundle doesn't cover it, say so — don't fill the gap from general DDD
> knowledge. Mark any such supplement explicitly as *outside the catalog*.

## Locating the bundle

Resolve the catalog path in this order; stop at the first that exists:

1. `catalog_path` in `<project-root>/.claude/dca/conventions.md` (explicit override wins)
2. `dca-knowledge-catalog/bundle/` relative to repo root (working in this repo)
3. `${CLAUDE_PLUGIN_ROOT}/skills/dca-knowledge/catalog/` — the **vendored copy that
   ships with the plugin**; always present once the plugin is installed, so
   `/dca-knowledge` works in any project with no extra setup
4. `.claude/dca/catalog/` (a manually vendored copy inside the consuming project)
5. Any directory containing both `index.md` and `log.md` with OKF frontmatter

Prefer the in-repo bundle (#2) over the vendored copy (#3) when both exist — the in-repo
one is freshly regenerable; the vendored one is a snapshot from the plugin's release.

> **Vendored copy is book-redacted:** in the plugin's catalog, `book/` nodes carry only
> frontmatter, a one-line description and their graph links — the verbatim chapter text is
> not shipped (the book is not public). All other node types are complete. When a deep
> book quote is needed and only the vendored copy is available, say so and answer from the
> `guide/` sections (full text) plus the node's metadata instead of guessing the book text.

If none found, tell the user the catalog isn't present and how to get it:

```bash
cd dca-knowledge-catalog && PYTHONPATH=src python3 -m dca_catalog.generate
```

or vendor the `bundle/` into `.claude/dca/catalog/` and set `catalog_path`.

## Node types & typed edges

The bundle is a graph. Knowing the node types and edge labels lets you traverse it
without reading everything.

| Node `type` | Lives in | Carries | Key outgoing edges |
|---|---|---|---|
| `Chapter` / `Guide` | `book/`, `guide/` | preamble + `## Sections` index | → child Sections |
| `Section` | `book/<ch>/`, `guide/<g>/` | **full verbatim text** | `## Related markers`, embedded `/adr/...` links |
| `Marker` | `marker/<cat>/` | interface signature, `extends`, methods | `## Extends`, `## Governed by` (rules), `## Referenced by ADRs` |
| `Rule` | `rule/<cat>/` | ArchUnit/Spock body, `enforced_by`, `status` | `## Applies to markers` |
| `ADR` | `adr/` | decision `pattern`, `status` | `## Applies to markers`, `## Enforced by` (rules), `## Decision process` |
| `Process` | `process/` | how-to (e.g. writing an ADR) | → any |
| `Recipe`/`Decision`/`Pitfall`/`Template`/`Note` | `recipe/` … `note/` (**extensible zone**) | authored playbooks, design-fork guides, anti-patterns, code skeletons, saved query answers | links into the skeleton |

**Link format:** bundle-relative, leading `/`, `.md` suffix — e.g. `/marker/port-in/usecase.md`.
Resolve against the bundle root, not the current file.

**Frontmatter as filter:** `type`, `tags`, `category`, `status` (rules/ADRs:
`enforced`/`accepted`/etc.), `source` (book vs guide). Use these to narrow before reading bodies.

**Reserved files** (`index.md`, `log.md`) are navigation, not knowledge — read them to
route, don't cite them as answers.

## Traversal protocol

Don't grep-and-dump. Walk the graph like a researcher:

1. **Enter** — read `bundle/index.md` (node-type counts + links to category indices).
2. **Route** — pick the category whose `type` fits the question:
   - "what/why/how concept" → `book/` or `guide/` section
   - "what's the contract / interface" → `marker/`
   - "what's enforced / is this allowed" → `rule/`
   - "why this decision / what's the rationale" → `adr/`
3. **Locate** — read the category `index.md`, pick candidate node(s) by title/slug.
4. **Read** — read the node body + frontmatter.
5. **Expand** — follow typed edges that the question needs:
   - marker → `Governed by` to get its enforced rules
   - marker/ADR → cross-links for rationale + enforcement together
   - section → `Related markers` to jump from prose to contract
6. **Cite** — answer with the node path(s) and each node's `resource:` source.

Stop expanding once the question is answered. Prefer 2–4 precise node reads over a bulk dump.

## Operations

### `/dca-knowledge ask <question>`
Default. Route → locate → read → expand → answer, grounded + cited.
> "Why must aggregate roots not reference other aggregate roots by type?"
> → reads the tactical rule + its `Applies to markers` + the linked ADR/section, answers with all three cited.

### `/dca-knowledge explain <concept>`
Concept walkthrough from the **book/guide** body (the teaching text), then anchor to the
concrete `marker`/`rule` nodes that realize it.
> "explain the use case pattern" → relevant section(s) + `/marker/port-in/usecase.md` + its governing rules.

### `/dca-knowledge rules-for <marker|concept>`
List the `Rule` nodes governing a marker (follow `Governed by`), with each rule's
`status` and `enforced_by` test, plus the source `resource:`.
> "rules-for Repository" → all rules whose `Applies to markers` includes `/marker/port-out/repository.md`.

### `/dca-knowledge why <ADR-id | decision>`
Pull the `ADR` node: its `pattern` (the decision), the markers it `Applies to`, and the
rules that `Enforced by` it. Surfaces decision + consequence + enforcement as one answer.

### `/dca-knowledge trace <node>`
Graph dump for one node: all inbound/outbound typed edges (marker ↔ rule ↔ ADR ↔ section).
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
   `rule/` node whose `constraint:` is the one-line precondition (no need to parse the Groovy).
5. **Verify** — run the rule's `resource:` test suite (`./gradlew test-architecture`).

If no recipe covers the task, build from the relevant `marker/` (+ its `Governed by` rules)
and offer to `save` a new `recipe/` so the next build is covered.

### `/dca-knowledge save [note|decision|pitfall|recipe|template] <title>`
**Compound** — promote a query answer (this turn's, or one just given) into a permanent
**extensible-zone** node so the wiki grows instead of re-deriving. Pick the type:
- `note` — a synthesis worth keeping ("domain vs integration events in an outbox")
- `decision` — a design-fork guide ("sync vs async event delivery")
- `pitfall` — an anti-pattern + the rule/ADR that forbids it
- `recipe` — an ordered task playbook · `template` — a domain-free code skeleton

Write `bundle/<type>/<slug>.md` (or the resolved catalog's extensible zone) with
frontmatter `type:` + `title:` + `tags:`, a body that **synthesizes** (don't paste the
chat), and bundle-relative links into the generated skeleton (markers/rules/ADRs/sections)
**and** to sibling extensible nodes. Then regenerate so it's catalogued:
`cd dca-knowledge-catalog && PYTHONPATH=src python3 -m dca_catalog.generate`. The node
survives future regenerations (extensible zone is preserved).

> **When to offer it:** after any `ask`/`explain` that took real graph traversal or
> resolved a non-obvious question, offer to `save` it. That is the Query→page loop — the
> catalog compounds. Don't save trivial lookups (a single rule/marker already covers them).

## Citation format

Every substantive claim ends with its provenance:

```
<claim>.
  — [Rule] /rule/tactical/aggregate-roots-must-not-have-fields-with-other-aggregate-root-types.md
    source: ai-architecture-sample/src/test-architecture/.../TacticalDDDArchUnitTest.groovy (status: enforced)
```

For "show me the real code", surface the `resource:` path so the user (or another tool)
opens the live source — the bundle is the index, `resource:` is the ground truth.

## Token discipline

- Lead with `index.md` files (small) before node bodies.
- Filter on frontmatter (`type`/`tags`/`status`) before reading bodies.
- Sections are atomic — read the one section, not the whole chapter.
- One guide node (`guide/architecture-reference-guide/custom-annotations-placement.md`) is
  large (~986 lines); read it only when directly on-topic, and quote the relevant subsection.
- For broad/fan-out questions across many nodes, delegate to an `Explore` agent over the
  bundle dir and keep only its conclusion in main context.

## Keeping the catalog fresh

The bundle is a **generated, derived artifact** — never hand-edit it, and treat a stale
bundle as a correctness risk. If an answer looks out of date versus the reference
implementation, the source changed but the bundle wasn't regenerated:

```bash
cd dca-knowledge-catalog && PYTHONPATH=src python3 -m dca_catalog.generate && PYTHONPATH=src python3 -m pytest tests/
```

(See `dca-knowledge-catalog/CLAUDE.md`.) When citing, the `resource:` is the source of
truth; if it diverges from the node body, flag the divergence and recommend a regenerate.

Health: `python3 -m dca_catalog.lint` mechanically flags broken links, stale `resource:`
pointers, and unanchored/orphan authored nodes. Run it after saving a `note/`/`recipe/`/etc
to confirm the new node is wired into the graph (no `unanchored-authored`/`orphan`/`broken-link`).

## Relationship to other skills

| Skill | How it pairs |
|---|---|
| `/dca-discipline`, `/dca-review` | They *apply* the rules while editing/reviewing; this skill *explains and cites* the rule + its rationale (ADR) on demand. |
| `/dca-bootstrap` | Bootstrap installs the markers/ArchUnit suite; this skill answers "what does each installed rule mean and why". |
| `/dca-scaffold` | Scaffold generates structure; ask this skill which marker/pattern a new use case should follow, with citation. |
| `/adr` | New decisions are recorded as ADRs in the sample; after regenerating the catalog they become queryable `why` answers here. |
| `/context-map`, `/ubiquitous-language` | Strategic/naming views of the live code; this skill is the canonical-knowledge view of the documented patterns. |

## What this skill does NOT do

- **Doesn't edit the generated zone.** `book/ guide/ marker/ rule/ adr/ process/` are
  derived from the sources (see the generator in `dca-knowledge-catalog/`) — the only
  writes this skill performs are `save` operations into the authored **extensible zone**
  (`recipe/ decision/ pitfall/ template/ note/`).
- **Doesn't answer from memory.** No catalog node = no grounded answer. It says so rather
  than guessing.
- **Doesn't replace `/dca-review`.** It explains rules; it doesn't audit your code against them.
- **Doesn't fetch remote catalogs.** It reads a local bundle (in-repo or vendored); pointing
  at a remote copy is the user's setup step.
