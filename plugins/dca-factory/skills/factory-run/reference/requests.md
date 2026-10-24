# Requests — the factory as a process of its own

Part of the `factory-run` skill: how the factory runs without a session — started once with `up`, ended with
`down`, shown in a browser with `serve` — and what a skill does when the factory runs it for a person's request
instead of a person in a chat.

## Two ways to act

| | In a session (`/factory-…`, the cockpit) | Through a request (`factory.sh request`, the page) |
|---|---|---|
| who acts | the session's agent, in the chat | the factory, headless, with the profile's tool |
| when | at once | before the next story, and between the stages of a running one |
| asking back | in the chat | as a decision record, answered on the page or in any session |
| needs | an open session | `factory.sh up` |
| tools | the session's | every tool the factory runs stages with |

Both write the same files: a request runs the skill a session would run, with the arguments a session would give
it. The order, the marks and which request a press writes are the factory's — every view's `action` carries its
`request` beside its `skill` — so a page decides nothing.

## The lifecycle

- `factory.sh up [--serve] [--port <n>]` starts `factory.sh run --watch --stay` in the background — a process of
  its own, outside any session — and says when it holds the checkout. Its pid and log lie beside the run folder
  (`.dca-factory/factory.json`, `factory.log`). The flags `run` takes for the backlog (`--tool`, `--parallel`,
  `--interval`, `--keep-going`, …) pass on. A factory that is up already — from `up`, a terminal or a session —
  is named, and nothing starts: one worker per checkout, as the claim has it.
- `factory.sh down` writes the stop file and sends the runner a TERM: it ends after its running stage (at once
  where it only waits), gives the claim back, and `down` waits for that. On Windows a signal would end the process
  at once, so there the stop file alone ends it — before its next story, or at once where it waits. `--now` interrupts the running stage too;
  its work so far stays, and the stage runs again later. `--no-wait` returns at once.
- `factory.sh serve [--port <n>]` serves the page. `up --serve` starts it with the factory, and `down` ends both.
- `status --live` names the worker — `worker: {owner, since, beat, how, alive, stopping}`, `how` one of `up`,
  `runner`, `session` — and every status counts the requests.

## The request file — `.dca-factory/requests/<stamp>-<kind>.md`

Protocol, not state: what a request does lands in the project's files, and the request is deleted once done. The
stamp is UTC to the millisecond, so the files sort in the order they were written; the factory works them in that
order.

```markdown
---
kind: answer
record: US-3-01
option: b
story: US-3
by: Ann
asked: 2026-10-24T10:15:00Z
state: queued
---

archived is history, not inventory
```

- **The front matter** names the kind and what it is about — `story:`, `epic:`, `record:`, `topic:` with
  `proposal:` — `option:` (an answer's option key, a correction's reason code), `from:` (a stage, for `run`),
  `by:` (who asked; `git config user.name` where nobody said) and `asked:`. The person's words are the body.
- **The kinds** and the skill each runs:

  | kind | names | runs |
  |---|---|---|
  | `wish` | the words | `factory-backlog <words>` — kept as a draft |
  | `release` | stories, or an epic | `factory-backlog release …` |
  | `stories`, `journey` | an epic | `factory-backlog stories|journey <epic>` |
  | `describe` | the words | the description skill (`dca-describe <change>`) |
  | `discover` | the words | `factory-discover <words>` |
  | `epic-from` | a topic and its proposal | `factory-backlog epic <proposal> --from <report>` |
  | `answer` | a record, an option or words | `factory-decisions <story> <record>: answer …` |
  | `accept`, `correct` | a story (correct: the words, `option:` the code) | `factory-decisions` on its acceptance |
  | `run` | a story, `from:` a stage | the runner: the story starts next |
  | `stop` | — | the runner: nothing more starts |

- **Checked when written, and again when worked.** `factory.sh request` and the page refuse what names nothing
  that exists, a record that is answered already, an option the record lacks, a kind without its words — with the
  reason, writing nothing. The same request queued twice is one. What held when it was written but no longer holds
  when the factory takes it (an answer given meanwhile by hand) fails with the reason.
- **`state:`** — `queued`; `running` (`worker:`, `started:`, `attempts:`); `waiting` (`record_file:` names the
  record its skill asked); `failed` (`error:`). A failed request is never taken again on its own:
  `factory.sh requests --retry <id>` queues it, `--drop <id>` removes it. A request a factory left `running` when
  it ended is queued again at the next start.
