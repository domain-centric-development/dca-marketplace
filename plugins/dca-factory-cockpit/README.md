# dca-factory-cockpit

**Claude Code only, optional.** The dca-factory cycle as a cockpit in a Claude Code pane — a function-hooks
plugin ("mod"). It draws what `factory.sh` prints and the project's files hold; it decides nothing, and the
factory works the same without it, in Claude Code, Codex or OpenCode.

```
[0 Describe]  setup  update  │ cycle ›  [1 Discover] [2 Backlog] [3 Run] [4 Decide] [5 Delivered]
```

| Tab | Shows | Acts |
|---|---|---|
| 0 Describe | the project description, each part present or missing, its missing and empty headings | `/dca-describe`, `/dca-describe <change>`, opens a file in the system's editor |
| 1 Discover | every discovery topic, its proposed epics (which are epics already), its proposed description changes | `/factory-discover <topic>`, `/factory-backlog epic <id> --from <report>`, `/dca-describe <file> — <section>: <change>` |
| 2 Backlog | every epic — also before its first story — newest first, with goal, outcome event; an epic opens with its intent, goal, outcome, domain contact, its own text and its stories with state, passes, time, tokens, cost, newest first (✎ open epic.md) | `/factory-backlog <words>`, `stories <epic>` (✦ suggest stories: Claude drafts them as `status: draft`), `release <story> …`, `/factory-run <wish>` |
| 3 Run | the worker — a factory `factory.sh up` started, or another runner holding the checkout, in place of the start buttons —, the requests waiting (`requests:`), the running stories with their stage, since when and the stage's last activity; a shared builder named with its stage (`builder · test`); the output of the worker started here, or else what the running stage reads, edits and runs (`factory.sh follow`) — whoever started it | starts `factory.sh run` / `run --watch` as a child of the session, stops it |
| 4 Decide | open questions and acceptances, answered records as Markdown; an open record with its options as choices; a story waiting for its merge, with what to do; other factories' claims — who, how long, a stale or orphaned one or an id collision with its release command; the judge's open findings, each in plain words first, then who saw it, the reviewer's defect and the fix | `/factory-decisions <story>`, `/factory-decisions <story> <record>: answer <option \| your words>` (✦ one button per option, the recommended one marked; accept or correct an acceptance); a finding opens its `findings.md` or goes to `/factory-backlog` (✦ to backlog — the skill decides what it becomes). Taking a claim away stays a command for a terminal — no button |
| 5 Delivered | the project's figures — kill rate, guarded rate, domain findings and corrections by code, the factory's own line —, delivered stories, the newest delivery first, epics with their outcome events, their figures and unguarded journeys | `/factory-verify <story>`, `/factory-backlog journey <epic>` (✦ add guard beside an unguarded epic, also under Journeys in 2 Backlog) |

A story opens with a short head — its title, its state and the one line the factory says about it (`situation`:
what runs, what waits, why it is superseded, when it was delivered) — and two views beside each other, `s` Story and
`p` Pipeline; the factory names the one to open with (`view`: the pipeline while the story runs or waits for the
person, the story before it starts and once it is done or set aside), a press switches. Story is every section of
its `story.md` in the factory's order — why it is not built framed first, then its own words, its criteria as
compact scenarios (the rule each serves, its title, its Given / When / Then) where they stand, its changed
expectations, assumptions and notes — and a button that opens its `story.md`. Pipeline opens with the story's signals —
questions, assumptions, what the plan left open, its rules' verdicts, the judge's findings and corrections by code, as
the gates recorded them in the journal ("not recorded" or "not measured" where none did, never 0) —, then the factory's numbers per stage — a shared builder's and verifier's stages beneath
them, with their share of the cost, their tokens by class (input, output, cache write, cache read), and the calls each was denied (a headless stage has nobody to grant one) — its passes, its history by day, its hand-overs, the output of every process it ran
(what each read, edited and ran, through `factory.sh follow --process`; "cleared" once the factory removed the raw
streams some days after the delivery — the journal keeps the record) and its decision records. A reviewer
appears there only for a perspective the profile asks for now — the status names them (`perspectives`); one an
earlier profile named, such as an old `review:dca`, stays out.

## The band above the prompt

While something waits for the person or runs, the cockpit draws a band directly above the prompt — whether the pane
is open or not; the status line says the same in one line. One row per item, as many as the band holds, the rest
counted (`n more in the cockpit`):

```
FACTORY  1 waits for you · 1 running                                  [ cockpit ]
? add-book — plan asks a question                              [ ✦ answer ]  open ›
▶ lend-book · builder · test — 3 min — Edit LendBook.java          output ›  [ ■ stop ]
```

| Row | Acts |
|---|---|
| what waits (`status.waiting`) | ✦ its own press, as in Decide (`/factory-decisions <story>` …) — `a` for the first; `open` opens the story in the pane. A row the factory says in words only (a story waiting for its merge) offers no press |
| what runs (`status.running`), or the worker started here between stages | `output` opens the Run tab; `■ stop` (`x`) stops the worker started here |
| the head | `cockpit` (`o`) opens the pane as it stood |

