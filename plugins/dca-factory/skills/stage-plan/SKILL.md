---
name: stage-plan
description: Plan stage of a factory run — turns one backlog story into an implementation plan — each acceptance criterion by its key, with its test level — and names the architecture elements that change. Use when a story is to be planned before any test or code is written, when the orchestrator hands over a story, or on "/stage-plan". Reads the story, the project description (product, technical decisions, designed domain), the stack profile, the method's configuration `dca.profile.yaml`, the project's glossary and generated context map and its existing tests — nothing else. Internal stage of the pipeline — factory-run starts it; by hand only to redo this one stage of a story that has the ones before.
---

# Plan one story

First read `factory-run/reference/stage-common.md` — the rules every stage holds to: a session the
runner started, one session that carries several stages, a repeat round, the shell, the gate. The
runner's prompt names its path and repeats none of it.

Input: the story file, the project description — `product/overview.md`, `product/tech.md` and
`product/domain.md`, or where the profile's `product:`, `tech:` and `domain:` point — the method's
configuration `dca.profile.yaml` at the project root (the instruction file's ``- configuration: `dca.profile.yaml` ``
line points at it; the layout, the naming suffixes and the resolved configuration the architecture suite holds the
code to; where it is missing or a key is absent, the defaults), and the
glossary and the context map generated from the code (`contextMap:`) where the project has them.
Nothing else — not the chat history, not an earlier run.
Output: `.dca-factory/runs/<story>/plan.md`, and nothing else. You write no test and no production code.

## Do

1. Read the story: its context, its acceptance criteria, its open assumptions.
2. Locate that bounded context — on the designed map first, then in the code. A context that is
   designed but not built yet is planned as new; say so. If the story's `context` is on neither map,
   stop: write the plan file with a `## needs-human` section stating that the story needs a new
   context or a new relationship between contexts. That is a structural decision. Where the
   designed map and the generated one disagree about the story's context or its relationships, say
   so in the plan — a difference is a finding, not something to settle in passing. A project
   without a map is not blocked by this — note the absence and go on.
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
4. **Check that the story's actor can already reach the behaviour.** The criteria name someone —
   a customer, an operator, an administrator — and a way in: a page, an endpoint, a message, a
   command line. If the context has no such way in today, the plan does **not** invent one. A new
   surface for an actor is a decision about the product and, where the surface needs a guard, about
   authorisation: write the plan file with a `## needs-human` section naming which surface the
   criteria would need and stop. Adding it silently is how one story becomes an endpoint nobody
   specified, and a rule about who may call it that nobody reviewed.
   The exception is a story whose criteria name the surface themselves — then it is specified, and
   it belongs in the change list like any other element.
5. Name the elements that change, in the project's own vocabulary: aggregates, value objects,
   domain events, use cases with their ports, adapters, read models. Say for each whether it is
   new or changed, and where it belongs — layer and package/namespace as this project lays them
   out, not as any sample does. A name carries the suffix `dca.profile.yaml` declares for its
   kind (a use case, its input port, a repository, a controller): the architecture suite refuses
   any other, and a plan the build has to rename is a plan that was not read.
6. Respect the architecture the project has adopted: the domain free of framework types, ports
   declared inward and implemented in adapters, no raw cross-context imports, one aggregate
   changed per transaction. Ask the project's knowledge skill where one is
   installed (see below) rather than deciding a pattern question from memory.
7. List the acceptance criteria by **key** — the story's keys verbatim, the later stages and the
   gate join on them — and give each its level (step 8). The criterion's text stays in the story;
   a plan that retypes it says nothing the reader does not have. The pipeline writes these lines:
   `factory-cli.py --plan-skeleton <story>` (the runner runs it; in a session run it yourself
   before the stage) puts the file's headings and one line per key in place. A story written in
   scenarios keeps its rules and each scenario's steps;
   plan within `## Out of scope` — what it lists is not planned, however close it lies. Add a criterion for every concrete detail the story specifies (wording,
   placement, ordering): a detail that is not a criterion is a detail no test will cover and no
   stage will build. A clause about a state that did not come about — not saved, not sent, unchanged —
   says how a person sees it (the list as it was, the old value still on the page, no new entry): write
   it after the criterion's level where the story leaves it implicit, and where neither the story nor
   the product description says it, choose the plainest sign and record it under `## Open assumptions`
   — the run goes on and the judge sees the assumption. An example of a rule sits where the rule
   differs from the obvious neighbour — a rounding exactly on the half cent, where rounding half up and
   half to even part; a limit on both sides of it. Where the story's example is one both rules answer
   alike, the rule's line under `## Invariants` names the value that tells them apart, so its unit test
   uses it.
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
8a. **Name the invariants of every domain type you change.** For each aggregate, entity, value object and
   domain service in `## Changes`: the rules it must never break — what the criteria imply and the guards
   its type implies (a value that is required, trimmed, within a range, unique in its aggregate). One line
   each under `## Invariants`, the rules separated by `;` — each rule gets its own unit test, so one rule
   is one thing the type refuses or keeps; a type without rules of its own says `none — <why>`. The test stage writes a
   unit test for every rule named here, and the build writes no guard that is not named: a check nobody
   planned is code no test asked for. The test gate refuses a changed domain type without its line.
