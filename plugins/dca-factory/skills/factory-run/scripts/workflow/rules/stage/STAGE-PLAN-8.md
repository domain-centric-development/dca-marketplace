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

8. **Each scenario gets the lowest level that observes its `Then` from outside**, from what the project **already has**
   (stack profile, existing tests).
   - **Happy path** — the one scenario marked `(happy path)` by the backlog, never by you → `e2e`: a browser test where
     the profile has `e2eTest:` and a browser runner, else the highest end-user level the project runs (HTTP, API).
   - **Every other scenario** → `integration`, in the source set a `test.<name>:` key declares, in one of two shapes:

     | `Then` | shape | asserted on |
     |---|---|---|
     | a business outcome — stored, refused, published, returned | `integration (port)` | the use case through its input port, wired app, real outgoing adapters, test persistence, external systems stubbed at the protocol (`http.stub:`) — once, however many adapters call it |
     | something only an incoming adapter produces — a page text, a status, a redirect, a message payload | `integration (adapter: <Adapter>, test: <Class>#<method>)` | that adapter's translation, against a stubbed input port answering with the outcome |
     | a surface showing what a state change produced — a refusal shown, a count, list or mark after a create, change or remove | both, on one line: `integration (port) and integration (adapter: …)` | port proves the change, adapter the text |

     - Read the scenario's `Then`, not its rule's heading: "computed from what is stored" over a `Then` quoting a shown
       sentence still asks for the sentence.
     - A refusal: the port test asserts the case the use case returns (with its values) or the failure it throws; the
       adapter stub answers with that same case or throws that same failure. Any other change: the stub answers with
       the outcome the port test asserts.
     - A quoted shown text stands in the adapter test as quoted — the test gate looks for it.
     - The adapter shape names its test after the **state the adapter shows** (`showsATitleOf200Characters`), never the
       scenario's action — the stub hands it that state, the test cannot perform the action. The test stage uses that
       name; `tests-planned` holds it.
     - **Adapter shape only where the `Then` names something the adapter itself produces** (a quoted text the person
       did not enter, a status, a redirect, a control, a message, a mark). A value the use case computes or keeps
       (trimmed, counted, shown as entered) that the surface merely shows → port shape alone: an adapter test beside
       it answers from a stub that already holds the value — **it reads back its stub.** The plan gate refuses an
       adapter shape whose `Then` names no control, message, hint, page, status, or quoted text beyond the `When`'s
       input (`adapter-shape`).
     - **Thrown or returned refusals is the project's choice, never the plan's.** Read `product/tech.md` (or `tech:`):
       `Refusals (<context>): thrown | returned`, else `Refusals: thrown | returned`; no line → the context's existing
       use cases (closed result with refusal cases, or thrown failure types). Name it in `## Context`
       (`refusals: <style> — <where read>`). Neither, in a story that refuses → stop once with `## needs-human` (choose,
       record the line in tech.md). Never pick one; never a returned refusal beside a thrown one in one context.
   - **`browser-only (<why>)`** — a `Then` only a browser observes (a countdown, a script's reaction to a click, a
     notification, anything after load). Needs a browser runner. `browser: none` → plan the next level and name what
     it cannot show. No `browser:` line and no runner → stop once with `## needs-human` (set one up, or record
     `browser: none`).
   - **No integration source set** (no `test.<name>:`, no `integration: none`) → stop once with `## needs-human` (set one
     up — `dca-add integration-tests` in a DCA project — or record `integration: none`); a fallback per story is a
     decision nobody took. `integration: none` → next level the project has, and say so.
   - Never a level needing a framework the project lacks (a stack decision). A level never justifies a new surface:
     that is step 4's `needs-human`, not a new adapter.
   - The test gate: a test the end-user command runs belongs to the happy path or a `browser-only` scenario.
   - **Journey** (`kind: journey`): no happy path, builds nothing — one journey test walking the epic's `## Journey`
     through the delivered stories, asserting the epic's outcome event, in the `test.journey:` source set.
