---
id: STAGE-PLAN-4
part: told
why: a plan invented an endpoint no criterion asked for, bringing an authorisation decision nobody reviewed
stages:
- plan
section: Do
order: 4
---

# STAGE-PLAN-4

4. **Check the story's actor can already reach the behaviour** — the criteria name someone (customer, operator,
   administrator) and a way in (page, endpoint, message, command line). No such way in today → do **not** invent one:
   a new surface is a product decision (and, with a guard, an authorisation one). Write `## needs-human` naming the
   surface the criteria need, and stop. Added silently, it becomes an endpoint nobody specified with an access rule
   nobody reviewed. Exception: criteria that name the surface themselves — then it is a change like any other.