8b. **A story that publishes the epic's outcome event** (`publishes:` in its front matter) plans the event
   in `## Changes` under that exact name — no synonym, no translation — and the domain type or use case that
   raises it. The document gate refuses the story while the code declares no such type, or nothing the story
   changed refers to it.
9. **Find the existing tests the story contradicts** — every test in the project, whoever wrote it:
   the ones that assert the behaviour the criteria change. Read the test sources, not the backlog;
   a test need not belong to any story. List each under `## Changed tests` with what backs the
   change: the line of the story's `## Changed expectations` it follows. Where the story has no
   such section and you still find contradicting tests, the story changes agreed behaviour without
   saying so — write **one** decision record (`stage: plan`) listing every one of them, with the
   expectation each holds today and what the story would need instead, and stop. Once answered,
   plan again and cite the id in each row. A test the story does not contradict is not listed; the
   gate lets the later stages change only what is listed and backed. A test that only has to follow a
   changed shape — a type it builds gains a field, or a type or a method it names is renamed, its assertions and
   expected values stay — is not contradicted: it is neither listed nor asked about.
9a. **Find what the system already shows.** A scenario whose `Then` holds on today's code cannot get a red
   test, and the test gate refuses a green one. Look for it the same way — the test sources, and the
   scenarios of the delivered and adopted stories under the epics. Who carries it decides what you do:
   - **only code carries it, no story, and a test shows it** → ask nothing. Write `## Adopt` in plan.md, one row
     per such scenario: `| <key> | <Class>#<method> |`, the test that shows it holds today. The plan gate adopts
     what you name: every scenario of the story → the story becomes `status: adopted`, and the runner goes on with
     it as an adoption (end the plan there, write no later stage's file); some → they move into an adopted story
     `<story>-holds` beside this one, and you plan the rest as usual. Where the scenarios that hold include the
     story's only happy path and others remain, do not adopt: ask, as below;
   - **a delivered or adopted story's scenario carries it** → write **one** decision record (`stage: plan`) naming
     each such scenario, the test that asserts it (file and line) and the story that delivered it, and stop;
     recommend `superseded` for a whole story, or taking the scenario out of this one;
   - where the story reads as asking for more than what holds — its wording names behaviour the code lacks — ask
     too, with the option to change the story so it asks for what the page does not do yet.
   A scenario the story changes is step 9's, not this one.
9b. **Derive the spec delta.** Read the story's context's spec — `product/spec/<context>/scenarios.md` and every
   `<feature>/scenarios.md` below it, the context lowercase and hyphenated; a context without one holds nothing yet.
   The story's `feature:` says which file its criteria go to (none: the context's own). A feature the context does
   not have yet is born here: the skeleton writes `- adds feature <name>`, and the plan proposes its glossary entry
   (`<Term> (<name>): <what it groups>`, `Type: Feature`) under `## Glossary proposals` — the document stage writes
   it, and the delivery refuses a feature without one. A criterion that stands under another feature moves; the
   skeleton writes `- moves <key>: <from> → <to>`. The skeleton's `## Spec delta`
   already says, key by key, what the comparison finds: `adds` (the spec lacks it), `holds` (word for word
   there) or `changes` (there, otherwise). Add what only you can see: `- removes <key>: <why>` for a criterion
   of the spec the story takes away, and `- rule "<old>" → "<new>"` where the story rewords a rule — the criteria the
   spec holds under the old text follow it to the new one without being the story's (a `- holds <key>` for one
   is accepted); a criterion the story takes away is `removes`. A rule `## Changed expectations` quotes that the
   story no longer writes is such a rewording: the test gate refuses a delta without its line. A change or removal must follow from
   the story's `## Changed expectations`; where it does not, it is a change of agreed behaviour nobody said —
   one decision record naming the keys, as in step 9, and stop. The other way round as well: a line of
   `## Changed expectations` that alters a criterion the spec holds, while the story does not carry that key
   with its new text, would leave the spec's old text standing — one decision record naming the keys and
   the text each would need, and stop.
9c. **Search what lies outside the story's own files**, and list each hit under `## Files` (`changes:` with what
   follows), so the tidy stage's footprint covers it:
   - a rule whose statement changes → its old wording in doc comments, messages and the other documents;
   - a call the story removes → the target's remaining callers; where none is left, the target and the tests that
     only keep it alive, `changes: removed`;
   - a check, a literal or a mapping the story adds → the same one elsewhere: a second copy is named, a third is
     lifted into one place.
   Nothing found is no line. A search the plan skipped is a finding the judge ranks against the plan.
10. Name business terms **and operations** in the criteria that are not in the glossary yet, as
   proposals with a one-line definition — an operation as `<domain word> (<code word>): <what it does
   to which term>`. Name use cases, commands and events from the operation's code word. The code word
   comes from the glossary, the description's `## Glossary` or the story's answered assumptions; where
   none of them gives it and the word could name more than one operation (e.g. creating a thing or
   adding it, deleting it or cancelling it), it is a `## needs-human`, not a choice. Do not silently invent domain language.
