# Running a stage

What `factory-run` does around each stage it runs — in the runner and in a session alike. The skill names this
file; read it before a stage runs in a session.

**A defect in a test goes back to the test stage.** Two stages can send a round there, with a line
`back: test`: the judge, when a test asserts less than its criterion, and the build, when a test cannot
pass because of its own code (a helper, a locator) while what it asserts stays the same. The build may
change no test, so without this way back it would have to ask a human about a repair that changes no
expectation. The repaired test is green — the code already meets it — so the test gate asks for its
break instead of a red run. A change to what a test asserts stays a human's question. A merge of the main line
that changed one of the story's tests after it was seen failing sends the story to the test stage the same way,
by the runner's own step: build and tidy never start on a stale red proof. Tidy's own moves in the story's tests —
a copy lifted into the support, a page object instead of a raw locator, what each test asserts kept — are the one
exception: its gate runs each moved test on the tree the test stage left (`red-tree`) and takes the new version
where it is red there (`red-reproof`).

**What a stage is told, so it searches for nothing.** Every stage prompt names the skill, the story and
where things are: the stack profile, the story's run folder and evidence folder, the knowledge skill's
catalog where the profile names one, `factory-cli.py --contract <stage>` — the exact shape the gate holds
that stage's file to, in a page, from the gate's own constants — the reports of an earlier round, and
the path of `reference/stage-common.md`. What a session does with them is said there, once, for every
stage, and the stage skills say to read it first — so a stage in a session and a stage the runner
started hold to the same text. A stage that runs its own gate runs it with `--brief`: what passed is one
line, what did not stays verbatim. Before the document stage the runner writes the stage's file as a
skeleton (`factory-cli.py --document-skeleton <story>`) with every changed path and run file
root-relative under `## Paths`; in a session run it yourself before the stage, and cite from it. The
prompt also names the shell the stage has without asking — the gate, the cli, the profile's commands
and the ordinary reading and text tools (`reference/stage-common.md`, *The shell a stage has*, which
also says that a file is changed with the editor, never with a script on stdin): in an unattended run a
refused command is a lost turn, nothing more, and the bench counted three per story before the list
carried what a stage reaches for.

**A model per stage.** The profile may name one: `model.<tool>.<stage>`, or `model.<tool>` for
every stage. The runner passes it as the tool's model flag. In the subagent tier, start the stage's
subagent on that model where the tool lets a subagent take one (Claude Code's subagents take an
alias such as the ones the profile names; a full model name the subagent tool does not accept runs
on the session's model). In-session the model cannot change. `--stage-start` records the request
either way, and the status shows a stage whose model is not the one requested — so a request that
had no effect is visible, not assumed.

## A question is a file

A question is a **file**, not a sentence in a report: the stage writes
`<story>/decisions/<nn>.md` in the story's folder from `templates/decision.md.tmpl` — the question, the
options, its recommendation, never an answer — and names it in its `## needs-human` as
`decision: <id>`. That is what makes the question survive the session and reach whoever answers
it, in this session or another (see `reference/file-contracts.md`, *Decision records*). When you
resume a story whose record is answered, run the stage it resumes at — the earlier of `stage:` in the
record and `applies:` in the answer — with the answer in front of it; the gate checks that its new file cites the id, and stamps the record
applied. The human answers through `factory-decisions` — in this session or another — which lists
the records (`factory-cli.py --list-decisions`), explains one and writes `## Answer` only on their
confirmation.
