# What every stage holds to — said once

The stage skills (`stage-plan`, `stage-test`, `stage-build`, `stage-tidy`, `stage-judge`,
`stage-document`, `stage-integrate`) share these rules. Each skill says to read this file first; a shared
builder that carries four stages reads it once, not four times. The stage-specific part — which
profile key names the carrier, which `stage:` a decision record carries — stays in the skill.

The runner's prompt names the skill, the story and where things are — the paths, the commands, the
reports of an earlier round — and nothing else. What a session does with them is said here.

## A session the runner started

A prompt that begins with *Apply the stage-… skill*, *Carry out these stages* or *Review the change*
comes from the pipeline's runner. Then:

- The runner holds the checkout for this session: the worker named at session start is the one that
  started you, not a second writer.
- The run folder the prompt names is where every hand-over goes. The evidence folder it names — the
  journal, the diff, the gate's reports — is written by the gate and the runner and only read by you, as
  the pipeline and the skills are.
- What the gate checks in a stage's file, in a page, is `factory-cli.py --contract <stage>`, the command
  the prompt names. Read that, never the gate's source.
- Where the prompt names a knowledge skill's catalog, open its `index.md` first. Where it names nodes to
  read once before you write code, read them before the first line: they hold what you would otherwise
  look up in a dependency's sources or a package cache, which is never the place.
- Where the prompt names this story's own worktree and the main checkout, you work in the worktree, on
  its branch: change the code there, never in the main checkout. The story with its decisions, the run
  folder, the pipeline and the skills are linked from the main checkout; write a decision record or a
  hand-over at the path you are given.
- A guard the prompt names is the profile's `carrier.guard` (*The guard beside the carrier*, below).

## A stage on its own

A prompt that names one skill — *Apply the stage-<stage> skill* — asks for that one stage (or step).
Do it yourself in this session; do not delegate it. Do not run other stages. Read only the story and
the files the skill names as its input, and write its output file in the run folder.

## One session, several stages

A prompt that says *Carry out these stages* names them in order. Apply each stage's skill in turn, in
this one session, reading only the story and the files that stage's skill names as its input, and
writing its output file in the run folder. Run only the stages the prompt names.

- After the test, build and tidy stages run that stage's gate — the command the prompt names, with
  `--stage <stage> --brief` — and fix exactly what it names before the next stage, at most three
  attempts per stage.
- Before you write `plan.md`, run the plan skeleton the prompt names: it writes the plan's headings and
  one line per criterion key — give each its level, never retype the story's text.
- Before you write `tests.md`, `build.md` or `tidy.md`, run the files skeleton the prompt names: it
  writes the file's list of changed files from the tree (or adds the missing ones to a file you wrote).
  Fill in the rest, never the list, and run the stage's gate only when the file is filled — never on
  the bare skeleton.
- Each hand-over says what the next stage needs and nothing a reader has elsewhere;
  `--contract <stage>` names its measure.
- Stop at once when a stage ends in a `## needs-human` section.
- Where the stages include build: if a test cannot pass for a reason in its own code (a helper, a
  locator), not in what it asserts, write `build.md` with the finding first, then go back to the test
  stage in this session — repair the test without changing what it asserts, write its break, run the
  test gate — and build again. A change to what a test asserts stays a needs-human question.
- Where the stages are judge and document: apply the stage-judge skill first and write `judge.md` with
  its verdict. Then — only when it says `verdict: pass` — run the document skeleton the prompt names and
  apply the stage-document skill: fill the skeleton's tables, cite paths from its `## Paths` section in
  exactly that form, run the document gate the prompt names and fix exactly what it names, at most
  three attempts. With any other verdict stop after `judge.md`; write no `document.md`. Change no code.

## A repeat round

The prompt names what an earlier round left; each is an input of this one.

- *The gate refused this stage before* (or *stage <stage>*): its report — read it and fix exactly what
  it names in that stage, nothing else.
- *The <gate> gate refused the story and sent it back to* this stage (or *stage <stage>*): fix in that
  stage exactly what its report names, nothing else.
- *The build stage sent the story back*: `build.md` names a defect in a test's own code — the test
  stage repairs exactly that, without changing what the test asserts, and writes the test's break
  (see the contract).
- *The judge asked for changes*: each stage fixes exactly the confirmed defects in `judge.md` that are
  its own — a test that asserts too little is the test stage's, with its break (see the contract); the
  code is the build's — nothing else.
- *The previous verdict*: the judge accounts for each defect it confirmed under `## Previous round` —
  fixed (with the evidence) or withdrawn (with the reason) — before judging anew.

## A review the runner started

A prompt that says *Review the change … from the <perspective> perspective* names the review skill, the
diff, its inputs and the report's path. Apply the skill to the diff — open a whole file only where the
diff's context does not carry the question. Write the report in the skill's own format: `## Findings`
with must-fix, should-fix and nits, every finding with the file and line it stands on and a one-line
fix; say plainly when you found nothing. Change no other file and no code; you are one of several
reviewers, a judge reads the reports.

## Ask, do not recall — but only a source the project named

