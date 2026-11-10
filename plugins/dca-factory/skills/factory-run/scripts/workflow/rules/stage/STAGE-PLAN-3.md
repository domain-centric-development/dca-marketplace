---
id: STAGE-PLAN-3
part: told
why: plans brought in elements the technical description excludes, such as a second persistence or a client framework
stages:
- plan
section: Do
order: 3
---

# STAGE-PLAN-3

3. **Take the decisions from the project description.** The product description's `## Surfaces`,
   `## How it works` and `## Look and feel` answer where state lives, which surfaces the product
   has and how a page looks — including the named sizes a page is designed for (`s`, `m`, `l`, `xl`,
   from the table under `## Look and feel`); a criterion names a size, never a pixel value, and one
   naming a size the table lacks is a question; the technical description's `## Persistence`, `## Frontend approach`
   and `## Integrations` answer how an element you name is built. Plan within them: an element that
   contradicts `product/tech.md` — a second persistence, a client framework on server-rendered
   pages, an integration it does not list — is not planned. A question they already answer is not
   a question for the human; one they leave open, or a story that contradicts them, is — through
   `## needs-human`, like any other. Without a description, say so in the plan and plan from the
   story alone.