11. Back every **decision** with evidence — a level chosen, a pattern picked, an element placed, a test
   named as contradicted: the file, and the line or symbol you read it from, in the same row or line.
   A row that names the file it changes is its own evidence; do not restate what the file says. A
   statement without evidence is a guess and is marked as one. A catalog node is cited by its path
   inside the catalog, as the knowledge skill cites it (`recipe/add-an-aggregate.md`,
   `marker/port-out/repository.md`) — never by a path into a skill folder, and never rewritten after
   the fact.
12. **Keep the plan a page.** Tables and one-line items, no paragraphs: the plan is read by every later
   stage and by the judge, so every sentence here is read four times. What the story already says is
   not repeated; what a later stage can read in the code is pointed at, not copied.

## Task mode

A `kind: task` changes nothing an actor sees, and has no criterion. The plan says what changes in the code and why
no behaviour does: `## Context`, `## Changes`, `## Files` (with `changes: new` and `changes: removed` where a file
comes or goes) and `## Invariants` only where a domain type changes; no `## Acceptance criteria`, no levels, no
`## Spec delta`, no `## Changed tests` — a test that existed before stays as it is, except that it follows a type or
a method the task renames: that is no question and no `## needs-human`, the plan lists the file under `## Files` with
`changes: follows the renamed <old> → <new>`, and the gate reads the rename from the tree. Name the finding rows the story's
`closes:` settles and where each one sits. Where the change would alter behaviour after all — an answer, a page, a
stored value — stop with a `## needs-human`: it is a story, not a task.

## Adopt mode

A story with `status: adopted` describes behaviour the project already has; nothing is built. The plan
restates its scenarios with their keys and, for each, names **where the behaviour lives** (file and line)
and **which existing test covers it** (file, class, method) — or that none does. It plans no change to
production code and no change to an existing test. A scenario the code does not show at all is not
adoptable: stop with a `## needs-human` — the story describes behaviour the system does not have.
Step 8a applies to what the scenarios exercise instead of what changes: under `## Invariants`, one line per
aggregate, entity, value object and domain service the adopted behaviour runs through, with the rules it
enforces today, its guards included (`- <Element>: <rule>; <rule>`, or `- <Element>: none — <why>`); where the
scenarios exercise no domain type, one line `- none — <why>`. The test gate refuses an adoption without a line.

## Ask, do not recall

Where the profile names `knowledge: <skill>`, ask it instead of your recollection whenever an
answer would decide something, and cite the node by its path inside the catalog; never adopt a
knowledge source the profile did not name. The rule in full: `factory-run/reference/stage-common.md`,
beside this skill.

## Who carries this stage

`carrier.plan: <name>` in the stack profile names the skill or agent that holds this project's craft
for it; use it where this tool offers it, otherwise do the stage as described here and say so in
your file. The rule in full: `factory-run/reference/stage-common.md`.

## The plan file

```markdown
# Plan — <story id>: <title>

## Context
<bounded context, and why this story belongs to it — two lines>

## Changes
| Element | Kind | Location | New or changed | Evidence |
(one row per element; Evidence is the file:line, or the catalog node by its path inside the catalog)

## Acceptance criteria
- <key>  →  level: e2e | integration (port) | integration (adapter: <Adapter>) | browser-only (<why>) — <the runner in this project>, happy path on the one the story marks
                                  (the key alone; the criterion's text stays in the story)

## Invariants
- <Element>: <rule>; <rule>           (one line per domain type in `## Changes`, its guards included; `;` separates rules)
- <Element>: none — <why>

## Changed tests                  (omit the section when the story contradicts no existing test)
| Test file | Backed by |
| --- | --- |
| <path from the project root> | <the story's changed-expectation line, or the decision id> |

## Files
- `<path>` — changes: <what>          (every file the plan expects to change, from the project root;
                                       `changes: new — <what>` for a file that does not exist yet,
                                       `changes: removed — <why>` for one that goes — the build gate
                                       holds both, `plan-files`)
- `<path>` — read: <why>              (the pattern to mirror, the fixture to reuse — what a later
                                       stage must read to understand the change; one line each)

## Glossary proposals
- <term>: <definition>            (omit the section when there are none)

## Open assumptions
- <assumption from the story that the plan rests on>   (a known gap it defers stays a gap: the judge keeps it as a finding)

## needs-human                    (only when the run must stop — otherwise leave the heading out)
decision: <story>-<nn>
<one line saying what is asked>
```

A `## needs-human` names a **decision record** with `stage: plan` — the shape, and how an answered
record is cited when you plan again, in `factory-run/reference/stage-common.md`.

## Do not

- Do not write code or tests, and do not run the build.
- Do not widen the story. A change you consider necessary but that no criterion asks for goes
  into `## Open assumptions`, not into the plan's change list.
- Do not add an incoming adapter — a page, an endpoint, a consumer, a tool — that no criterion
  names. That is step 4's `needs-human`, and it stays one whether or not the project has an
  obvious precedent for such an adapter.
- Do not renumber or rename the criterion keys; they are committed identifiers.
