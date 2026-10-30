---
name: factory-backlog
description: Writes and checks the backlog a delivery run reads — an epic with its outcome event, or one story small enough for a single run, in the markdown-with-front-matter contract. Use when a story or an epic is to be added, split or repaired, when the plan gate refused a story as incomplete, or on "/factory-backlog". Never invents an intent, a goal, a metric or a domain contact.
---

# Write one backlog item

Input: what the human tells you, plus the project description — the product, the technical
decisions and the designed domain — and the glossaries. Output: `<epics>/<epic>/epic.md`,
`<epics>/<epic>/<story>/story.md` (a folder per story, named after its id), or a correction to one of them. The places are the stack profile's
`product:`, `tech:`, `domain:` and `epics:`, by default `product/overview.md`, `product/tech.md`,
`product/domain.md` and `product/epics`.
You write no plan, no test and no code. Run the pipeline separately once the item stands.

## Arguments

The same words from a person, a view that sends them, or another tool — one meaning each:

| Form | Does |
|---|---|
| `/factory-backlog` | asks what is wanted: an epic, a story, a correction |
| `/factory-backlog epic <id> --from <report>` | the person releases the proposal `### <id>` of that discovery report: write it as an epic (step 2a) |
| `/factory-backlog stories <epic>` | cut the next stories of that epic, each `status: draft` |
| `/factory-backlog journey <epic>` | the epic is delivered and unguarded: propose its journey (section *A journey*) — the `## Journey` timeline from the delivered stories' operations and events, ending in the outcome event, and the journey item as `status: draft` — or the `- none: <why>` line, if the person decides against one |
| `/factory-backlog release <story> [<story> …]` | the person releases these drafts: run the question pass (step 6) for each, set `status: approved` where it leaves nothing open, and say which stay drafts and why |
| `/factory-backlog release <epic>` | the person releases a whole epic: the same for every draft story of it — an id that names a folder under the epics with an `epic.md` is an epic, one that names a story's folder a story |
| `/factory-backlog <story>: <finding>` | a judge's finding to settle (the cockpit sends it so): a story where it changes behaviour, a task where it does not (section *A task*) |
| `/factory-backlog <name>#<n>: <finding>` | a finding of the project's own (`product/findings/<name>.md` — a test flaky in more than one story is `flaky#<n>`): the same, the task's `closes:` names that row |
| `/factory-backlog <words>` | anything else: what the person wants, in their words — an epic, a story, a task or a correction |

A form names the person's decision; it never skips a check. A release with open questions stays a draft until
they are answered.

The full contract is in `factory-run/reference/backlog-contract.md`; read it before your first
item in a project. The templates are `factory-run/templates/backlog/{epic,story,task}.md.tmpl`.

## Before the first item: the project description

Run `python3 .agents/factory/story-gate.py --project` first, every time. It exits 0 when the product
and the technical description both stand, 1 when one is incomplete, and 3 when one is missing. On 3
or 1, write **no** epic and **no** story. Say in one sentence which part is missing (or which
heading), and that `/factory-setup` writes it first — what is built, for whom, through which
surfaces, how it works, how it looks, and the stack, frontend approach, persistence, runtime,
integrations and version policy. Every story would otherwise carry decisions nobody took, and a
plan stage would stop for them later, when no one is there to answer.

If the human insists on a story anyway, write it with `status: draft` and a first assumption
`- open: the project description is not written yet — /factory-setup` — and never approve it while
the gate still reports it missing. Once the description stands, write within it: a story that needs
a surface the product description does not list, state kept where `## How it works` says otherwise,
something `product/tech.md` excludes, or a context the designed map does not carry is a question
about the description — ask it now, while the person is here, and change the description first
(through the description skill or the context-map skill where they are installed) — not a story
that smuggles the decision in.

## Do

1. **Find out what is being asked for.** An epic and a story are different things: an epic states
   why a body of work exists and how anyone will know it delivered; a story describes one piece of
   observable behaviour small enough for one run. If what you were told is one sentence about a
   button, it is a story; if it is a problem someone has, it is an epic and its first story.
2. **Never invent the four epic fields.** `intent`, `goal`, `metric` and `domain_contact` are the
   fields the gate refuses a story for, and it refuses it for a reason: a stage that cannot read
   the intent invents one. If the human has not stated them, ask — one question per missing field,
   in their words, not a form. A placeholder is worse than a missing file, because the gate passes
   it.
