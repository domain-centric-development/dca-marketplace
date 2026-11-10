---
id: STAGE-PLAN-8
part: told
why: without a level per scenario the test stage guessed where each criterion is tested
stages:
- plan
section: Do
order: 8
---

# STAGE-PLAN-8

8. **Give every scenario its level, the lowest that observes its `Then` from outside.** Choose from
   what the project **already has**: read the stack profile and look at the existing tests.
   - **The happy path** — the one scenario the story marks `(happy path)` — gets `e2e`: a browser
     test where the profile declares `e2eTest:` and a browser runner, otherwise the highest end-user
     level the project runs today (an HTTP-level test against the running application, an API test).
     The mark comes from the backlog; never pick it yourself — a story without one was refused by
     the plan gate already.
   - **Every other scenario** gets `integration`, in one of two shapes, in the source set a
     `test.<name>:` key declares. A `Then` that is a business outcome — what is stored, refused,
     published, returned — is asserted on the **use case through its input port** in the wired
     application, with real outgoing adapters, persistence as the project runs it in tests, and an
     external system stubbed at the protocol (`http.stub:`): the use case is tested once, however
     many adapters call it. A `Then` only an incoming adapter produces — a text on the page, a status
     code, a redirect, a message's payload — is asserted on **that adapter's translation**, against a
     stubbed input port that answers with the outcome. A `Then` that shows on a surface what a state
     change produced needs both — a refusal the page shows, and as much a count, a list or a mark the
     page shows after something was created, changed or removed: the port shape proves the change, the
     adapter shape the text. Read the scenario's `Then`, not its rule's heading: "the number is computed
     from what is stored" over a `Then` that quotes a sentence shown still asks for the sentence. For a
     refusal the port shape proves the use case refuses — its `Then` asserts the case the use case
     returns, with its values, where the context returns its refusals, and the failure type it throws
     where the context throws them — and the adapter shape's stub answers with that same case or throws
     that same failure; for any other change it answers with the outcome the port test asserts. A text
     the `Then` quotes as shown stands in the adapter test as it is quoted — the test gate looks for it
     in the criterion's tests. Write the shape after the level: `level: integration (port)`,
     `level: integration (adapter: <Adapter>)`, or both on the criterion's line —
     `level: integration (port) and integration (adapter: <Adapter>)`.
     **Which of the two a context does is the project's choice, never the plan's.** Read it from the
     technical description (`product/tech.md`, or where the profile's `tech:` points) — a line
     `Refusals (<context>): thrown | returned`, else `Refusals: thrown | returned` for every context — and
     where no line says it, from the context's existing use cases: a closed result with refusal cases,
     or failure types they throw. Name it in `## Context` (`refusals: <style> — <where it was read>`).
     A context that says neither, in a story that refuses something, is a stack decision: stop once
     with a `## needs-human` (choose, and record the line in the technical description); never pick one, and never plan a returned
     refusal beside a thrown one in one context.
   - **`browser-only (<why>)`** for a scenario whose `Then` only a browser can observe — a countdown,
     a script's reaction to a click, a notification, anything that happens after the page has
     loaded. It needs a browser runner; with `browser: none` the project has decided without one:
     plan the next best level and name what it cannot show. With no `browser:` line and no runner,
     stop once with a `## needs-human` naming the stack decision (set up a browser runner, or
     record `browser: none`).
   - **No integration source set** — no `test.<name>:` key and no `integration: none` — is a stack
     decision too: stop once with a `## needs-human` (set one up — in a DCA project `dca-add
     integration-tests` — or record `integration: none`); a fallback taken story by story is a decision
     nobody took. With `integration: none` the other
     scenarios take the next level the project has, and the plan says so.
   The gate holds the plan to it: at the test gate, a test the end-user command runs must belong to
   the happy path or to a `browser-only` scenario. Never pick a level that would need a test
   framework the project does not have; adding one is a stack decision, not part of a story. A test
   level is never a reason to build a surface: if the criterion could only be driven through a page
   or an endpoint the project does not have, that is the `needs-human` of step 4, not a new adapter.
   A **journey** item (`kind: journey`) has no happy path and builds nothing: plan one journey test
   that walks the steps its epic's `## Journey` names through the delivered stories and asserts the
   epic's outcome event, in the source set `test.journey:` declares.
