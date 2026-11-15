---
name: dca-describe
description: Writes the project description with the person who decides what is built — the product (what, for whom, surfaces, how it works, how it looks, qualities, what it is not), the technical decisions (stack, how expected refusals reach callers, frontend approach, persistence, runtime, integrations, version policy) and the designed domain (bounded contexts, subdomain types, relationships and why, the glossary of terms and operations with their code words) — under product/, and the AGENTS.md line that makes every implementation read them first. Use before the first line of code or the first story, when a project has code but no description, when a description is incomplete, on "/dca-describe", or on "/dca-describe <change>" to change one statement in the person's words. Never invents an answer; writes no code and no story.
---

# Describe the project

Writes `product/overview.md`, `product/tech.md`, `product/domain.md` (or where `dca.profile.yaml` puts them), the
`AGENTS.md` section naming them, and a context's own glossary `product/spec/<context>/glossary.md` through
`ubiquitous-language`. Nothing else under `spec/` (`scenarios.md`, `journeys.md` change only by delivery). No
story, plan or code.

The files hold intent, written before the code. What exists and why (architecture docs, decision records,
generated maps) goes to `docs/`. Not yet built → `product/`; the code could show it → `docs/`.

## Do

1. **Look before you ask.** Places from `dca.profile.yaml` at the root, flat `key: value`, every key optional:
   `root:` (default `product/`); `overview:` (`<root>/overview.md`), `tech:` (`<root>/tech.md`), `domain:`
   (`<root>/domain.md`), `spec:` (`<root>/spec`, the glossaries' folder). Missing file or key → default.
   - Person wants another place → write `root:` or the one key into `dca.profile.yaml`, keep its other lines.
   - An `AGENTS.md` section of this skill naming a place the file lacks → write it once into
     `dca.profile.yaml`: `- product:` as `overview:`, `- tech:` as `tech:`, `- domain:` as `domain:`; a default
     place needs no line.
   - Read what exists. A complete file: check it, do not rewrite it unless the person wants a change.
2. **One question per heading, from the catalogue.** Headings are fixed by `templates/` (product's six, tech's
   six, domain's contexts, relationships, one glossary table per context); `reference/questions.md` holds each
   heading's question word for word, with options and default. Look every heading up; ask **only the open ones —
   all at once, in catalogue order, word for word**; write answers in the person's words.
   - DESC-REFUSALS offers both styles as equals, never recommends one.
   - **Never invent an answer**: an invented look gets built, and a placeholder passes a heading-count check.
   - Nothing to decide → one honest line.
   - Called with answers given (`dca-new` asks the catalogue in its one pass) → write those, ask only the rest.
3. **Decisions only, no design.** "The client keeps the draft; the server stores what is submitted" → product;
   "server-rendered pages, no client framework" → tech. Endpoint, package, class → neither.
4. **Existing code: draft from it, ask for the rest.** Draft what code tells — surfaces, how it works, look and
   feel, stack, each context's refusal style (thrown or returned; both shown → draft as a question), persistence,
   runtime, integrations, contexts and dependencies — each marked as read from the code. Ask what code cannot
   tell: purpose and audience, qualities, what it is not, version policy, subdomain types, reasons. The person
   confirms each file before it counts.
5. **The domain through the map's craft.** Write `product/domain.md` through `context-map` where installed
   (relationship patterns, subdomain types, its questions); else from `templates/domain.md.tmpl` with the same
   questions. One context → the designed map is optional; say so, never invent a second.
   - Glossary: terms **and operations**, each with the code's word, before the code exists. Ask events first
     (DESC-GLOSSARY). An operation whose word could name more than one effect (create vs add, delete vs
     cancel) is asked which, never translated.
   - Before asking, where the session can search: per context, look up how its field names its operations
     (published standard, widely used systems' vocabulary, look-alikes they keep apart; `ubiquitous-language`
     describes the lookup); offer findings with source as DESC-GLOSSARY drafts. A draft is open until confirmed.
   - **Per context, one place per entry.** Each designed context: a `### <context>` section under `## Glossary`.
     A context with code and its own `product/spec/<context>/glossary.md` (`<context>` lowercase, words joined
     by `-`) gets its entries there (through `ubiquitous-language` where installed); its section is one line
     naming the file. Code created later → the section moves into that file (`dca-new context` does it): moved,
     not copied. A glossary still beside domain code is migrated: `factory.sh update` with a delivery pipeline,
     else `git mv`.
   - Shared-kernel words → `product/spec/shared-kernel/glossary.md`, never a context's file; a context names a
     shared term where used, never redefines it.
6. **One designed map, never two.** An earlier designed map (`docs/context-map.md` or another name) is moved:
   propose `git mv docs/context-map.md product/domain.md`, do it on confirmation. A map generated from code
   (`docs/architecture/context-map.md`) is not designed and stays.
7. **Write the instruction line.** Add or replace this section in `AGENTS.md`, places resolved as in step 1:

   ```markdown
   <!-- dca-describe: start -->
   ## Project description

   What is to be built is described in three files. Read them before any implementation — in a
   delivery pipeline or by hand — and treat a contradiction between them and a change as a finding,
   not as something to fix in the code:

   - product: `product/overview.md` — what is built, for whom, surfaces, how it works, how it looks,
     qualities, what it is not
   - tech: `product/tech.md` — stack, frontend approach, persistence, runtime, integrations,
     version policy
   - domain: `product/domain.md` — the designed bounded contexts, their subdomain types and
     relationships, and the glossary of their terms and operations until a context has its own
     (`product/spec/<context>/glossary.md`); the map generated from the code shows what was built
   <!-- dca-describe: end -->
   ```

   Pointer, not source: tools read places from `dca.profile.yaml`; a place changes there first, then here. Keep
   the lines' form. Only this block is yours. A `CLAUDE.md` without `@AGENTS.md` → say Claude Code will not
   read the section.
8. **Say what comes next.** No code → `/dca-new`. Code → nothing, or the first epic where stories run through
   a pipeline.

## Changing the description later

`/dca-describe <change>`: one statement in the person's words ("the shop also sells gift cards", "we move from H2
to PostgreSQL"), or a released change from a discovery report as
`<overview.md | tech.md | domain.md> — <section>: <change>`. Find its heading, show the line as is and as it
would read, write on yes; ask only what it leaves open; name other headings it touches (new persistence →
`## Runtime`). No argument → look up every heading, ask the open ones. Exception: a capability's line under
`## Stack` is written by `dca-add`.

A story needing a surface not listed, a persistence the tech excludes, or a context the map lacks is a question
about the description: change it first, through this skill with the person; the story follows. No build stage
edits these files.

## Without a person in the session

A delivery pipeline may run this skill for a written request; its prompt says so, names the person and where a
question goes. The request is the yes: write the change as given, without showing it. Never guess or ask in chat
what it leaves open: write one decision record where the prompt names — question, options `- a: …` with what
each means for the description, a recommendation, the front matter the prompt asks — and end, description
unchanged where the answer is missing. Rerun with the answer, write what it settles. Never start a pipeline or
commit.

## Do not

- Write a story, epic, plan or code.
- Fill a heading the person did not answer, or keep an answer taken back.
- Create a second designed map beside the one the instructions name.
- Read a delivery pipeline's configuration for the places; the `AGENTS.md` section is the source, and a
  pipeline reads it from there.
