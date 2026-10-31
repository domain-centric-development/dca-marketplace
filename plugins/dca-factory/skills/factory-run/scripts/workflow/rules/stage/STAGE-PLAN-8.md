---
id: STAGE-PLAN-8
part: told
stages:
- plan
section: Do
marked: stage-plan/SKILL.md
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
     stubbed input port that answers with the outcome. Write the shape after the level:
     `level: integration (port)` or `level: integration (adapter: <Adapter>)`.
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
