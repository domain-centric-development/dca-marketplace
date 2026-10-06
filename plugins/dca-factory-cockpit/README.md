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
| 2 Backlog | every epic — also before its first story — with goal, outcome event, its stories with state, passes, time, tokens, cost | `/factory-backlog <words>`, `stories <epic>` (✦ suggest stories: Claude drafts them as `status: draft`), `release <story> …`, `/factory-run <wish>` |
| 3 Run | the worker, the running stories with their stage, since when and the stage's last activity; a shared builder named with its stage (`builder · test`); the output of the worker started here, or else what the running stage reads, edits and runs (`factory.sh follow`) — whoever started it | starts `factory.sh run` / `run --watch` as a child of the session, stops it |
| 4 Decide | open questions and acceptances, answered records as Markdown | `/factory-decisions <story>` |
| 5 Delivered | delivered stories, epics with their outcome events, unguarded journeys | `/factory-verify <story>`, `/factory-backlog journey <epic>` (✦ add guard beside an unguarded epic, also under Journeys in 2 Backlog) |

A story opens with its pipeline, the factory's numbers per stage — a shared builder's and verifier's stages beneath
them, with their share of the cost, their tokens by class (input, output, cache write, cache read), and the calls each was denied (a headless stage has nobody to grant one) — its passes, its history by day, its hand-overs, the output of every process it ran
(what each read, edited and ran, through `factory.sh follow --process`) and its decision records.

## What it reads

`factory.sh status --format json --live`, `status --story <id> --format json --live`, `decisions --format json`,
`discover --list --format json`, `follow --once --format json` — and the append-only journals and hand-over files under `.dca-factory/runs/`. A
project whose pipeline is older than these views gets a line saying so and a button for `/factory-update`.

## How it acts

A button or field marked ✦ hands the work to Claude in this session: a skill runs and may write files. The
others only show or open something, or start the worker (▶).


A press sends the matching slash command into the session through `$.command.run`, as if the person typed it
(Claude Code refuses a plugin prompt that begins with `/`); a press on Run starts `factory.sh run` with
`FACTORY_ALLOW_NESTED=1`, the runner's own switch for a deliberate start inside a session. Ending the session or
reloading the plugin stops that worker; the runner gives its claim on the workspace back. One worker at a time:
a second press while one starts does nothing.

The cockpit reads the factory every 20 s, after every turn and after every write under `project/` — in the
background, so no tool result and no turn waits for it. One reading runs at a time; one asked for meanwhile is
served right after it. With the pane closed only the status is read, for the status line; a story's journal and
hand-overs are read again only when its row changed or a stage of it runs.

## Install and use

```
/plugin install dca-factory-cockpit@dca-marketplace
/factory-cockpit
```

`0` opens Describe, `1`–`5` the cycle, ↑↓, Tab and Shift+Tab move, `b` goes back, `q` or `ctrl+x x` closes the pane (`/factory-cockpit close` from the prompt), `Esc` returns to the prompt. ← and → are Claude Code's own — a mod receives no left or right arrow. The pane has the keyboard after
`/factory-cockpit`, a click into it, or `ctrl+x tab` — the last two only while the prompt is empty.

## Early access

Function hooks are an early-access surface of Claude Code and may change between releases; this plugin keeps its
own version so it can follow them without touching the factory. Tests: `claude plugin test plugins/dca-factory-cockpit`.
