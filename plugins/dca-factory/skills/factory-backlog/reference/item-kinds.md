# Kinds of backlog items

Part of the `factory-backlog` skill: what its *Kinds of item* section points to — a journey, a feature, a task, a
feature taken away, a story from a wish or pasted from a tracker, splitting, and repairing an item the gate refused.

## A journey

An epic may name its **journey** — `## Journey` in `epic.md`: the steps as a user takes them, across the
epic's stories and contexts, to the epic's outcome event, and why a break would hurt. Write the steps
as an event timeline — each a command and the event it causes (`place → OrderPlaced`), the last
one the outcome event; a step whose command or event the glossary does not name is a question first. Ask for it when an
epic is created ("Which flow through this epic must never break, and why?"); leave it `open:` when the
person cannot say yet — a journey emerges from delivered stories — and add it at any later time. An epic
decides against one with `- none: <why>` under `## Journey`; without the section it has decided nothing, and once
every story of the epic is delivered the status names it *delivered, unguarded*. Then propose its journey item:
the delivered stories' operations and events as the timeline, ending in the outcome event — or the `none:` line,
if the person decides against it. The product description's
`## Qualities` may name flows that must never break; offer them as an epic's journey.

The journey test is its own backlog item in the epic's folder: `kind: journey`, `depends_on:` the stories
that build its steps, one scenario walking the steps to the outcome event (no happy-path mark — it is a
guard, not acceptance). It becomes ready when those stories are delivered, runs plan, test, judge and
document — nothing to build — and its test is green at its test gate. Template:
`factory-run/templates/backlog/journey.md.tmpl`.

## A feature

A story names the feature it changes — `feature:` beside `context:`, the feature's name as its glossary entry spells
it in parentheses (`productdetails`); without one its criteria belong to the context as a whole. A feature is a term of
the context's language: look it up in `product/spec/<context>/glossary.md` (`Type: Feature`) and in the spec's
folders; a story that needs one the context does not have names it, and its plan brings it in. Criteria of two
features are two stories: split the story, one feature each.

## A task

One question decides between a story and a task: **would an actor notice the change?** Yes — a missing or wrong
behaviour, a bug, a feature taken away — is a story, with a criterion and a red test (a feature taken away has the
absence as its criterion). No — dead code, a helper nothing calls, a method a port inherits and nobody uses, a
placeholder file, copied test helpers, a dependency or build change, a unit test for an invariant that already holds —
is a task (`kind: task`, `factory-run/templates/backlog/task.md.tmpl`): no criterion, a sentence or two of what changes
in the code, `closes:` the finding rows it settles. Where a person's words or a finding leave it unclear, ask that one
question. A finding that makes a test assert more is neither: the test's expectation changes, which is a story's
`## Changed expectations` or a decision of the test stage.

A task lives in the epic of the code it touches — for a finding, the epic of the story the finding belongs to; for a
project finding (`flaky#<n>`), the epic whose code the test covers.
Several findings of one kind may go into one task; findings that touch unrelated code are separate tasks.

## Taking a feature away

A feature taken away is a story — an actor sees it gone. Its criterion is the **absence**, in the actor's words and
observable: "the list offers no export", "the export address answers that there is no such page"; that criterion is
its happy path and its test is red until the feature is gone. Under `## Changed expectations` say what no longer
holds, in a person's sentence — it backs the plan's `- removes <key>: <why>` for every scenario of the feature in the
spec and the deletion of the feature's tests (`## Changed tests`). Where the feature leaves code nobody needs, the plan
lists it `changes: removed`; the build takes it away.

## A story from a wish

`/factory-run <words>` hands you a wish: a user story in the person's words, with the id still to give.
Draft the story from it in the contract — the words become `## Story`, rules and keyed scenarios, open points
`open:` assumptions — and then ask from `reference/questions.md`: only the open entries, all at once, in the
catalogue's order, word for word, followed by what the question pass (step 6) turns up. A new epic gets its
four fields from these answers, never from the wish alone. Everything else is as for any story — the checks
against the description, the gate's `--check-backlog`, the measuring window. On "run it now" the story is
released (`status: approved`) and you hand its id back to `/factory-run`; on "keep it as a draft" it waits for
its release like any other.

## A story pasted from a tracker

A story pasted from an issue tracker — Jira wiki markup, GitHub Markdown, a document — is rewritten
into the contract, not copied: its goal becomes `## Story`; its scope rules become `### Rule:`
headings; its scenarios become keyed scenarios with one `When` each; its out-of-scope sentences go
to `## Out of scope`; integration notes (endpoints, environments, status codes) become a question
about the project description (item 6, external dependency); open points become `open:`
assumptions. Then run the question pass over the result. The wording of criteria and messages stays
the human's.

## Splitting

A story one run cannot deliver is two stories, not a bigger one. The tell is not length but
seams: two actors, two contexts, a criterion that only makes sense after another has shipped.
Split along the seam, give each part its own keys, and put the order in `depends_on` — never a
"part 1 / part 2" pair whose halves are meaningless alone.

## Repairing an item the gate refused

Fix exactly what the gate named. An incomplete epic gets its missing fields from the human, not
from you; a story without a context gets one only if the map already has it; a criterion without a
key gets a key that names its behaviour. Do not rewrite the parts the gate did not complain about
— a story's wording is the domain contact's, not yours.

**Speak in skills.** You run the commands; the person gets the result and, for a next step, the
skill that does it (`/factory-status`, `/factory-decisions`, `/factory-run <story>`,
`/factory-backlog`) — never a shell command to type, unless the person asks how to do something
without a session. You may run `factory.sh` for everything that starts no tool — `setup`,
`backlog`, `status`, `decisions`, `update`, `verify`, `check` — but never `run`: it starts a tool
process per stage (`claude -p` and the like) on top of this session, and the runner refuses it
inside one anyway.