2a. **An epic from a discovery report** (`product/discovery/<topic>/discovery.md`, a proposal the person
   released): take its `intent`, `goal` and `metric` as the report writes them, add `discovery:` with the
   report's path, and ask only what it leaves `open` — the domain contact, the journey. Where the problem itself
   is unclear and no report exists, offer `/factory-discover <topic>` before writing an epic.
2b. **Whether the epic waits for another.** An epic may name the epics that must be delivered before its
   stories start: `depends_on: [<epic id>, …]` in its `epic.md`, `[]` for none. Ask it for a new epic when the
   backlog has another (WISH-EPIC-AFTER in the catalogue), never assume an order: epics without one run side
   by side where the runner runs more than one story, and the earlier epic's story first where it runs one. The
   gate refuses an epic that names no epic there is, itself, or a cycle.
3. **The metric is an outcome event, not a count.** Ask which domain or integration event the
   project publishes when the epic has actually worked for someone — the event whose appearance in
   production is the evidence. A story count, a burndown or "feature shipped" is not a metric. If
   the project publishes no such event yet, say so in the epic: the event is then part of the work.
4. **Name the bounded context, and check the map.** A story's `context` must be a context the
   designed map (`product/domain.md`) already carries — designed, even where it is not built yet. If the behaviour would need a new context or a new relationship
   between contexts, do not write the story: say that it is a scoping question and what it would
   need. That decision is not one a story may smuggle in.
