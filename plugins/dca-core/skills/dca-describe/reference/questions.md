# dca-describe — the questions

One entry per heading of the three templates, in the order they are asked. The skill looks each
answer up first and asks **only the open ones — all at once, in this order, word for word**. The
answer goes under the heading the entry names, in the person's words; an entry whose answer is
already there is not asked again.

Each entry has the same fields:

- **look up** — where the answer already is; found there, the question is not asked;
- **asked** — when the question is put at all;
- **question** — the text, word for word;
- **options** — the choices offered, where there are some; the person may always answer otherwise;
- **default** — offered as the first choice where a convention exists; `—` where there is none;
- **answer goes to** — the file and heading.

A question that depends on an answer still open in the same pass is asked with its condition in front
("Where the product has pages: …"); its answer is dropped where the condition turns out false.

"Open" means the heading is missing, empty, or holds only the template's comment or a `{{…}}`
placeholder. A heading drafted — from existing code, or from what the person said with the call — counts
as open until the person confirms it: its question is asked word for word all the same, with the draft
offered as the first option. The
paths are the defaults; the `dca-describe` section of `AGENTS.md` names the places a project uses.

## Product — `project/product.md`

### DESC-WHAT
- look up: `## What and for whom`
- asked: when open
- question: What is built, and for whom? Name the product in two or three sentences and its actors — who uses it, and for what.
- options: —
- default: —
- answer goes to: `project/product.md → ## What and for whom`

### DESC-SURFACES
- look up: `## Surfaces`
- asked: when open
- question: How does each actor reach the product — pages, notifications, an HTTP API, a command line, a tool — and on which devices?
- options: —
- default: —
- answer goes to: `project/product.md → ## Surfaces`

### DESC-HOW
- look up: `## How it works`
- asked: when open
- question: How does the main flow go, where does state live (the client, the server, both), and what is persisted?
- options: —
- default: —
- answer goes to: `project/product.md → ## How it works`

### DESC-LOOK
- look up: `## Look and feel`
- asked: when open
- question: How should it look — style direction, language, accessibility level, a design system where there is one?
- options: —
- default: —
- answer goes to: `project/product.md → ## Look and feel`

### DESC-SIZES
- look up: the size table under `## Look and feel`
- asked: when open and DESC-SURFACES names pages or is itself open
- question: Where the product has pages: which page sizes is it designed for? The defaults are s up to 480 px (phones upright), m up to 768 px (small tablets, phones on their side), l up to 1180 px (tablets) and xl above (laptops and desktops).
- options: the defaults · other limits
- default: the defaults
- answer goes to: `project/product.md → ## Look and feel`, the size table

### DESC-QUALITIES
- look up: `## Qualities`
- asked: when open
- question: Which qualities does the product need — security and authorisation, privacy, performance, availability — as this product needs them?
- options: —
- default: —
- answer goes to: `project/product.md → ## Qualities`

### DESC-NOT
- look up: `## Not part of the product`
- asked: when open
- question: What will the product not do?
- options: —
- default: —
- answer goes to: `project/product.md → ## Not part of the product`

## Technical decisions — `project/tech.md`

### DESC-STACK
- look up: `## Stack`
- asked: when open
- question: Which language, framework and build tool — and why, where it is not obvious?
- options: Java with Spring Boot and Gradle · Java with Spring Boot and Maven · C# with ASP.NET Core
- default: —
- answer goes to: `project/tech.md → ## Stack`

### DESC-FRONTEND
- look up: `## Frontend approach`
- asked: when open
- question: Server-rendered pages, a client application, or no frontend — and what does that exclude?
- options: server-rendered pages, no client framework · a client application · no frontend
- default: —
- answer goes to: `project/tech.md → ## Frontend approach`

### DESC-PERSISTENCE
- look up: `## Persistence`
- asked: when open
- question: Where is state kept — one database, files, in memory until a later story — and what does the product not use?
- options: in memory until a later story · one relational database · files
- default: —
- answer goes to: `project/tech.md → ## Persistence`

### DESC-RUNTIME
- look up: `## Runtime`
- asked: when open
- question: Where and how does it run — a container, a platform, a desktop, a device — and what does it need there?
- options: —
- default: —
- answer goes to: `project/tech.md → ## Runtime`

### DESC-INTEGRATIONS
- look up: `## Integrations`
- asked: when open
- question: Which external systems does the product talk to, in which direction, what is sent and received — each field with its type — and what counts as unavailable?
- options: none
- default: —
- answer goes to: `project/tech.md → ## Integrations`

### DESC-VERSIONS
- look up: `## Version policy`
- asked: when open
- question: How are dependency versions chosen and kept current?
- options: the generator's current defaults, kept current by hand · pinned, raised deliberately · the latest release
- default: the generator's current defaults, kept current by hand
- answer goes to: `project/tech.md → ## Version policy`

## Designed domain — `project/domain.md`

### DESC-CONTEXTS
- look up: the `## Bounded contexts` table
- asked: when open
- question: Which bounded contexts does the product have — each with its responsibility and its subdomain type (core, supporting, generic)?
- options: one context for now
- default: —
- answer goes to: `project/domain.md → ## Bounded contexts`

### DESC-RELATIONSHIPS
- look up: the `## Relationships` table
- asked: when open and DESC-CONTEXTS names more than one context or is itself open
- question: Where there is more than one context: how do the contexts depend on each other — which is upstream, which downstream, with which pattern, which translation and for which reason?
- options: —
- default: —
- answer goes to: `project/domain.md → ## Relationships`
