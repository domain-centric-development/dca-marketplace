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
   python3 .agents/factory/story-gate.py --status
   ```

   It prints four sections — *running*, *waiting for a human*, *stories*, *cost*. Show it as it is;
   where the gate is not installed, say so and stop rather than reconstructing it by hand.
2. **Lead with what needs someone.** An open decision blocks its story and everything that depends
   on it: name it first, with the story it blocks, and point to `/factory-decisions` to answer it.
3. **Read "running" for what it is.** It means a stage started and its end is not in the journal. The
   journal cannot tell a running stage from one whose runner was stopped: say how long ago it
   started, and, when that is far longer than a stage takes, that it may have been interrupted.
4. **Explain a state from its files when asked.** "Why is STORY-3 blocked?" — the dependency it names;
   "why does STORY-1 run from document?" — its document gate has not passed yet. Read the file the
   state comes from before you repeat the reason.
5. **Give cost on request, in detail.** The status shows totals. For a story's stages run
   `python3 .agents/factory/story-gate.py --usage --story <id>`. Unmeasured invocations are unknown,
   not free; a session log has no price, so its cost reads `—`.

## Do not

- Do not run a stage, the runner, a gate for a stage or `--stage-start`/`--stage-end`. Looking is not
  taking over a story.
- Do not answer or edit a decision record — that is `/factory-decisions`, on the human's confirmation.
- Do not report a state from memory or from an earlier look; run the command again.
