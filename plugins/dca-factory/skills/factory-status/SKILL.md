---
name: factory-status
description: Shows where the delivery pipeline stands in this project — which stage is running, which decisions wait for a human, every story's state and what comes next, and what the stories cost in tokens — read from the project's files alone. Use when someone asks how a run is going, what the factory is doing, what is waiting, how far the backlog is, what a story cost, or on "/factory-status". Works from any session in the project, beside a running pipeline; it changes nothing and starts nothing.
---

# Show where the pipeline stands

Input: the project's files — the story journals under `tasks/<story>/.verify/`, the decision records
under `.agents/factory/decisions/`, the backlog under `project/backlog/`. Output: an answer in the session. You write nothing,
start nothing and answer nothing on anyone's behalf.

## Do

1. **Run the one command, in the form this session renders.** From the project root:

   ```
   bash .agents/factory/factory.sh status --format md --live
   ```

   (`python3 .agents/factory/story-gate.py --status --format md --live` where the project has no runner
   copy.) `--format md` gives Markdown tables, which a session shows as tables; the terminal form
   (without it) is for a person at a shell. `--live` adds what the clock says: how long ago a stage
   started, its last activity, the worker, whether a session listens, a newer pipeline on this machine.
   Asked about one story, add `--story <story>`: its criteria, its passes (a correction after
   acceptance is a pass of its own), its stages with the time they worked and their tokens, its
   decisions.
2. **Show it as it is, and nothing after it.** The view is written to be read without you: what waits
   for a person first, then what runs, then the backlog by epic, and it ends with **Next** — the one
   thing to do now, with its skill. Do not retell the tables in sentences, do not reformat them, do
   not add an interpretation of the numbers, and do not repeat *Next* in your own words. Say more
   only when asked — the reason behind a state, read from the file it comes from ("why is STORY-3
   blocked?" — the dependency its story names; "why did test run three times?" — the journal and the
   decision records). Where the gate is not installed, say so and stop rather than reconstructing it
   by hand.
3. **What the marks mean**, if someone asks: 👀 look at it and accept it, ❓ answer a question (or
   release a draft), ⛔ stopped or interrupted, ⏳ running, ✅ delivered, ➖ nothing to do. The terminal
   uses `!` `?` `✗` `▶` `✓` `·` for the same, in colour.
4. **Name the part of the factory that is missing.** Also run
   `bash .agents/factory/factory.sh status --brief`: its lines say when the project description is
   missing (`/factory-setup`), when the backlog is empty (`/factory-backlog`), when the backlog still
   sits at the project root (the move to `project/`), and when detection finds something the stack
   profile does not declare (`setup --check`). Name what it says with the skill that fixes it.
5. **Read the live lines for what they are.** A stage *running* started and has no end in the journal;
   its `activity:` line says how long ago its session log last grew and its last tool call — the sign
   of life. A stage older than a stage may take is shown as ⛔ *interrupted?*. `listening:` names the
   session that last looked at the backlog: within the hour a listening session waits for work; a
   long silence means nobody works the backlog until someone starts it. A `note:` about a duplicate
   pipeline means stages run in a session may pick the plugin's skills; the runner's see only the
   project's.
6. **Cost is tokens.** A session log has no price, so the view shows tokens and says so once; a
   runner that reports a price adds a cost column. "not measured" is unknown, not free. The full split
   into input, cache and output per stage is `factory.sh status --usage`.

**Speak in skills.** You run the commands; the person gets the result and, for a next step, the
skill that does it (`/factory-status`, `/factory-decisions`, `/factory-run <story>`,
`/factory-backlog`) — never a shell command to type, unless the person asks how to do something
without a session. You may run `factory.sh` for everything that starts no tool — `setup`,
`backlog`, `status`, `decisions`, `update`, `verify`, `check` — but never `run`: it starts a tool
process per stage (`claude -p` and the like) on top of this session, and the runner refuses it
inside one anyway.

## Do not

- Do not run `factory.sh run`, a stage, a gate for a stage, or `--stage-start`/`--stage-end`.
  `status`, `decisions`, `backlog` and `setup --check` only read; nothing else here does.
  Looking is not taking over a story.
- Do not answer or edit a decision record — that is `/factory-decisions`, on the human's confirmation.
- Do not report a state from memory or from an earlier look; run the command again.