The band takes the keys after a click into it or `ctrl+x tab`; `ctrl+x ctrl+a` or its `[-]` collapses it. It is
quiet — the engine's own band shows — while nothing waits or runs, while a survey holds the band, and in a project
without a factory. It draws in the pane's palette and wordmark, on the terminal and in the Desktop app (the two
surfaces that have the band); like every press of the cockpit, an answer goes to `/factory-decisions`, which writes
the record — the band writes nothing.

## Beside the pane

- **What Claude is told.** With a prompt the person sends, Claude reads where the factory stands — what runs, what
  waits for the person, what comes next — as context beside the prompt, never in the system prompt (which would
  break the prompt cache on every change). It is attached only when it changed since it was last attached; a slash
  command carries none.
- **A tool for Claude.** `factory_status` (`mcp__dca-factory-cockpit__factory_status`) answers with `factory.sh`'s own
  JSON, read-only and without a shell: the status cut to what runs, waits and comes next, the queue, the epics and the
  totals and the project's figures (`signals`); `full: true` the whole status; `story` or `epic` one item's view; `decisions: true` the records.
- **`/factory-cockpit status`** prints where the factory stands into the transcript — the text Claude reads, drawn
  as a small framed panel in the cockpit's palette with the same items and presses as the band and the project's
  figures, as it stood when it was read. A status from a resumed session keeps the plain text.
- **Since the last session.** The cockpit keeps what a session saw per project (`$.store`); the next session's first
  reading says in a toast what moved meanwhile: `factory since 22.10.2026 17:05 UTC: 3 delivered (…) · 1 new for you (…)`.

## What it reads

`factory.sh status --format json --live`, `status --story <id> --format json --live`, `status --epic <id> --format json`,
`decisions --format json`,
`discover --list --format json`, `follow --once --format json` — and the append-only journals and hand-over files under `.dca-factory/runs/`. A
project whose pipeline is older than these views gets a line saying so and a button for `/factory-update`.

Every order and every selection it shows is the factory's: the epics and an epic's stories newest first, the
delivered stories newest delivery first (`delivered_order`), what waits and what comes next — the cockpit draws them
as given. A story's and an epic's details are drawn from the same blocks (the line of what is up, labelled fields, the view
switch, the item's sections, its criteria or its stories, the button that opens its file), the same in every tab
that opens one. An epic is one page without a switch: its head (title, progress, intent, goal, outcome, domain),
its line, the sections of its `epic.md` the head does not already say, then its stories newest first — where the
factory places them.

## How it acts

A button or field marked ✦ hands the work to Claude in this session: a skill runs and may write files. The
others only show or open something, or start the worker (▶).


A press sends the matching slash command into the session through `$.command.run`, as if the person typed it
(Claude Code refuses a plugin prompt that begins with `/`); a press on Run starts `factory.sh run` with
`FACTORY_ALLOW_NESTED=1`, the runner's own switch for a deliberate start inside a session. Ending the session or
reloading the plugin stops that worker; the runner gives its claim on the workspace back. One worker at a time:
a second press while one starts does nothing.

The cockpit reads the factory every 20 s, after every turn and after every write under `product/` — in the
background, so no tool result and no turn waits for it. One reading runs at a time; one asked for meanwhile is
served right after it. With the pane closed only the status is read, for the status line; a story's journal and
hand-overs are read again only when its row changed or a stage of it runs.

## Install and use

```
/plugin install dca-factory-cockpit@dca-marketplace
/factory-cockpit
```

`0` opens Describe, `1`–`5` the cycle, ↑↓, Tab and Shift+Tab move, `b` goes back, `q` or `ctrl+x x` closes the pane (`/factory-cockpit close` from the prompt; `/factory-cockpit status` prints where it stands), `Esc` returns to the prompt. ← and → are Claude Code's own — a mod receives no left or right arrow. The pane has the keyboard after
`/factory-cockpit`, a click into it, or `ctrl+x tab` — the last two only while the prompt is empty.

## Terminal and Desktop

The same data and actions on every surface; each draws what it draws best (`e.surface`). The terminal keeps its
monospace grid: rules under table headers, bars and the wordmark as text. The Code tab of the Desktop app (and the
editor and the mobile app) draws a proportional font: the tables keep their column bars but no header rule, a mark
gets two cells, the Hex Graph stands before the wordmark and progress shows as a vector bar. A Markdown file opens in
the surface's own renderer there; a story's diff opens in the highlighter's diff view everywhere.

## Early access

Function hooks are an early-access surface of Claude Code and may change between releases; this plugin keeps its
own version so it can follow them without touching the factory. Tests: `claude plugin test plugins/dca-factory-cockpit`.
