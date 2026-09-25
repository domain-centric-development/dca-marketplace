---
name: factory-backlog
description: Writes and checks the backlog a delivery run reads — an epic with its outcome event, or one story small enough for a single run, in the markdown-with-front-matter contract. Use when a story or an epic is to be added, split or repaired, when the plan gate refused a story as incomplete, or on "/factory-backlog". Never invents an intent, a goal, a metric or a domain contact.
---

# Write one backlog item

Input: what the human tells you, plus the project description — the product, the technical
decisions and the designed domain — and the glossaries. Output: `<backlog>/<epic>/epic.md`,
`<backlog>/<epic>/<story>.md`, or a correction to one of them. The places are the stack profile's
`product:`, `tech:`, `domain:` and `backlog:`, by default `project/product.md`, `project/tech.md`,
`project/domain.md` and `project/backlog`.
You write no plan, no test and no code. Run the pipeline separately once the item stands.

The full contract is in `factory-run/reference/backlog-contract.md`; read it before your first
item in a project. The templates are `factory-run/templates/backlog/{epic,story}.md.tmpl`.

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
something `project/tech.md` excludes, or a context the designed map does not carry is a question
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
3. **The metric is an outcome event, not a count.** Ask which domain or integration event the
   project publishes when the epic has actually worked for someone — the event whose appearance in
   production is the evidence. A story count, a burndown or "feature shipped" is not a metric. If
   the project publishes no such event yet, say so in the epic: the event is then part of the work.
4. **Name the bounded context, and check the map.** A story's `context` must be a context the
   designed map (`project/domain.md`) already carries — designed, even where it is not built yet. If the behaviour would need a new context or a new relationship
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
   story is for?"
   An assumption that fixes an observable result — a format, an order, a wording the user sees —
   is a criterion waiting for its answer, not a footnote: the plan stage builds the next best shape
   around an open assumption, and that shape then reaches delivery unconfirmed. Ask for it before
   the story is released, or write the answer in as a criterion.
