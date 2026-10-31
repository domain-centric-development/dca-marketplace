---
id: STAGE-PLAN-4
part: told
stages:
- plan
section: Do
order: 4
---

# STAGE-PLAN-4

4. **Check that the story's actor can already reach the behaviour.** The criteria name someone —
   a customer, an operator, an administrator — and a way in: a page, an endpoint, a message, a
   command line. If the context has no such way in today, the plan does **not** invent one. A new
   surface for an actor is a decision about the product and, where the surface needs a guard, about
   authorisation: write the plan file with a `## needs-human` section naming which surface the
   criteria would need and stop. Adding it silently is how one story becomes an endpoint nobody
   specified, and a rule about who may call it that nobody reviewed.
   The exception is a story whose criteria name the surface themselves — then it is specified, and
   it belongs in the change list like any other element.
