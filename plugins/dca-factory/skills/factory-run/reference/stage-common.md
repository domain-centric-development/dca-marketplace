# What every stage holds to — said once

The six stage skills (`stage-plan`, `stage-test`, `stage-build`, `stage-tidy`, `stage-judge`,
`stage-document`) share these rules. Each skill names them in one line and points here; a shared
builder that carries four stages reads them once, not four times. The stage-specific part — which
profile key names the carrier, which `stage:` a decision record carries — stays in the skill.

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
**decision record**: `decision: <story>-<nn>`, the record at `<story>.decisions/<nn>.md` beside the
story (`nn` — the next two-digit number among this story's records) with the question, the options
you see, the evidence you read and your recommendation — never an answer. The full shape is
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
and the ordinary reading and text tools — `sed`, `grep`, `find`, `xargs`, `cat`, `ls`, `head`, `tail`,
`wc`, `sort`, `diff`, `mkdir`, and `git status`, `git diff`, `git log`, `git ls-files`, `git apply
--check` (how a break patch is tried). Everything else asks, and in an unattended run nobody answers:
the call is refused and the turn is lost. A file is changed with the editor tools, never with a script
fed on stdin (`python3 -` and a heredoc) — that is the one habit the bench saw refused three times per
story. In a session the same tools are the ones a person answers "yes" to without looking twice.

## The formatter runs last

Where the stack profile declares `formatFix:`, run it last, before you finish: it corrects the
formatting of what you wrote, so the stages after you find their own files as the formatter wants
them. The gate and the commit hook only check `format:` and change no file. A file the formatter
touches that this story never changed is not yours to keep quiet about — the pipeline's record of
what changed names it, and the judge reads it as the finding it is.
