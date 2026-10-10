# Several stories

Part of the `factory-run` skill: what its *Several stories* section points to — the schedule, one story with
unfinished code per checkout, the runner's worktrees and loop, where a story starts, what a running stage does,
and what a story cost.

One story per run; several stories are a loop over it, never two builders working in parallel on one
code base. What comes next is read off the files, like everything else:

```
python3 .agents/factory/factory-cli.py --schedule
```

prints each story with its state — `delivered` (its document gate passed), `waiting` (an open decision record), `resumable`
(answered, with the stage that applies the answer), `in-progress` (with the stage it continues from: a refused
gate's stage, else the first missing file), `ready`, `stopped` (three rounds, a story conflict, a
refused plan gate, a `## needs-human` without a record), `blocked` (a dependency not delivered,
unknown or on a cycle, or an epic its epic depends on not delivered), `unreleased`/`superseded` — and ends with
`next: <story> <stage>` or `next: none — <why>`. Order: `depends_on`, ties by the epic's place (its own
`depends_on:`, then its id), then by id.

**One story with unfinished code in this checkout at a time.** In a session the stages run here: a story
that got past its plan stage (it has `tests.md`) and is not delivered holds the checkout — it is next if it
can run, and while it waits or is stopped no other story starts, because the next one would build on its
tests and code. A story that stopped with a question at its plan stage wrote no code, so independent
stories run past it.

**The runner gives every story a worktree of its own** (`.dca-factory/worktrees/<story>/`, branch
`story/<id>`): its code waits there, so a story waiting for an answer or an acceptance holds nothing and the
next one starts. The worktree links what is state to this checkout — the stories with their decisions, the
run folder, the pipeline, the skills — and `FACTORY_HOME` names this checkout to the gate and the cli, so
both read every place from here. A story is delivered when it is integrated: the integrate step merges the
main line into its branch (the `stage-integrate` agent where git stops on a conflict), squashes it to one
commit, runs the integrate gate on that tree — the tidy gate's checks once more, no conflict marker left —
and fast-forwards this checkout's branch; then its worktree and branch go. `--parallel <n>` runs up to `<n>`
stories at once. A story the runner started in its worktree is not taken up in a session: run it with
`factory.sh run --story <id>`.

The runner — the person's, in a shell — does the same loop: `factory.sh run [--tool <t>]` without `--story` runs the next story from the stage the
schedule names, asks again, and ends when nothing can run. A story that stops for a decision does
not end it (`run` exits 3 there); any other stop does, because retrying a failure spends a run on
the same refusal. `--watch` keeps it waiting while a story waits on a human: it re-reads the
schedule every `--interval` seconds (default 60, 1–3600), invokes no agent while nothing changed,
and resumes the answered story at the stage that applies the answer. `--max-stages <n>` caps the agent
invocations of the run (exit 4, the work so far stays); `.dca-factory/stop` ends it before the
next story.

`factory.sh run --story <id>` without `--from` starts where that story's files say, as the schedule
would: `python3 .agents/factory/factory-cli.py --story <id> --start` prints its `state:`, `start:` and
`detail:`. A delivered story runs nothing; one that waits, is blocked by a dependency or another
story's unfinished code, or stopped, runs nothing and says why — `--from <stage>` is the person's way
to run it anyway, and starts a new count of rounds. An accepted story starts at the document gate
and is delivered without a stage invocation. Resumed at a gated stage whose file exists, the runner
lets the gate decide first on today's tree: a file that holds costs no invocation, and a stage that
does run reads a report of now.

**What a running stage does.** The runner keeps each stage's tool output as the tool writes it, one event
per line, in `.dca-factory/evidence/<story>/<stage>.<time>.out`. When the person asks what a stage is
doing, run `bash .agents/factory/factory.sh follow --once` (or `--story <id>`) and show its lines — what
the stage reads, edits and runs, its answers, its turns and cost at the end; `follow` without `--once`
keeps printing for a person at a terminal; `--process builder` (or `verifier`, `review-ddd`, …) one process,
`--all` every process of a story — also of a delivered one. It starts nothing.

**Inside a shared process.** `factory.sh status --story <id>` shows a shared builder's or verifier's
stages beneath it, split where it loaded each stage's skill: time and tokens from its stream, output and
cost marked `≈` because the process reports them once; `status` names the stage a running builder is in.

**What a story cost.** The runner asks Claude Code and Codex for their machine-readable output and
records each invocation's tokens — input, cache read, cache write, output, and Claude's cost — as a
`usage` line in the story's journal. `python3 .agents/factory/factory-cli.py --usage [--story <id>]`
sums them per story and stage, repeat rounds included; the schedule shows each story's total.
`--story-budget <tokens>` (on `run`, with or without `--story`) stops dispatch once a story has used that many,
counted from the journal, so a restart or a second session continues the same count; the stage
that crosses the line still finishes, because usage is known only after it ran. A tool that reports
nothing — OpenCode today, a custom `FACTORY_TOOL_CMD` without `FACTORY_USAGE_FORMAT` — is shown as
invocations without a report, never as zero. An in-session run is measured through the stage marks
(the skill's *Execution tier*); a session log carries tokens but no price, so its cost reads `—`, not 0.
Its numbers are copied into the journal once a window is five minutes old, by the next command that
writes — a stage start, a claim, a release, a listening look — for every story; until then the journal
holds only the session's id, and a story's last stages are frozen by whatever runs next.
An old session log can be read whole: `factory-cli.py --usage-from claude-session|codex-session <log>`. The watch lives as long as its process: a closed session or terminal ends it, and a
file wakes nobody. In-session, do the same loop yourself — ask the schedule, run the story it
names, ask again — and stop instead of waiting.
