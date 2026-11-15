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

3. **Take the decisions from the project description.** `## Surfaces`, `## How it works`, `## Look and feel` (where
   state lives, which surfaces, how a page looks, the named sizes `s`/`m`/`l`/`xl`) and `product/tech.md`'s
   `## Persistence`, `## Frontend approach`, `## Integrations` (how an element is built). A criterion names a size,
   never a pixel; a size the table lacks is a question. Never plan what `tech.md` excludes (a second persistence, a
   client framework on server-rendered pages, an unlisted integration). A question they answer is no question for
   the human; one they leave open, or a story contradicting them, goes to `## needs-human`. No description → say so,
   plan from the story.
