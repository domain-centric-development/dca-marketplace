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

The catalog: atomic markdown nodes with typed front matter and bundle-relative links. Zones: **generated** (guide
docs and sections, markers, rules, process, references) and **extensible** (`recipe/`, `decision/`, `pitfall/`,
`template/`, `note/` — authored, kept across regeneration, may be empty). Self-contained: a citation needs no path
outside it.

> **Grounding rule (non-negotiable):** answer only from nodes you read. Not covered → say so; never fill from
> general DDD knowledge. Mark any supplement *outside the catalog*.

## Locating the bundle

First that exists wins:

1. `catalog_path:` in `dca.profile.yaml` at the project root (the `AGENTS.md` line
   ``- configuration: `dca.profile.yaml` `` points at it).
2. **`catalog/` beside this skill file** — `${CLAUDE_PLUGIN_ROOT}/skills/dca-knowledge/catalog/`, or
   `.claude/skills/dca-knowledge/catalog/` (`.codex/skills/…`, `.opencode/skills/…`) when copied or linked. The
   path in every consuming project; there is no `bundle/` folder here, do not search for one.
3. `.agents/dca/catalog/`, then `.claude/dca/catalog/` — vendored by hand.
4. `dca-knowledge-catalog/bundle/` beside the repository root — only in the generating checkout; fresher, preferred.

None → say the catalog is not present; it ships with this skill, a project keeping its own copy vendors it into
`.agents/dca/catalog/` and sets `catalog_path`.

**No book, no ADRs.** Sources are the guide plus the markers and rules. Never cite the DCA book (not public) or
a sample ADR ("ADR-030" is a file the user lacks). A decision the catalog does not carry → say so, do not
reconstruct it.

## Node types & typed edges

| Node `type` | Lives in | Carries | Key outgoing edges |
|---|---|---|---|
| `Guide` | `guide/` | preamble + `## Sections` index | → child Sections |
| `Section` | `guide/<g>/` | **full verbatim text** | `## Related mentions (heuristic)` |
| `Marker` | `marker/<cat>/` | interface signature, `extends`, methods | `## Extends`, `## Governed by` (rules), `## Related mentions in guides (heuristic)` (sections) |
| `Rule` | `rule/<cat>/` | Java/ArchUnit or C#/ArchUnitNET evidence, `enforced_by`, `status`, `maturity` | `## Applies to markers` |
| `Process` | `process/` | how-to (e.g. writing an ADR) | → any |
| `Reference` | `reference/` | `DcaLayout` (settings, defaults, patterns, framework names) and `DcaArchitecture` (context and module-root discovery, every query the rules select through) — Java and .NET | ← every rule ("Configured by") |
| `Recipe`/`Decision`/`Pitfall`/`Template`/`Note` | `recipe/` … `note/` (**extensible zone**) | playbooks, design-fork guides, anti-patterns, code skeletons, saved answers | links into the skeleton |

- **Links:** bundle-relative, leading `/`, `.md` — `/marker/port-in/usecase.md`. Resolve against the catalog root.
- **Front matter filters:** `type`, `tags`, `category`, `status` (rules: `enforced`/`informational`/`disabled`),
  `maturity` (rules: `released`/`experimental`). Narrow before reading bodies.
- **Experimental binds only on opt-in.** Before "enforced" / "not allowed" from a `maturity: experimental` node,
  check `withExperimental()` / `WithExperimental()` in the architecture test or `dca.rules.experimental = true` in
  `dca-archunit.properties`. Without it: cite as information, say experimental, never a reason to change code.
- **Reserved files** `index.md`, `log.md`: route with them, never cite them.
- A large rule node keeps selection and check; its ArchUnit code (Java, C#, helpers) is in evidence slices linked
  at its end.

## Traversal protocol

No grep-and-dump.

1. **Enter** — `index.md` at the catalog root.
2. **Route** — concept what/why/how → `guide/`; contract/interface → `marker/`; enforced/allowed → `rule/`; why a
   rule exists → the rule's `rule:` rationale, then the guide section on the marker it applies to.
3. **Locate** — the category `index.md`; pick nodes by title/slug.
4. **Read** — body + front matter.
5. **Expand** — only edges the question needs: marker → `Governed by` (rules); marker → guide mentions
   (sections); section → related mentions (markers).
6. **Cite** — the node paths read.

Stop once answered; 2–4 precise reads over a bulk dump.

## Operations

| Form | Does |
|---|---|
| `/dca-knowledge ask <question>` (default) | route → locate → read → expand → answer, grounded and cited |
| `explain <concept>` | the guide's teaching text first, then the marker and rule nodes that realize it |
| `rules-for <marker>` | the rules governing a marker, with `status`, `maturity` and `enforced_by` |
| `why <rule>` | the rule's rationale, the markers it applies to, the guide sections that discuss them |
| `trace <node>` · `find <text>` | one node's edges · a ranked locator over titles and tags |
| `build <thing>` | the build loop: recipe → decision → template → the recipe's rules → the architecture suite |
| `save <type> <title>` | propose a new authored node to the catalog's owner — never written into the shipped copy |

Read `reference/operations.md` for an operation's detail, the build loop, `save`, token discipline, a stale
catalog, retrieval order.

## Citation format

Every substantive claim ends with its provenance:

```
<claim>.
  — [Rule] /rule/tactical/dca-tac-003.md
    enforced_by: TacticalPatternRules#DCA-TAC-003 (status: enforced)
```

"Show me the real code" → quote the node (rule: ArchUnit expression + `enforced_by`; marker: signature), then point
at the matching type in *the user's own* project, never another repository.

## Review status

Authored node `review:`: `reviewed` → cite as the answer; `draft` (majority) → use, say once it is draft,
never override a generated node; `superseded` → history, follow `superseded_by`; missing → `draft`. Generated nodes (rule,
marker, guide, reference) win every contradiction.

## When in doubt

- Planning a change (naming elements, not writing them) → `digest/index.md` and the digests of the kinds planned;
  cite the recipe node. Full recipe only for a decision the digest leaves open; template code only when writing code.
- `index.md` files before bodies; filter on front matter; one section, not the chapter.
- The shipped copy is read-only and may lag the project's libraries: cite the node body, say when it looks
  stale, never hand-edit (`reference/operations.md`, "When the catalog looks stale").
- Explains rules; auditing code against them is `/dca-audit`.
