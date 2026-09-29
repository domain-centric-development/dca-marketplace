---
name: dca-knowledge
description: |
  Answers Domain-Centric Architecture questions grounded in the generated OKF
  knowledge catalog (the `catalog/` folder beside this skill) — the full implementation-guide
  text anchored to marker contracts and ArchUnit rules as one cross-linked graph.
  Loads `index.md`, traverses typed links (governed-by / applies-to / discussed-in),
  and cites the node path for every claim. Use when the user
  asks "what does DCA say about X", "which rule governs this marker",
  "explain <DCA concept>", "/dca-knowledge", or wants an answer
  grounded in the canonical catalog rather than the model's own recollection.
disable-model-invocation: false
---

# /dca-knowledge — Grounded Q&A over the OKF catalog

The OKF bundle is the **canonical, machine-readable DCA knowledge base**: several hundred atomic
markdown nodes, each with typed frontmatter and bundle-relative cross-links forming a
graph. Two zones:

- **Generated** (implementation-guide docs and sections, marker contracts,
  architecture rules, process and API references) — derived from the sources.
- **Extensible** (`recipe/`, `decision/`, `pitfall/`, `template/`, `note/`) — authored
  by a human or an LLM, preserved across regeneration. May be empty until populated.

This skill answers DCA questions **from that bundle** — not from the model's own
memory — and **cites** the node path for every claim. The bundle is
self-contained: nodes carry the marker signature, the rule expression and the guide
text themselves, so a citation needs no path outside the catalog.

> **Grounding rule (non-negotiable):** Answer only from nodes you actually read in the
> bundle. If the bundle doesn't cover it, say so — don't fill the gap from general DDD
> knowledge. Mark any such supplement explicitly as *outside the catalog*.

## Locating the bundle

Resolve the catalog path in this order; stop at the first that exists:

1. `catalog_path` in the conventions file — the one the `AGENTS.md` line ``- conventions: `<path>` `` names,
   `.agents/dca/conventions.md` by default (`.claude/dca/conventions.md` in older projects). An explicit
   override wins.
2. **The `catalog/` folder beside this skill file** — the copy that ships with the skill and travels with it:
   `${CLAUDE_PLUGIN_ROOT}/skills/dca-knowledge/catalog/` for a plugin install, `.claude/skills/dca-knowledge/catalog/`
   (or `.codex/skills/…`, `.opencode/skills/…`) where the skill was copied or linked into the project. This is
   the path in every consuming project; do not search for a `bundle/` folder, there is none here.
3. `.agents/dca/catalog/`, then `.claude/dca/catalog/` — a copy the project vendored by hand.
4. `dca-knowledge-catalog/bundle/` beside the repository root — only in the checkout that generates the
   catalog; it is fresher than a shipped copy and is preferred where both exist.

> **No book, no ADRs.** The catalog is built from the implementation guide plus the
> reference implementation's marker interfaces and ArchUnit rules. The DCA book is not a
> source (it is not public), and neither are the sample's ADRs: an ADR records a decision
> *one* project made, so citing "ADR-030" would point at a file the user does not have.
> Answer from the `guide/` sections and the skeleton — and if the question is really about
> a decision the catalog does not carry, say so rather than reconstructing it.

If none is found, say so: the catalog is not present. It ships with this skill; a project that keeps its
own copy vendors one into `.agents/dca/catalog/` and sets `catalog_path`.

## Node types & typed edges

The bundle is a graph. Knowing the node types and edge labels lets you traverse it
without reading everything.