Where the stack profile names a **knowledge skill** — `knowledge: <skill>`, one that answers
architecture questions from a catalog and cites the node it read — use it instead of your own
recollection whenever the answer would decide something: which pattern applies, why a rule exists,
whether a construct is a pitfall, what a recipe prescribes. Name the node you relied on in your
file, the way you name a file and line for a claim about the code: by its path inside the catalog
(`recipe/add-an-aggregate.md`), never by a path into a skill folder.

**Never adopt a knowledge source the profile did not name.** A catalog that happens to be installed
may be a vendored copy of an older release: its rule ids, marker names and recipes can describe a
version the project does not use, and a citation makes that wrongness look verified. If you notice
such a skill, say so in your file — "`<skill>` is available but not named in the profile, so it was
not used" — and decide from the project's own rules, markers and documents instead. Those are the
source of truth; a catalog is a convenience the project has to vouch for.

Without a `knowledge:` entry, work from what the project itself carries: its rule catalog and the
report its architecture suite prints, its building blocks, its glossary, its documents. Nothing
here fails for the absence of a knowledge skill.

## Who carries a stage

The stack profile may name a carrier for a stage — `carrier.<stage>: <name>` — the skill or agent
that holds this project's craft for it. A **skill** works in every tool; an **agent** only where the
tool has agents. Use the named carrier when this tool offers it; otherwise do the stage as its skill
describes and say in your file which it was ("in-session; `<carrier>` not available here"). A
missing carrier is a missing preference, never a reason to skip the stage.

**The guard beside the carrier.** For the stages that write production code — build and tidy — the
profile may also name `carrier.guard: <name>`: the skill that holds the architecture's invariants
while code is edited (in a DCA project `dca-discipline`). Apply it for every file you write, the same
way you use the carrier: where this tool offers it; otherwise keep the invariants as the stage skill
describes them and say so in your file. An absent key is skipped and named like any other.

## A question is a decision record

A stage that cannot go on writes its file anyway, with a `## needs-human` section naming a
**decision record**: `decision: <story>-<nn>`, the record at `<story>/decisions/<nn>.md` in the
story (`nn` — the next two-digit number among this story's records) with the question, the options
you see, the evidence you read and your recommendation — never an answer. The story file and every
`## Answer` are the person's: the window's end compares them with its start, and a change stops the story
until a person confirms it. The full shape is
`factory-run/templates/decision.md.tmpl`, beside this file; the gate reads exactly this front matter,
and a record without `id:` equal to the file name is refused:

```markdown
---
id: <story>-<nn>
story: <story>
stage: <the stage that will apply the answer>
asked: <now, UTC, ISO 8601>
---

# <the question in one line>

## Question
## Options
## Recommendation
```

The gate refuses a `## needs-human` that names no record. When you run again on a story whose
record is answered — asked by your stage, or answered `applies: <your stage>` — read the answer,
apply it, and cite the id in your file where it landed (`Decision <id> answered <option>: …`); the
gate stamps the record applied only then, and refuses a file that does not cite it.

## The gate is your test run

For the stages that write code — test, build, tidy: run a single test while you work, as often as
you like; when you believe the stage is done, run the stage's gate (`story-gate.py --story <id>
--stage <stage> --brief`). It compiles the sources and runs every mapped test and the required
suites once per command, the architecture suite and the formatter, and fails on exactly what is
red. Its refusal quotes the failing test's own output, the assertion included — there is nothing a
suite run of your own would show you that the gate's report does not. Do not run the whole suite
yourself before it: the gate runs the same commands, and a stage that runs them first pays twice for
one answer. Do not finish while the gate names something red — and write nothing about the gate into
your file: its report is the record, and a stage edits no hand-over after the gate ran. A `gate:note`
(a size, an older contract) is information for whoever maintains the pipeline; it is never a reason
to edit your file after the gate ran, and never a reason to run the gate again.

## The shell a stage has

The runner lets a stage run, without asking, the gate, the cli, the commands the stack profile declares,
and the ordinary reading tools — `cd`, `ls`, `cat`, `head`, `tail`, `wc`, `sort`, `grep`, `diff`, `pwd`, and
`git status`, `git diff`, `git log`, `git ls-files`, `git apply --check` (how a break patch is tried); the
prompt names the list. Nothing that writes: list files with Glob, search with Grep, write with Write (it makes the folders). Everything else asks, and in an unattended run nobody answers:
the call is refused and the turn is lost. A file is changed with the editor tools, never with a script
fed on stdin (`python3 -` and a heredoc) — that is the one habit the bench saw refused three times per
story. In a session the same tools are the ones a person answers "yes" to without looking twice.

Every command is checked part by part before it runs, and nobody is there to grant one: a loop, a
variable or `$(…)`, a part outside that list and a path outside the project are refused, each a turn
spent. Run one plain command per call from the project root, never a `cd` to an absolute path; read
files with Read — several in parallel calls, never a loop over them. Every turn sends this whole
session again, so put the calls that do not wait for each other's result into one turn: the files you
read, the searches you run, the files you write that do not depend on one another.

## The formatter runs last

Where the stack profile declares `formatFix:`, run it last, before you finish: it corrects the
formatting of what you wrote, so the stages after you find their own files as the formatter wants
them. The gate and the commit hook only check `format:` and change no file. A file the formatter
touches that this story never changed is not yours to keep quiet about — the pipeline's record of
what changed names it, and the judge reads it as the finding it is.
