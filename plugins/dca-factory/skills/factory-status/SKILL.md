---
name: factory-status
description: Shows where the delivery pipeline stands in this project — which stage is running, which decisions wait for a human, every story's state and what comes next, and what the stories cost in tokens — read from the project's files alone. Use when someone asks how a run is going, what the factory is doing, what is waiting, how far the backlog is, what a story cost, or on "/factory-status". Works from any session in the project, beside a running pipeline; it changes nothing and starts nothing.
---

# Show where the pipeline stands

Input: the project's files — the story journals under `tasks/<story>/.verify/`, the decision records
under `.agents/factory/decisions/`, the backlog. Output: an answer in the session. You write nothing,
start nothing and answer nothing on anyone's behalf.

## Do

1. **Run the one command.** From the project root:

   ```
   bash .agents/factory/factory.sh status
   ```

   (`python3 .agents/factory/story-gate.py --status` where the project has no runner copy.)

   It prints four sections — *running*, *waiting for a human*, *stories*, *cost*; the cost is a
   table with one row per story and the total. Asked about one story, run
   `bash .agents/factory/factory.sh status --story <story>` instead: the same look, with that story's cost
   per stage. Show it as it is; where the gate is not installed, say so and stop rather than
   reconstructing it by hand.
2. **Lead with what needs someone.** An open decision blocks its story and everything that depends
   on it: name it first, with the story it blocks, and point to `/factory-decisions` to answer it.
3. **Name a duplicate pipeline.** A `note:` line under *running* says the dca-factory plugin is
   enabled for the person while the project holds its own copy: stages run in a session may then
   pick the plugin's skills. Say so, and that the runner's stages see only the project's.
4. **Say whether a session listens.** `listening:` names the session that last looked at the backlog
   and when. A look within the hour means a listening session (`/factory-run` asking the schedule again; in
   Claude Code `/loop /factory-run`) is waiting for work; a long silence
   means it has probably ended — then the backlog is worked by nobody until someone starts one.
5. **Read "running" for what it is.** It means a stage started and its end is not in the journal. The
   journal cannot tell a running stage from one whose runner was stopped: say how long ago it
   started, and, when that is far longer than a stage takes, that it may have been interrupted.
6. **Explain a state from its files when asked.** "Why is STORY-3 blocked?" — the dependency it names;
   "why does STORY-1 run from document?" — its document gate has not passed yet. Read the file the
   state comes from before you repeat the reason.
7. **Give cost as the table says it.** The status shows each story and the total; `status <story>`
   shows the stages of one, with input, cache and output tokens, the time where the runner measured
   it, and the model each stage ran on — marked where the profile asked for another one that did
   not reach the stage. Unmeasured invocations are unknown,
   not free; a session log has no price, so its cost reads `—`, and `+` after a price means some of
   the invocations it sums named none.

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