5. **Write criteria as observable behaviour, with keys** — as scenarios by default: the story's
   business rules as `### Rule: <text>`, under each at least one `#### <key>` scenario with
   `- Given / When / Then / And` steps and concrete values (the line form `- <key>: <criterion>`
   stays valid). One `When` per scenario: a scenario with two causes ("the value fails the format
   check *or* is unknown") is two scenarios, even though the gate can only count the `When`s. The
   key is lowercase, hyphenated and names the behaviour (`shows-empty-state`). It is committed —
   the test stage records it next to the test that proves it — so never a number and never renamed
   later. Every concrete detail the human states (wording, order, placement) is its own criterion:
   a detail that is not a criterion is a detail no test will cover.
   A criterion is behaviour the system **does not show yet**: its test must be red before the build
   stage, and the gate refuses one that is already green. What has to keep working is the job of
   the tests that already exist — "posting still works" is not a criterion.
   A story that changes behaviour the system **already has** says so under `## Changed
   expectations`: what is seen now, what is seen after, in the project's words. The human writing
   it needs to know the behaviour, not the stories or the tests behind it.
   **Mark the happy path** — the one scenario that shows the story's value, as the person would
   demonstrate it: `#### <key> (happy path)` (line form `- <key> (happy path): …`). Exactly one per
   story; the plan gate refuses none and two. It gets the story's end-to-end test; every other
   scenario is tested integrated. Ask for it where it is not obvious: "Which scenario shows what this
   story is for?" Give it a `Title:` line where the key in words is not what its end-user test should be
   called — and always where the project binds its end-user tests to a shared list of scenario titles:
   then the title is that list's, added there first.
   An assumption that fixes an observable result — a format, an order, a wording the user sees —
   is a criterion waiting for its answer, not a footnote: the plan stage builds the next best shape
   around an open assumption, and that shape then reaches delivery unconfirmed. Ask for it before
   the story is released, or write the answer in as a criterion.
6. **Run the question pass before the story is released** — `reference/question-pass.md`, every item,
   against the story, the three files of the project description, the glossary and the code it touches:
   context on the
   map, surface and actor, technical fit, external dependency, inputs at both sides of every limit,
   examples where rules part, malformed address, position and order, defaults, failure of a
   dependency, state and lifecycle, changed behaviour (and the spec scenario it alters), already a
   story's, already the system's (adopt), already green (a guarantee, not a criterion), repeated or
   abusive use, coverage, out of scope, operations (the glossary's word, looked up in the field),
   outcome (`publishes:`). Ask the human what it turns up, while they are here. What the description
   already answers is not asked again; answers go into rules, scenarios or `answered:` assumptions,
   what stays open is an `open:` assumption.

7. **Use the project's own words.** Read the context's glossary and the description's `## Glossary`
   first and write the story in those terms and operations. A term or a verb the story needs that
   neither carries goes into `## Assumptions` as a question for the domain contact, not into the story
   as if it were established.
8. **Assumptions are questions, never decisions.** Each line is `open:` or `answered:`. What the
   team decided itself belongs in the criteria or in a plan, not here. A story whose criterion
   contradicts one of its own open assumptions is not ready — the judge will stop the run for it,
   so resolve it now: either the assumption is answered, or the criterion is not yet a criterion.
8a. **Give a new story an id no factory uses.** Where the profile names `claim_remote:` (several factories on one
   backlog), take the id from `python3 .agents/factory/factory-cli.py --free-id <PREFIX>` — it fetches and skips
   every id the remote main line, its `Story:` history or a remote claim uses; otherwise the next number of the
   epic's prefix. Never reuse the id of a delivered story, also one whose folder is gone.
8b. **Say when it was written.** Every new epic, story, task and journey item carries `created:` in its front
   matter, the UTC time you write it (`date -u +%Y-%m-%dT%H:%M:%SZ`). The views show the backlog newest first by
   it; never change it on an item that has one.
9. **Leave `status: draft` unless the human releases it.** The gate refuses to plan a draft story,
   which is the one check no script can replace. Say plainly that the story is waiting for their
   release, and set `approved` only when they say so. Commit the story once it is released, the release
   line included: the runner starts a story from the main line's commit and leaves one the checkout
   holds uncommitted, or changed since its commit, `blocked`.
10. **Check it with the gate, not with your own judgement:**
   `python3 .agents/factory/story-gate.py --check-backlog --story <id>` — the plan gate's checks on
   the story, writing nothing. Not `--stage plan`: that one records the story and the tests as the run
   found them, and a record taken while the story is still being written leaves files under `.dca-factory/runs/`
   that the commit hook then refuses. Every finding it reports is yours to fix before you hand the
   item over. Report what it said.

11. **Measure the work on the story.** Writing a story costs tokens too, and what a story cost
   includes it. As soon as the story's id is settled — before the question pass — run
   `python3 .agents/factory/factory-cli.py --window-start backlog --story <id>`, and when you hand the
   story over — released and committed, or stopped with open questions — first
   `python3 .agents/factory/factory-cli.py --window-end backlog --story <id>`, then commit (the journal
   under `.dca-factory/evidence/<id>/` is part of the commit). One window per session; a session that picks the story
   up again opens its own. The window claims nothing: a runner working another story is not held up.
   An epic alone opens no window.

12. **Showing the backlog.** When someone asks what is in the backlog or where it stands, run
   `bash .agents/factory/factory.sh backlog --format md` and show it as it is — the tables by epic,
   the tokens and *Next* — without retelling it, reformatting it or adding after its *Next*. Say more
   only when asked, read from the file the answer comes from.

## Kinds of item

Before writing one of these, read its section in `reference/item-kinds.md`:

- **a journey** — an epic's `## Journey` as an event timeline to its outcome event, and the journey item
  (`kind: journey`, `depends_on:` its stories, one scenario, no happy-path mark) once the epic is delivered;
- **a feature** — `feature:` beside `context:`, a term of the context's glossary; criteria of two features
  are two stories;
- **a task** (`kind: task`) — a change no actor notices: no criterion, `closes:` the finding rows it settles;
  the one question that decides between story and task is *would an actor notice?*;
- **taking a feature away** — a story whose criterion is the absence, its `## Changed expectations` what
  no longer holds;
- **a story from a wish** (`/factory-run <words>`) — drafted in the contract, then the open entries of
  `reference/questions.md` asked at once, in order, word for word;
- **a story pasted from a tracker** — rewritten into the contract, never copied;
- **splitting** — along a seam (two actors, two contexts, a criterion that needs another shipped), order in
  `depends_on`, never "part 1 / part 2";
- **repairing an item the gate refused** — exactly what the gate named, nothing else.

## Run for a request

When the factory runs you for a person's request — the prompt says *request `<id>` … you run headless* — follow
`factory-run/reference/requests.md`, *Run headless*. The arguments are the forms above, word for word. A wish keeps
what it writes `status: draft`: the person releases it. Every question this skill would ask — the project
description missing, which epic, a criterion the words leave open, a decision the description does not carry — is
answered from the files where they settle it, else asked as **one** decision record with `request: <id>`: beside the
story it concerns (`stage: backlog`), or as the project's own record where no story exists yet; then end. A release
is the person's decision: run the question pass, approve what it leaves open nowhere, and write each open question
as a record beside its story, which stays a draft.

## Do not

- Do not write a plan, a test shape, an implementation hint or a file path into a story. What
  changes in the code is the plan stage's answer, and a story that prescribes it stops being a
  statement about behaviour.
- Do not migrate an existing backlog wholesale. The contract applies to new items; the gate only
  ever looks at the story it is called with, and rewriting finished work invents intents nobody
  stated.
- Do not touch `.dca-factory/` — those are run artefacts, not backlog — and never write `status: delivered`
  or `delivered:`: those two lines are the gate's.
