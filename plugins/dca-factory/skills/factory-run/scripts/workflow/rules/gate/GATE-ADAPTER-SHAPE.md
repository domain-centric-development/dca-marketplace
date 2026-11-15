---
id: GATE-ADAPTER-SHAPE
title: An adapter shape only where the adapter produces what the Then says
part: check
kinds:
- story
reports:
- adapter-shape
pass: every criterion the plan gives the adapter shape names, in its `Then`, something the adapter produces
fail: a criterion with the adapter shape whose `Then` names no control, message, hint or page, no text quoted as shown beyond what its `When` entered, and no status
---

# GATE-ADAPTER-SHAPE

**When:** the plan gate runs, for a plan that came about under contract 35 or later — a new or changed plan is held to
the profile's contract; one an earlier plan gate passed keeps the contract it was stamped with

**Why:** a value the use case computes and a surface merely shows is proven by the port test; an adapter test beside
it answers from a stub that already holds the value, so it copies another test or claims a change it cannot make

What counts as produced by the adapter: a control the `Then` names (a button, a field, a link, a form), a message, a
hint or a page; a text it quotes as shown that no `When` step of the scenario entered — the quoted text compared
without surrounding spaces, so a title entered with spaces and shown trimmed is the use case's outcome —; a status, a
three-digit code from 100 to 599. Whether a value is computed or rendered beyond that is not checked — the plan's
craft.
