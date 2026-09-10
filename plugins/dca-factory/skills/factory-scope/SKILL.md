---
name: factory-scope
description: Handles the one question a delivery run may not answer for itself — a story that would need a new bounded context, a new relationship between contexts, or a surface its actor does not have yet. Use when a plan stopped with needs-human for one of those, when the backlog skill refused a story for a context that is not on the map, or on "/factory-scope". Produces a decision and a map, never code.
---

# Answer one scoping question

Input: the question — from a plan's `## needs-human`, from a story the backlog skill would not
write, or from a human — plus the project's context map, its glossaries and its decision records.
Output: a decision recorded where the project keeps such decisions, and the context map brought in
line with it. You write no story, no plan, no test and no production code.

A scoping question is exactly one of these, and nothing else belongs here:

- the behaviour needs a **bounded context the map does not have**;
- it needs a **relationship between two contexts** that does not exist yet;
- its actor needs a **surface** — a page, an endpoint, a consumer — that the context does not have,
  and with it a decision about who may use it.

## Do

1. **Restate the question so it can be answered.** Name the behaviour, the actor and the contexts
   already involved. A question you cannot state without inventing a requirement is not ready:
   ask the human instead of resolving it in prose.
2. **Try the map you have first.** A new context is the expensive answer, and most questions do
   not need it: the behaviour may belong to a context that already owns the language, or be a
   second use case in one. Say why the existing contexts do *not* fit — different lifecycle,
   different language for the same word, a different team, an invariant that cannot span the
   boundary — before proposing a new one. "It feels separate" is not a reason.
3. **Name the subdomain type.** Core, supporting or generic decides how much pattern the context
   earns: a core subdomain gets the full tactical set, a supporting one may stay simple, a generic
   one is bought rather than built. This choice, not the context's existence, is what shapes the
   work that follows.
4. **Name the relationship in the project's own vocabulary**, with a direction and a reason:
   customer/supplier, partnership, shared kernel, conformist, anti-corruption layer, open host
   service, published language, separate ways. Say which side owns the contract and what happens
   to the downstream when the upstream changes. Where the project ships a context-map skill, use
   it rather than drawing a map by hand.
5. **For a surface, decide two things and separate them.** What the surface is (a page, an
   endpoint, a consumer, a tool) and **who may use it**. The second is an authorisation decision:
   say where the check belongs by the project's own rule, and never let it arrive as a side effect
   of adding the surface. A guard nobody decided is a guard no test holds.
6. **Record the decision in a file.** An answer that exists only in a reply is lost the moment the
   session ends, and the next plan asks the same question — the whole pipeline keeps its state in
   files for that reason. Write it where the project keeps decisions: its architecture decision
   records (use its ADR skill if it ships one), or the document its own instructions name. Where
   the project has no such place, create `docs/decisions/<nnn>-<slug>.md` and say that you did, so
   the project can name that place from now on. The record carries the question, the options
   weighed, the answer and the consequence — including what becomes possible and what becomes
   harder. A scoping answer with no file is not finished work.
7. **Update the context map in the same step — once the decision is actually taken.** A decision
   that is not on the map is a decision the next plan cannot read: the plan gate checks the story's
   context against the map, so an unrecorded answer blocks the very story this question came from.
   Where the answer still depends on a question only the domain contact can settle, the record
   carries the recommendation and the open question, and the map stays as it is. Say that, so the
   unchanged map reads as a state and not as an oversight — a context on the map that nobody has
   agreed to is worse than a question still open.
8. **Hand back what changes for the story.** Say plainly whether the story can now be written, what
   its `context` must be, and which of its criteria the decision moved or split. Do not write the
   story — that is the backlog skill's, with the human's words.

## When the answer is "not now"

A scoping question may be answered by declining it: the behaviour waits, the story is dropped, or
a smaller piece of it fits the map as it stands. That is a real answer and it gets recorded like
any other — an undocumented "we decided against it" comes back as the same question in a month.

## Do not

- Do not add a context to the map without the decision record that explains it. A map is the
  summary of decisions, never the place they are taken.
- Do not answer a modelling question that is not about scope. Which aggregate holds an invariant,
  whether a rule is a specification, how a result is shaped — those belong to the plan and the
  build, and the project's knowledge catalog answers them.
- Do not introduce a context to hold code nobody owns. A context is a language boundary with a
  team and an owner behind it; a package for leftovers is neither.
