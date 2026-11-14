# Execution tiers

Part of the `factory-run` skill: what its *Execution tier* section points to — the three tiers and what each one
carries, the shared builder and verifier, the reviews beside each other, and the stage marks a session sets.

Who runs the stages is the human's choice, not yours, and it decides what the run costs and where:

| Asked for | Stages run | Tool processes |
|---|---|---|
| `/factory-run [story]`, "deliver STORY-1", `/loop /factory-run` | **in this session** — a subagent per stage where the tool can start one and it comes back, otherwise in-session | none beyond this session |
| the person runs `factory.sh run [--story X]` in a shell | **the runner**, one process per stage | one per stage |

The runner — `factory.sh run` — is the person's, never yours: it starts a tool process
per stage on top of this session, and refuses to inside one. Asked for "one process per stage", "unattended" or "in the
background", say that this is the runner and that they start it in a shell. Say in the report which
tier ran.

- **subagent per stage**: the stage gets the story and its predecessor file as its whole input and a
  fresh context of its own — the isolation the runner gives, without a process per stage.
- **in-session** where the tool has no subagents: you carry out the stage assignment yourself, in
  order, reading only the story and the predecessor file for that stage — not what you remember
  from earlier stages. The file contract plus the gate is what keeps this honest.
- **the runner**: it calls the tool once per stage, and each stage process sees only the project —
  its skills, the carriers the profile names, its settings — not the person's plugins or MCP
  servers, with one prefix shared by every stage. So every stage begins with an empty context by
  construction; it applies the gates, the judge's verdict, the round counter and the file checks
  itself, and records each stage's cost with its price. Per-tool flags (a model, an effort level, a
  sandbox) come from the environment — `FACTORY_CLAUDE_ARGS`, `FACTORY_CODEX_ARGS`,
  `FACTORY_OPENCODE_ARGS` — because they are the tool's configuration and never the process's.

**Shared stages — the default.** Plan to tidy run in one context (the "shared builder", window
`builder`), judge and document in another (the "shared verifier", window `verifier`) — never in one: the
judge's independence from the builder is the point of the split. The profile's `stages: separate`,
`factory.sh run --separate-stages` or `FACTORY_SHARED_BUILDER=0` / `FACTORY_SHARED_VERIFIER=0` separate
them. `reference/shared-stages.md` says what each process carries, how a session marks its window and
what to check after the end mark — read it before running either in a session. Say in the report which
variant ran.

**The reviews run beside each other, before the judge.** In every tier the judge converges from one
review file per perspective — `.dca-factory/runs/<story>/reviews/<perspective>.md`, the three built-ins
plus the profile's `reviews:`, each written by the carrier `review.<perspective>:` names — instead of
reviewing in its own context. The runner starts one tool process per perspective **at once** and waits
for all before the judge (an adoption gets none: nothing was built); each is a `review:<perspective>`
window in the journal with its cost. In a session, start one subagent per perspective at once where
the tool has them — the reviewer agents the craft plugin carries are these — each writing its file;
without subagents, run each review skill in-session one after another and still write the files. A
perspective without a file is the judge's own pass, named so under `## Perspectives covered`; the
document gate notes a missing file and refuses one without a findings section (`reviews`).
`factory-cli.py --perspectives` lists the perspectives with their carriers; `--contract review` the
file's shape.

In the subagent and in-session tiers, mark every stage so its cost is known: run
`python3 .agents/factory/factory-cli.py --stage-start <stage> --story <id>` right before it and
`--stage-end <stage> --story <id>` right after its file is written. The gate records the window in
the story's journal and reads the tool's own session log for it later — Claude Code's log of this
session, subagents included, or Codex's — so `--usage`, the schedule and a budget see in-session
stages the way they see the runner's. A mark without a log it can read records the stage as
unknown. Do not work on anything else between the two marks: the window counts everything the
session did in it. The marks also record what the stage changed — the start its tree, the end the
changed-files record — so call the stage's gate **after** `--stage-end`: a gate inside the window
(a stage checking its own work) skips the files check and says the stage is still open. `--stage-end`
exits 7 where the story file or a `## Answer` changed inside the window: stop the story and tell the human —
`factory-cli.py --owned-confirm <id>` is theirs to run once they looked.