6. **Run the question pass before the story is released.** Read the story, the three files of the
   project description, the glossary and the code the story touches, and go through this list. Ask the
   human what it turns up, while they are here — a question left for the plan stage stops a loop
   later, when nobody is there to answer:
   - **context:** is the story's context on the designed map? If not, it is a question about the
     description — a new context, a new relationship — asked now, not a story;
   - **surface and actor:** does a trigger or an outcome need an entry point, a page or a message
     `## Surfaces` does not list, or an actor `## What and for whom` does not name? Who may reach
     it? (Ask *whether* a way exists, never *which* one to build.)
   - **technical fit:** does the story need what `project/tech.md` excludes — a second persistence,
     a client framework where pages are server-rendered — or what the stack cannot do? That is a
     question about the technical description, not a detail of the story;
   - **external dependency:** a system neither the designed map nor `## Integrations` carries is a
     question about the description, not a story. Its contract (endpoints, status codes, what
     counts as unavailable) goes into the description and the configuration once, never into the
     story;
   - **inputs:** format, allowed range, boundaries, and what happens at them — a scenario per boundary
     that matters;
   - **defaults:** one stated value, and where the user sees it;
   - **failure of a dependency:** the behaviour, and after how long a slow answer counts as a failure;
   - **state and lifecycle:** every transition a rule names, including the conflict case where two
     sources of the same value meet;
   - **changed behaviour:** what looks different afterwards → `## Changed expectations`;
   - **already the system's behaviour:** a whole story whose scenarios the system already shows is not
     a story to build but one to **adopt** — `status: adopted` (the backlog contract's "Adopted story"):
     the factory maps it to green tests, writes the missing ones with a break each, and records it as
     delivered with evidence. Offer it; on a brownfield project, offer once per new story to adopt the
     existing behaviour the new story depends on — never as a stop;
   - **already green:** check every scenario whose outcome is an absence or a non-change — "no …
     is shown", "nothing changes", "… still works" — against the code as it is today. If it already
     holds (the element does not exist yet, so it is not shown), it is a guarantee, not a
     criterion: its test would be green before the build, and the gate refuses that. Take it out
     of the criteria and say so; the plan stage turns it into a guard for the existing tests. Keep
     it only when today's system does show what the scenario forbids;
   - **repeated or abusive use:** a rule a user can probe or exhaust;
   - **coverage:** a rule without a scenario, a scenario with two causes, a `Then` no test can observe;
   - **out of scope:** what this story leaves to another → `## Out of scope`.

   What the project description already answers is not asked again. Answers go into rules, scenarios or
   `answered:` assumptions; what stays open is an `open:` assumption.
7. **Use the project's own words.** Read the context's glossary first and write the story in those
   terms. A term the story needs that no glossary carries goes into `## Assumptions` as a question
   for the domain contact, not into the story as if it were established.
8. **Assumptions are questions, never decisions.** Each line is `open:` or `answered:`. What the
   team decided itself belongs in the criteria or in a plan, not here. A story whose criterion
   contradicts one of its own open assumptions is not ready — the judge will stop the run for it,
   so resolve it now: either the assumption is answered, or the criterion is not yet a criterion.
9. **Leave `status: draft` unless the human releases it.** The gate refuses to plan a draft story,
   which is the one check no script can replace. Say plainly that the story is waiting for their
   release, and set `approved` only when they say so.
10. **Check it with the gate, not with your own judgement:**
   `python3 .agents/factory/story-gate.py --check-backlog --story <id>` — the plan gate's checks on
   the story, writing nothing. Not `--stage plan`: that one records the story and the tests as the run
   found them, and a record taken while the story is still being written leaves files under `tasks/`
   that the commit hook then refuses. Every finding it reports is yours to fix before you hand the
   item over. Report what it said.

11. **Measure the work on the story.** Writing a story costs tokens too, and what a story cost
   includes it. As soon as the story's id is settled — before the question pass — run
   `python3 .agents/factory/story-gate.py --window-start backlog --story <id>`, and when you hand the
   story over — released and committed, or stopped with open questions — first
   `python3 .agents/factory/story-gate.py --window-end backlog --story <id>`, then commit (the journal
   under `tasks/<id>/` is part of the commit). One window per session; a session that picks the story
   up again opens its own. The window claims nothing: a runner working another story is not held up.
   An epic alone opens no window.

12. **Showing the backlog.** When someone asks what is in the backlog or where it stands, run
   `bash .agents/factory/factory.sh backlog --format md` and show it as it is — the tables by epic,
   the tokens and *Next* — without retelling it, reformatting it or adding after its *Next*. Say more
   only when asked, read from the file the answer comes from.

## A journey

An epic may name its **journey** — `## Journey` in `epic.md`: the steps as a user takes them, across the
epic's stories and contexts, to the epic's outcome event, and why a break would hurt. Ask for it when an
epic is created ("Which flow through this epic must never break, and why?"); leave it `open:` when the
person cannot say yet — a journey emerges from delivered stories — and add it at any later time. An epic
without one has no journey test, which is a decision, not a gap. The product description's
`## Qualities` may name flows that must never break; offer them as an epic's journey.

The journey test is its own backlog item in the epic's folder: `kind: journey`, `depends_on:` the stories
that build its steps, one scenario walking the steps to the outcome event (no happy-path mark — it is a
guard, not acceptance). It becomes ready when those stories are delivered, runs plan, test, judge and
document — nothing to build — and its test is green at its test gate. Template:
`factory-run/templates/backlog/journey.md.tmpl`.

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

## Do not

- Do not write a plan, a test shape, an implementation hint or a file path into a story. What
  changes in the code is the plan stage's answer, and a story that prescribes it stops being a
  statement about behaviour.
- Do not migrate an existing backlog wholesale. The contract applies to new items; the gate only
  ever looks at the story it is called with, and rewriting finished work invents intents nobody
  stated.
- Do not touch `tasks/` — those are run artefacts, not backlog.