- **The journal** — `.dca-factory/requests/journal.tsv`: one line per start and end (`request-start`,
  `request-end` with its exit, its state and its commit) and the `usage` of each process. The tool's raw output is
  `.dca-factory/requests/out/<id>.out` (`factory.sh follow --request <id>`), pruned a week after its request ended.

## When the factory works a request

- **Before the next story**, every request in order; then `run` requests, whose story starts next; then the
  schedule. A `stop` request ends the factory there.
- **Between the stages of a running story** — before its next unit (the builder, the reviews, the verifier) —
  every request not about that story. One about it waits until its run ended.
- **In a parallel run** a request takes the next free slot before any story; one about a running story waits.
- Each request is one process (`factory-cli.py --work-request <id>`) in the main checkout, under the runner's
  claim, with the tool `tool.request.<kind>`, `tool.request` or `tool:` names, `model.<tool>.request` and
  `effort.<tool>.request` as for a stage. Its shell is a stage's, with `factory-cli.py` narrowed to the flags the
  dialog skills read and record with, plus `factory.sh` backlog, status, decisions, discover, spec-delta and help —
  no flag and no verb that starts a run, a request, the factory or its page.
- **What it wrote is committed on its own** — `chore(backlog): <kind> <target>`, `Request:` and `By:` in the
  body — the paths it changed that were clean before and belong to the backlog or the description (the folder the
  epics lie in and everything in it, the description's files, the discovery, `docs/`, `AGENTS.md`), never the spec —
  what holds is merged by the gate that delivers. A path a person had changed before stays uncommitted and is named;
  so is anything else, code and the spec above all. The commit goes through the commit hook like a person's backlog
  commit, so it runs what the profile's `checks.backlog:` names; refused, what the request wrote stays in the
  checkout, unstaged, and the request says why.

## Run headless — what a skill does for a request

The prompt says so: *request `<id>` of the factory, written by `<person>` … you run headless*. Then:

1. **The request is the person's confirmation of what it names.** Write what they asked for, as theirs: `by:` is
   the request's `by:`, `at:` now. A press on "accept" is the acceptance; an answer's option key is the answer; a
   wish's words are the wish. Do not ask whether they meant it.
2. **Never guess, never ask in the chat.** Where the skill would ask the person and the files do not settle it,
   write the question as **one decision record** with `request: <id>` in its front matter, and end:
   - about a story — beside it, `<story>/decisions/<nn>.md`, the stage the question belongs to as `stage:`
     (`backlog` for the backlog skill), as `templates/decision.md.tmpl` has it;
   - about no story — the description, a discovery, an epic not written yet — as the project's own record,
     `<product>/decisions/<stamp>-<topic>.md` (the prompt names the file), `id:` its file name, no `story:`,
     `stage: request`.

   Options, each `- a: …`, and a recommendation, as every record. The factory sets the request `waiting`; once a
   person answered the record, it runs the request again and says so in the prompt — *this request ran before and
   asked* — read the answer, go on from there, and write nothing the answer and the request do not settle. The
   factory stamps the record `## Applied` when that run ends.
3. **One request, one item.** Do what the request names — the skill's own checks included (the project gate, the
   question pass, the description first) — and nothing beside it.
4. **Start nothing, commit nothing.** No stage, no `factory.sh run`, no `git commit`: the factory commits what the
   request wrote and runs the stories.
5. **Say what you did** in your last message — it is the request's output, read on the page.

A skill that cannot run for a request at all says why in its last message and writes nothing; the request then
ends as done with nothing committed, and the person reads why.

## The page — `factory.sh serve`

One HTML file with its script inline, shipped in the package, served by Python's `http.server`: the cockpit's tabs
(0 Describe, 1–5 Discover, Backlog, Run, Decide, Delivered), drawn from the factory's JSON views, a running stage's
or request's output as server-sent events. Every press writes a request (or calls `up` / `down`).

- **Bound to 127.0.0.1 alone.** Each checkout takes a port of its own — one derived from the checkout's path
  between 8700 and 8899, so a bookmark holds, and the next free one where another factory's page has it;
  `--port` names one. `.dca-factory/serve.json` records the pid, the port and the URL.
- **One script, by its hash**: the page's policy allows its own inline script alone (`script-src 'sha256-…'`).
- **A token per start**, in the URL (`http://127.0.0.1:<port>/?t=<token>`) and on every call; the `Host` header
  must name this server (no DNS rebinding); a write must carry this page's `Origin`, be JSON and at most 64 KiB; a
  refused write closes its connection.
  A view's argument is one id. Any other web page the browser has open can neither read the factory nor write a
  request.
- What it does not do: authenticate a person beyond `by:`. Whoever can open the URL on this machine acts as
  whoever they type into "as".
