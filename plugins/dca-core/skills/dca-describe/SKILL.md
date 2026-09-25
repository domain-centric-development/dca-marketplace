---
name: dca-describe
description: Writes the project description with the person who decides what is built — the product (what, for whom, surfaces, how it works, how it looks, qualities, what it is not), the technical decisions (stack, frontend approach, persistence, runtime, integrations, version policy) and the designed domain (bounded contexts, subdomain types, relationships and why) — under project/, and the AGENTS.md line that makes every implementation read them first. Use before the first line of code or the first story, when a project has code but no description, when a description is incomplete, or on "/dca-describe". Never invents an answer; writes no code and no story.
---

# Describe the project

Input: the person who decides what is built, and — in a project that has code — the code.
Output: `project/product.md`, `project/tech.md`, `project/domain.md`, and a section in `AGENTS.md`
that names them. You write no story, no plan and no code.

The three files hold **intent**: what is to be built, written before the code. What exists and why —
architecture documentation, decision records, generated maps — belongs in `docs/`, after the code.
The rule of thumb: an intention that need not be built yet goes to `project/`; a statement the code
could show goes to `docs/`.

## Do

1. **Look before you ask.** Read `AGENTS.md`: a section between `<!-- dca-describe: start -->` and
   `<!-- dca-describe: end -->` names where the files are; use those places. Read what already
   exists there. A file that is complete stays as it is unless the person wants to change it — you
   check it, you do not rewrite it.
2. **One question per heading, in their words.** The headings are fixed by the templates in
   `templates/` — the product's six, the technical description's six, the domain's two tables. Ask
   for what is missing; never invent an answer. A stage or a person that reads an invented look
   builds it, and a placeholder passes a check that counts headings. A heading with nothing to
   decide gets one honest line.
   - **product** — what is built and for whom; how each actor reaches it (the surfaces, and on
     which devices); how it works — where state lives, what is persisted; how it looks; the
     qualities it needs; what it will not do.
   - **tech** — the stack and why; the frontend approach and what it excludes; the persistence and
     what it excludes; where it runs; the systems it talks to; how versions are chosen.
   - **domain** — the contexts with their responsibility and subdomain type, and the relationships
     with a pattern, the translation and a reason.
3. **Decisions only, no design.** "The client keeps the draft; the server stores what is
   submitted" belongs in the product description; "server-rendered pages, no client framework" in
   the technical one. An endpoint, a package or a class belongs in neither.
4. **Existing code: draft from it, ask for the rest.** Where code exists, draft what the code can
   tell — surfaces, how it works, look and feel, stack, persistence, runtime, integrations, the
   contexts and their dependencies — and mark each draft as read from the code. Ask for what code
   cannot tell: what it is for and for whom, the qualities, what it is not, the version policy, the
   subdomain types and the reasons. The person confirms each file before it counts.
5. **The domain through the map's craft.** Where the `context-map` skill is installed, write
   `project/domain.md` through it: it holds the relationship patterns, the subdomain types and the
   questions to ask when a context or a relationship is added. Otherwise write it from
   `templates/domain.md.tmpl` with the same questions. The designed map is optional where a project
   has one context; say so rather than inventing a second.
6. **One designed map, never two.** A designed map written earlier at `docs/context-map.md` — or
   under another name the project used — is moved, not copied: propose
   `git mv docs/context-map.md project/domain.md` and do it on the person's confirmation. A map
   generated from the code (`docs/architecture/context-map.md` in a DCA project) is not a designed
   map and stays where it is.
7. **Write the instruction line.** Add — or replace — this section in `AGENTS.md`, with the places
   the files actually have:

   ```markdown
   <!-- dca-describe: start -->
   ## Project description

   What is to be built is described in three files. Read them before any implementation — in a
   delivery pipeline or by hand — and treat a contradiction between them and a change as a finding,
   not as something to fix in the code:

   - product: `project/product.md` — what is built, for whom, surfaces, how it works, how it looks,
     qualities, what it is not
   - tech: `project/tech.md` — stack, frontend approach, persistence, runtime, integrations,
     version policy
   - domain: `project/domain.md` — the designed bounded contexts, their subdomain types and
     relationships; the map generated from the code shows what was built
   <!-- dca-describe: end -->
   ```

   The `- product:`, `- tech:` and `- domain:` lines are read by other tools, so keep their form.
   Only this block is yours; the rest of `AGENTS.md` is the project's. Where the project keeps a `CLAUDE.md` without
   `@AGENTS.md`, say that Claude Code does not read the section then.
8. **Say what comes next.** A project without code: the project skeleton (`/dca-new`). A project
   with code: nothing, or the first epic where the project delivers stories through a pipeline.

## Changing the description later

A story that needs a surface the product description does not list, a second persistence the
technical description excludes, or a context the designed map does not carry is a question about
the description, not about the story. The answer changes the description first — through this
skill, with the person — and the story follows it. No build stage edits these files: they record
decisions people took, not facts a stage can check against code.

## Do not

- Do not write a story, an epic, a plan or code.
- Do not fill a heading the person did not answer, and do not keep an answer they took back.
- Do not create a second designed map beside the one the instructions name.
- Do not read a delivery pipeline's configuration for the places; the `AGENTS.md` section is the
  source, and a pipeline reads it from there.