| Node `type` | Lives in | Carries | Key outgoing edges |
|---|---|---|---|
| `Guide` | `guide/` | preamble + `## Sections` index | → child Sections |
| `Section` | `guide/<g>/` | **full verbatim text** | `## Related mentions (heuristic)` |
| `Marker` | `marker/<cat>/` | interface signature, `extends`, methods | `## Extends`, `## Governed by` (rules), `## Related mentions in guides (heuristic)` (sections) |
| `Rule` | `rule/<cat>/` | Java/ArchUnit or C#/ArchUnitNET evidence, `enforced_by`, `status` | `## Applies to markers` |
| `Process` | `process/` | how-to (e.g. writing an ADR) | → any |
| `Reference` | `reference/` | `DcaLayout` (settings, defaults, patterns, framework names) and `DcaArchitecture` (how contexts and module roots are discovered, every query the rules select through) — Java and .NET | ← every rule ("Configured by") |
| `Recipe`/`Decision`/`Pitfall`/`Template`/`Note` | `recipe/` … `note/` (**extensible zone**) | authored playbooks, design-fork guides, anti-patterns, code skeletons, saved query answers | links into the skeleton |

**Link format:** bundle-relative, leading `/`, `.md` suffix — e.g. `/marker/port-in/usecase.md`.
Resolve against the bundle root, not the current file.

**Frontmatter as filter:** `type`, `tags`, `category`, `status` (rules:
`enforced`/`informational`/`disabled`). Use these to narrow before reading bodies.

**Reserved files** (`index.md`, `log.md`) are navigation, not knowledge — read them to
route, don't cite them as answers.

## Traversal protocol

Don't grep-and-dump. Walk the graph like a researcher:

1. **Enter** — read `bundle/index.md` (node-type counts + links to category indices).
2. **Route** — pick the category whose `type` fits the question:
   - "what/why/how concept" → `guide/` section
   - "what's the contract / interface" → `marker/`
   - "what's enforced / is this allowed" → `rule/`
   - "why this rule exists" → the `rule/` node's `rule:` rationale, then the guide
     section that discusses the marker it applies to
3. **Locate** — read the category `index.md`, pick candidate node(s) by title/slug.
4. **Read** — read the node body + frontmatter.
5. **Expand** — follow typed edges that the question needs:
   - marker → `Governed by` to get its enforced rules
   - marker → `Discussed in` for the guide sections that explain it
   - section → `Related markers` to jump from prose to contract
6. **Cite** — answer with the node path(s) you read.

Stop expanding once the question is answered. Prefer 2–4 precise node reads over a bulk dump.

## Operations

| Form | Does |
|---|---|
| `/dca-knowledge ask <question>` (default) | route → locate → read → expand → answer, grounded and cited |
| `explain <concept>` | the guide's teaching text first, then the marker and rule nodes that realize it |
| `rules-for <marker>` | the rules governing a marker, with `status` and `enforced_by` |
| `why <rule>` | the rule's rationale, the markers it applies to, the guide sections that discuss them |
| `trace <node>` · `find <text>` | one node's edges · a ranked locator over titles and tags |
| `build <thing>` | the build loop: recipe → decision → template → the recipe's rules → the architecture suite |
| `save <type> <title>` | propose a new authored node to the catalog's owner — never written into the shipped copy |

Each operation in full, with examples, the build loop's steps and the `save` workflow: `reference/operations.md`.

## Citation format

Every substantive claim ends with its provenance:

```
<claim>.
  — [Rule] /rule/tactical/dca-tac-003.md
    enforced_by: TacticalPatternRules#DCA-TAC-003 (status: enforced)
```

For "show me the real code", quote the node itself: a `rule` node carries its ArchUnit
expression and `enforced_by` test name, a `marker` node its signature. Then point at the
matching type in *the user's own* project — never at another repository.

## When in doubt

- Lead with `index.md` files (small) before node bodies; filter on frontmatter before reading bodies;
  read the one section, not the chapter. More in `reference/operations.md` (token discipline).
- The shipped copy is read-only and may be older than the libraries the project uses: cite the node body,
  say so when it looks out of date, never hand-edit it (`reference/operations.md`, "When the catalog looks stale").
- It explains rules; it does not audit code against them — that is `/dca-audit`.
