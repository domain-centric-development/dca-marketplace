# dca-factory

The **delivery pipeline** for a Domain-Centric Architecture project, in three parts: a **project
description** (what is to be built), a **backlog** of epics and stories, and a **runner** that works
through them — six stage skills with file hand-overs, a deterministic story gate between them and
one orchestrator. How it grew, version by version: [`CHANGELOG.md`](CHANGELOG.md).

```
dca-factory.profile.yaml   the stack profile — the person's, committed; the one fixed path
project/                   what is to be built (a person writes it)
  product.md               what, for whom, surfaces, qualities, what it is not
  tech.md                  stack, frontend approach, persistence, runtime, integrations, version policy
  domain.md                the designed cut: contexts, subdomain types, relationship patterns and why
  epics/<epic>/epic.md · <story>/story.md · <story>/decisions/<nn>.md · <story>/findings.md
.agents/factory/           the installed pipeline (gate, cli, runner, hook) — factory-update owns it whole
.dca-factory/runs/<story>/ the run's protocol: hand-overs, marks, journal — disposable
.dca-factory/worktrees/<story>/  the runner's checkout for one story, on its branch story/<id> — gone once integrated
docs/                      what exists and why — written after the code; generated maps live here
```

One owner per place. `project/` is the people's: the description, the epics with their stories and,
in each story's folder, its decisions (questions a stage asked, a human's answers, acceptances). A story
carries its own state — `status: draft | approved | adopted | superseded` is the person's line,
`status: delivered` and `delivered:` are the gate's, written by nothing else. `.dca-factory/` is
protocol: delete it at any time and the factory still knows what is delivered and what was decided;
what is lost is history — hand-overs, the journal, the tokens. Every place is the profile's to move
(`epics:`, `runs:`, `product:`, `tech:`, `domain:`); the profile itself stays where it is, because it
is where the others are read from.

`project/` holds intent, written before the code and read as a story's input; `docs/` holds what
exists, written after the code by people and by `stage-document`. Where the two meet — the designed
`project/domain.md` against a map generated from the code — a difference is a finding, not a
duplicate.

## A foundation once, then the cycle

```
foundation   describe · set up                         once, and when something moves
cycle        discover → backlog → run → decide → delivered      with every body of work
                         └ plan → test → build → tidy → judge → document
```

| Part | Step | Agent | What it does |
|---|---|---|---|
| foundation | describe | `/dca-describe`, `/dca-describe <change>` | the project description; a change in your words later |
| foundation | set up | `/factory-setup`, `/factory-update` | runner, gate, hook and stack profile — only what is missing |
| cycle | discover | `/factory-discover <topic>` | optional: the problem worth solving, proposed epics with their outcome events |
| cycle | backlog | `/factory-backlog epic <id> --from <report>` · `stories <epic>` · `release <story> …` · `journey <epic>` | an epic from a released proposal, its stories as drafts, their release, the journey that guards a delivered epic |
| cycle | run | `/factory-run [<story>]` | the six stages with a gate between them |
| cycle | decide | `/factory-decisions [<story>]` | questions a stage may not decide, acceptances |
| cycle | delivered | `/factory-status` | what is delivered — stories, epics, outcome events; delivered is not shipped |

The description is not part of the cycle: it is amended in parts by the step that found the reason — a
structural answer (`/factory-decisions`), the document stage (glossary, map), a released description change
from a discovery, a new capability (`/dca-add` writes its `## Stack` line).

## Install

```
/plugin marketplace add domain-centric-development/dca-marketplace
/plugin install dca-factory@dca-marketplace
/plugin install dca-core@dca-marketplace          # the method: the description skill, the skills the stages take their craft from
```

Then, once per project:

```
/factory-setup
```

It checks each part and does only what is missing, in any order relative to the code: the project
description (through `dca-core`'s `dca-describe`, where installed — the factory writes no template of
its own), a git repository (`git init` on your confirmation), the runner, and the stack-profile
lines for what the code has gained since. A second run says what is there and writes nothing; an
installed pipeline is `/factory-update`'s to replace.

```
/factory-setup → /dca-new → /factory-setup → /factory-backlog → /factory-run    description first
/dca-new → /factory-setup → /factory-backlog → /factory-run                     code first
/factory-setup                                                                  an existing project
```

Underneath it runs the same command a terminal or CI uses:

```
bash <plugin>/skills/factory-run/scripts/factory.sh setup --tool claude
```

`--tool codex`, `--tool opencode` or `--tool all` instead, for a project used with those. Setup
needs a git repository and stops without one. It detects the build from the **presets**
(`skills/factory-run/templates/presets/`: one flat file per build tool, browser runner, formatter
or rule package it recognises — the files that give it away and the profile lines it writes) and
leaves a command no preset detects *out* rather than writing a placeholder the gate would try to
run. A new stack is one more preset file, no change to the script. It names a **carrier** — the skill a
stage takes its craft from, `carrier.<stage>:` in the profile — only where that skill is installed beside
the pipeline (`dca-modelling`, `dca-discipline`
where the project has the DCA rule packages; `ubiquitous-language`, `context-map`, `e2e-testing`
wherever they are installed) and installs it in the same run. The skills go into the tool's skill
folder as **copies** when the source is a plugin cache (the marketplace install: a cache folder is
versioned and removed some time after an update, so a link into it would go stale) and as **links**
when it is a checkout (a clone of the marketplace, or `FACTORY_PLUGIN_DIR`: an edit is live);
`--copy` and `--link` name the other one. Check the files it wrote before the first run:

```
dca-factory.profile.yaml     your build and test commands, one per test source set
.agents/factory/story-gate.py            the gate, callable from a terminal and from CI
.agents/factory/factory-cli.py           what shows and coordinates — status, help, usage, the checkout — beside it
.githooks/pre-commit                     the change check on what every commit contains (core.hooksPath)
.claude/skills/.dca-factory-skills       what the install placed there, in which mode, from which kind of source
```

## The project description, before the first story

The description skill writes `project/product.md` and `project/tech.md` with you, one question per
heading: what is built and for whom, through which surfaces, how it works (where state lives, what
is persisted), how it looks, the qualities it needs, what it will not do — and the stack, the
frontend approach, the persistence, where it runs, what it talks to, how versions are chosen. The
designed domain, `project/domain.md`, is optional. Decisions only, no code design. It also writes a
line into `AGENTS.md` that makes every implementation — a stage or a person in a session — read the
three files first. `/factory-backlog` writes nothing while product or tech is missing, and reads
all three before it writes a story; `stage-plan` plans within them and `stage-judge` reports a
change that contradicts them.

## Your first story

Where the problem itself is not clear yet, `/factory-discover <topic>` comes first: it writes a report with
sources and proposes epics, each with its outcome event, and the backlog takes the one you release.

```
/factory-backlog
```

(Installed as a plugin, the skills are namespaced: `/dca-factory:factory-backlog`. The bare
`factory.sh` and gate commands below are the same in every tool.)

Say what the behaviour is. It writes `project/epics/<epic>/epic.md` and one story, asks for the four
epic fields rather than inventing them (`intent`, `goal`, `metric`, `domain_contact`), and leaves
the story `status: draft` until you release it — the one check no script can replace.

```
/factory-run
```

Six stages, a gate between them, one hand-over file each under `.dca-factory/runs/<story>/`. It stops and says
so when a stage escalates, when the judge finds the *story* wrong, or when three rounds did not
converge. The stages run in your session — a subagent each, where the tool has them. One process per
stage, outside the session, is the runner, and it runs only when you start it:

```
bash .agents/factory/factory.sh run --story STORY-1 --tool claude
```

**Every story in a worktree of its own.** The runner gives each story a git worktree under
`.dca-factory/worktrees/<story>/`, on a branch `story/<id>` made from the checkout's branch. The stages
change code there and nowhere else; what is state stays in the main checkout and the worktree sees it
through links — the stories with their decisions, the run folder, the pipeline, the skills — so a
question a stage writes, an answer you give and the status all read one place. When every gate passed
(and a person accepted the story, where one is asked), the **integrate step** merges the main line into
the story's branch, squashes the story to one commit (`feat(<context>): <title>`, the story's id in the
body), runs the gate once more on that tree, and fast-forwards the checkout's branch to it; only then is
the story delivered, and its worktree and branch go. Where git stops on a conflict — two stories changed
the same lines — the `stage-integrate` agent makes both changes hold, and the runner commits. Where the
checkout cannot take the commit (you changed the same file there, or switched branches), the story stops
and says so; `factory.sh run --story <id> --from integrate` takes it up again. A repository without a
commit, a detached HEAD, or a story begun in the checkout before it had a worktree run in the checkout as
before. An IDE opens a story's worktree as a project of its own. A story you set `superseded` loses its
worktree and branch when the runner next starts.

**A human looks before it counts.** With `acceptance: pages` in the profile (`factory-setup`
proposes it where the product has web pages; `all` for every story, `none` for none), a story with
something to see stops after the last gate instead of being delivered: an acceptance record
`<story>-accept-<n>` lists the criteria with their tests and the profile's `run:` command, the gate
exits 3 and the story waits in its worktree, holding no slot — the next story runs meanwhile; its code
reaches the main line only once you accepted it. Answer it through `/factory-decisions`: *accepted*
delivers it; a correction goes into **the same story**, which runs again from plan and is asked
again. A story delivered earlier is taken back for a correction the same way, through
`/factory-decisions` — not while another story holds the checkout, and after an acceptance only to add what the
story left unsaid (changing a criterion is a new wish, a new story). Stories name page sizes by the
table in the product description (`s`, `m`, `l`, `xl`), never in pixels.

Several stories are one command. It runs them in dependency order — and an epic's `depends_on:` before
its stories — runs past a story that waits for a decision or an acceptance, and with `--watch` picks that
story up again at the stage that asked, once the answer is written (`--max-stages` caps the agent
invocations, `.dca-factory/stop` ends it). `--parallel <n>` (or `parallel: <n>` in the profile,
`FACTORY_PARALLEL`) runs up to `<n>` stories at once, each in its worktree, every line of the run named by
its story; a slot counts a story with a running stage, so one that waits holds none. Among the stories
that may start, one with a worktree goes first, then the order, and between stories of one epic the one
whose context no running story changes. With `--parallel`, `--max-stages` and `--story-budget` count per
story process:

```
bash .agents/factory/factory.sh run --tool claude --watch
bash .agents/factory/factory.sh run --tool claude --parallel 2
```

What each story and stage cost — tokens per invocation from the tool's own report, summed across
rounds and restarts, for runner stages and for in-session stages alike (those through
`--stage-start`/`--stage-end` marks, read from the session's own log); `--story-budget <tokens>` on
`run` stops dispatch at a limit:

```
bash .agents/factory/factory.sh status --usage
```

```
/factory-verify
```

Two modes: **observe** the run that just happened — the stages' claims against the repository, the
gate reports and the run journal — or — for whoever changes the pipeline — **check the machinery** itself against throwaway fixtures
(every gate check, the runner's loop and the install shapes). Either way it reports three things: what
did not hold, what held, and what it could not observe. The last one is not decoration: a check
that was not observed is not a check that passed.

## One entry point

`factory.sh setup` puts the runner next to the gate, so everything a person does with the pipeline
in a project goes through one script. Its verbs mirror the skills — `/factory-x` in an agent and
`factory.sh x` in a terminal or CI do the same thing; the skill adds the conversation:

| Command | Skill | Does |
|---|---|---|
| `factory.sh setup [--tool <t>] [--copy\|--link]` | `factory-setup` | installs the pipeline where it is not — copies from a plugin cache, links from a checkout, unless named; on an installed project it only reports |
| `factory.sh setup --check` · `--write [--replace <key>]` | `factory-setup` | what detection finds against the profile · add the keys it lacks, never overwriting a value a person wrote |
| `factory.sh backlog [--check]` | `factory-backlog` | every story's state and the next one · the plan gate's backlog checks over every story; it never works the backlog off |
| `factory.sh run [--story <id> [--from <stage>]] [--watch] [--parallel <n>]` | `factory-run` | one story through the six stages in its worktree, from where its files say, then integrated · `--from` names the stage (or `integrate`) and starts a new count of rounds · without `--story` every story in dependency order, waiting for answers with `--watch`, up to `<n>` at once with `--parallel` |
| `factory.sh status [--story <id>] [--live] [--format md\|json] [--usage] [--refusals] [--brief]` | `factory-status` | what waits for you, what runs, the backlog by epic with times and tokens · one story's passes, stages and decisions · every token class per stage · the gate refusals, form against substance |
| `factory.sh decisions [--story <id>]` | `factory-decisions` | the decision inbox |
| `factory.sh help [--format md\|json]` | `factory-help` | the flow and where this project stands in it, every command in its agent and its shell form, the marks, the files — before the pipeline is installed too |
| `factory.sh update [--from <dir>] [--copy\|--link] [--adopt <skill>,…\|all]` | `factory-update` | the newest pipeline found, same tools; the mode the project has, or the one named; `--adopt` takes over a method skill's copy the install did not make, which every later update then refreshes |
| `factory.sh verify --story <id>` · `--fixtures` | `factory-verify` | observe a delivered story · check the machinery |
| `factory.sh check [--staged] [--checks "<c> …"]` · `--parity <config>` | *(hook, CI)* | the profile's checks outside a story, as the commit hook runs them · several implementations against one scenario contract |

All of them run as `bash .agents/factory/factory.sh …` from the project root. The gate stays a
Python script underneath; what shows and coordinates is `factory-cli.py` beside it, and the stage
skills, the session-start hook and the runner call the one that answers — the gate for a check, the
cli for a view, a mark or a claim.

## How to update a project

The plugin holds the skills; the project holds copies of the gate, the runner and the hook, pinned
in git, so the commit hook and CI run without the plugin and a reviewer sees which pipeline governs
the project. A newer plugin reaches a project when it is updated:

```
/factory-update
bash .agents/factory/factory.sh update [--from <plugin>/skills]     # the same, without a skill
```

It finds the newest pipeline on the machine (`--from`, `FACTORY_PLUGIN_DIR`, the project's skill links,
Claude Code's plugin cache), hands over to *that* pipeline's runner — so a release that adds a file
the project needs puts it there — for the tools the project already uses, and reports the versions
and whether the profile's `contract:` line has to be raised. It commits nothing and leaves the
profile; at its end it names `factory.sh setup --check`, which lists what the project gained since
(a browser runner, a formatter) as profile lines to confirm.

Skills are held one of two ways. The install picks by the source, the update keeps what the project
has unless `--copy` or `--link` names the other:

- **Copies** — the default from a plugin cache (`/plugin install`): the project's own, committed with it,
  so every clone delivers stories without the marketplace, with exactly this pipeline; the update
  refreshes them. A cache folder is versioned and removed some time after an update, which is why a
  link into it is not the default; `setup --link` makes one anyway and says so.
- **Links** — the default from a checkout (a clone of the marketplace, `FACTORY_PLUGIN_DIR`): always
  current, machine-local, kept out of git by the install itself — one `.gitignore` line per link, never
  the folder. A clone gets them back with `factory.sh update`; a link that points nowhere is named by
  `status --brief` (the session's start) with the update that relinks it.

`.dca-factory-skills` beside the skills records the mode, the kind of source and every entry the
install made, and is committed in both modes. Only those entries are the install's to replace or
remove: a skill of the project's own — even with a pipeline skill's name — is never adopted or
overwritten, and a copy from before the list is taken over only when it is byte for byte the
pipeline's. For Claude Code the install also says that, with the plugin enabled, the same skills are
listed a second time as `dca-factory:<skill>`; the project's entry is the one a session and a runner
stage use.

`factory.sh status --live` says when the project is behind the pipeline it found.

## A session that starts knowing where things stand

`setup` writes a section into `AGENTS.md` (between `<!-- dca-factory: start -->` and `end`; only
that block is replaced on an update) telling any tool to begin a session with the gate's
`--status --brief` and to ask what to do. For Claude Code it also adds a `SessionStart` hook to
`.claude/settings.json` that puts those lines into the session's context, and allows the reading
commands (`status`, `decisions`, `backlog`, `setup --check`, `verify`) without a prompt, removing
what an older install allowed under verbs that are gone. Skills use `factory.sh` for everything that
starts no tool; `run` starts a tool process per stage, so no skill runs it and the runner refuses it
inside an agent session (`FACTORY_ALLOW_NESTED=1` to force).
The first message — even "hi" — then gets the state and the choices.

The runner's own processes get a fixed allow-list instead: the gate, the cli, the commands the profile
declares, and the ordinary reading tools (`grep`, `cat`, `head`, `tail`, `ls`, `diff`,
`git diff`, `git ls-files`, `git apply --check`, …) — `factory.sh run --dry-run` prints it as `shell allowed`.
No head that writes or runs is on it (`sed -i`, `xargs`, `find -exec`, `echo >`, `printf >`, `mkdir`, a script on
stdin): a stage lists with Glob, searches with Grep and changes files with the editor tools.

## How to see where it stands

From any session in the project — beside a running `run --watch` too, since it only reads:

```
/factory-status
bash .agents/factory/factory.sh status          # the same, without a skill
```

First what waits for you — a story to accept, a question to answer, a draft to release, a story that
stopped — each with what to do; then what runs; then the backlog grouped by epic, one row per story
with its state, stage, passes, when it started and was delivered, how long its stages worked and its
tokens; then what comes next. The same files give the same text: times are UTC stamps and durations
from the journal. `--live` adds what the clock says (how long ago, the running stage's last activity,
the worker, a listening session, a newer pipeline on this machine). `--story <id>` shows one story:
its passes — a correction after acceptance is a pass of its own — its stages and its decisions.

In a terminal the marks are `!` look at it · `?` answer · `✗` stopped · `▶` running · `✓` delivered ·
`·` nothing to do, in colour where the output is a terminal (`--color always|never`, `NO_COLOR`).
`--format md` renders the same rows as Markdown tables with 👀 ❓ ⛔ ⏳ ✅ ➖ — what a session shows —
and `--format json` for tools. Every epic with an `epic.md` is listed, also before its first story (its next
step is `/factory-backlog stories <epic>`), with its title, goal, outcome event and discovery link; the JSON also
carries the project description as it stands — each part present or missing, its missing and empty headings.
`factory.sh discover --list [--format json]` lists every discovery topic with its proposed epics, which of them
are epics already, and its proposed description changes. In Claude Code, the optional `dca-factory-cockpit` plugin
draws all of it as a cockpit; the files and these commands stay the source.

## A model per stage

```yaml
model.claude.tidy: <model>        # in dca-factory.profile.yaml
model.claude: <model>             # the default for every other stage of that tool
```

Keys are bound to a tool, because a model name means nothing to another one: a profile written for
Claude does not break a colleague's Codex run, and the gate refuses an unqualified `model.tidy`. The
runner passes the value as the tool's model flag (`--model`, `-m`); a `--model` in
`FACTORY_<TOOL>_ARGS` overrides it for one person, and the run says so. A custom `FACTORY_TOOL_CMD`
gets it as `FACTORY_MODEL`. In a session, a subagent can run on it; the session's own context cannot.
`factory.sh status --story <story>` names the model the stages ran on — per stage where they differ — and marks a
request that did not reach a stage. The pipeline names no model: which stages can run cheaper is the project's to measure.

## Two contexts per story: one builds, one checks

By default `factory.sh run` starts a story in two processes. The **builder** carries plan, test, build and
tidy and runs each stage's gate itself; the runner then checks that the red proof exists and runs the
build and tidy gates again, so a process that skipped a gate is stopped, not trusted. The **verifier**
carries the judge and — only on `verdict: pass` — the document stage, which starts on what the judge has
just read; it runs the document gate itself and the runner runs it again. The builder and the verifier
are never one process: the judge's independence from the builder is the point of the split. An
adoption's verifier is the judge alone. Per-stage model keys do not apply to a shared process;
`model.<tool>` does.

```
stages: separate                                                        # in dca-factory.profile.yaml: one process per stage
bash .agents/factory/factory.sh run --story STORY-3 --separate-stages   # the same, for one run
```

One process per stage is the profile's `stages: separate` or `--separate-stages` for a run;
`FACTORY_SHARED_BUILDER=0` or `FACTORY_SHARED_VERIFIER=0` separates one half. Measured: the shared builder
cost 31 % less on one story at the same verdict, and on a smaller model it was the variant that delivered
every story where the separate stages stopped one on its third round.

## Following a running stage

```
bash .agents/factory/factory.sh follow                   # the stage in flight, one line per tool call, as it happens
bash .agents/factory/factory.sh follow --story STORY-3   # that story's stages
bash .agents/factory/factory.sh follow --once --format json   # the last lines, for a view such as the cockpit
bash .agents/factory/factory.sh follow --story STORY-3 --process builder --once   # one process, also long after
bash .agents/factory/factory.sh follow --story STORY-3 --all  # every process of the story, in the order they began
```

Every stage writes its tool's output as it happens — Claude's `stream-json`, Codex's `exec --json`,
OpenCode's `run --format json` — to `.dca-factory/evidence/<story>/<stage>.<time>.out`. `follow` reads
the newest of them and prints what the stage reads, edits and runs, its answers and, at the end, its turns
and cost. It works for any run, whoever started it — a session, a shell, a worker, a scheduled job — and
starts nothing. The cost per stage is read from the same file's last event. The outputs stay beside the story,
so a delivered story's processes can be read afterwards; in a shared builder or verifier each stage it begins is a
heading (`── test`). A call that failed is `✗ <reason>`; one the tool denied because nobody could grant it is
`✗ denied: …` once the process ended, and the result line counts them (`3 denied`).

## What a stage is told

Every stage prompt names the skill, the story and where things are — the stack profile, the story's run
folder, the knowledge skill's catalog, the reports of an earlier round — and `factory-cli.py --contract
<stage>`: the exact shape the gate holds that stage's file to, in a page, from the gate's own constants,
so a stage reads that and never the gate's source. Nothing else: what a session does with those paths
is in the skills and in `factory-run/reference/stage-common.md`, which every stage skill reads first.
A stage that runs its own gate runs it with `--brief` (what passed is one line, what did not stays
verbatim). Before the document stage the runner writes the stage's file as a skeleton
(`factory-cli.py --document-skeleton <story>`) with every changed path and run file root-relative under
`## Paths`, so a cited path is copied, never retyped package-relative — the one refusal that cost the
document stage its rounds on Sonnet.

## What a stage may not write

A stage reads the pipeline and writes code, its hand-over and its question. It never writes what proves its work
or what judges it:

- **The evidence** — the journal, the red ledger, the snapshots and changed-files records, the base tree, the
  story's digest, the round count, the tools' output — lies in `.dca-factory/evidence/<story>/`, beside the run
  folder. The gate and the runner write it; the run folder keeps the hand-overs.
- **The pipeline and the skills.** Claude Code gets `.agents/factory/`, the evidence folder and the skill folders
  as folders to read, under a deny rule for every editing tool (`Edit(//<path>/**)`), in the checkout and in a
  worktree alike; Codex, which reads everywhere, is given only the folders it writes. A change a stage makes
  under `.agents/factory/` anyway is not hidden as the pipeline's own: the next gate refuses it (`pipeline`).
- **The hash.** `gate.installed` records a SHA-256 over the installed files. The runner compares it when a run
  starts — a pipeline that is not the installed one starts nothing — and again before every gate it runs; a
  stage that rewrote the gate stops the run there (exit 7, `pipeline-changed` in the journal, the stop file
  set). `factory.sh update` installs the pipeline again.
- **The story and the answers.** The story file and every decision's `## Answer` are the person's. A stage window
  records their digest at its start and compares at its end (the runner, or `--stage-end` in a session); a stage
  that answered its own question or set its story's `status:` stops the run (exit 7), and the story stays
  stopped — the gate refuses it (`owned`) — until a person looked and runs `factory-cli.py --owned-confirm
  <story>`. `by:` stays free text: the digest is the proof, not the name.

## How to see what a story cost

The runner records every stage's tokens; nothing else is needed.

```
bash .agents/factory/factory.sh run --story STORY-1 --tool claude       # or without --story, --watch
bash .agents/factory/factory.sh status --usage --story STORY-1
```

```
story/stage              runs measured     input  cache read cache write   output   cost $
STORY-1/plan                1        1        18      419063       32121     2596     0.24
STORY-1/test                1        1        18      411307       24978     2386     0.21
STORY-1/build               1        1        16      359248       23996     1977     0.19
STORY-1/tidy                1        1        14      306109       23342     1796     0.17
STORY-1/judge               1        1        16      367718       28256     2806     0.21
STORY-1/document            1        1        20      471299       27528     3275     0.24
STORY-1 total               6        6       102     2334744      160221    14836     1.26
```

A small story on a small library, one round, Sonnet. Almost everything is cache read: every stage
starts fresh and reads the skill, the story and its predecessor's file again.

- A shared builder or verifier is one process with one report. `status --story` shows its stages
  beneath it — `· plan`, `· test`, … — split where the process loads each stage's skill: time and
  input and cache tokens as the stream recorded them, output and cost shared out (`≈`) by what each
  stage wrote and by the tokens' relative prices. The parts add up to the process's line;
  `status` names the stage a running builder is in (`builder · test`).
- A Claude stage runs headless: a call its allow-list does not cover — a loop, a variable, `$(…)`, a path
  outside the project — is denied, and the stage spends a turn on another way. `status --story` counts
  them per stage and per part (`notes`) and lists each call under *Denied*; the stage prompt names what stays refused.
- `runs` counts invocations, repeat rounds included; `measured` those the tool reported on. The
  difference is shown as "without a usage report" — unknown, not zero.
- Leave out `--story` for every story. `factory.sh backlog` shows each story's total in one line.
- `factory.sh status --refusals [--story <id>] [--format json]` counts the gate refusals per story from the
  journal — the runner's (`by=runner`, or no `by`) apart from the stages' own self-checks — and each as *form*
  when every failed check is about how a hand-over is written (`FORM_CHECKS` in the gate: `files-listed`,
  `story-pass`, `tests-mapped`, `test-titles`, `plan-levels`, `levels`, `documented`, `decisions`, `reviews`,
  `layout`), as *substance* otherwise: a form refusal costs a round without the code being wrong.
- `--story-budget <tokens>` on `run` or `backlog` stops before the next stage once the story has
  used that many. The count comes from the journal, so a restart does not reset it.
- In a session (`/factory-run` without the runner) the orchestrator marks each stage with
  `--stage-start`/`--stage-end`; the numbers come from the session's own log, without a price, so
  `cost` reads `—`.
- An old session log is read whole: `python3 .agents/factory/factory-cli.py --usage-from claude-session
  <log>` or `codex-session <log>`
  (`~/.claude/projects/<project>/<session>.jsonl`, `~/.codex/sessions/<date>/rollout-*.jsonl`).

**History.** Every number lives in the project: `.dca-factory/evidence/<story>/journal.tsv`, next to the gate
reports and each invocation's raw output (`*.out`). Whether `.dca-factory/runs/` is committed is the
project's choice: committed, the history travels with the repository — `factory.sh status --usage`
without `--story` shows every story ever run, `status --story` its passes and costs; left out, a clone
still knows what is delivered (the story says so) and what was decided (the records beside it). The journal is append-only, so
the install marks it `merge=union` in `.gitattributes`: two branches that ran the same story merge
without a conflict, a window read on one side and pending on the other counts once, and "running" is
judged by time, not by line order. An in-session stage first
records its window and the session log it read from; once that log has caught up (five minutes after
the window), the next stage mark appends the numbers as a `usage` line of their own, without the session's id,
so the history survives a clone and the tool's cleanup of old session logs. `--usage` and the status
only read.

Claude Code and Codex report their usage; OpenCode's is unknown until its output format is
checked against a real run. The numbers are the tool's, read from its machine-readable output or
its session log — neither is a documented interface, and what cannot be read stays unknown.

## What it reads outside the project, and what it keeps

Only for stages run inside a session, marked with `--stage-start`/`--stage-end`, and for an explicit
`--usage-from`:

- **Claude Code:** the log of the running session and its subagents, found by
  `CLAUDE_CODE_SESSION_ID` under `~/.claude/projects/`. No other session is opened.
- **Codex:** the log of the running session, found by `CODEX_SESSION_ID` in its file name under
  `~/.codex/sessions/`. No other session is opened; without the id nothing is searched.
- **Taken from them:** token counts, the model's name, timestamps — no content. Nothing leaves the
  machine.
- **Kept in the project:** the journal records the session's id and the window, never a path; once
  read, a line with the numbers and without the id follows it. The runner keeps each stage's final message (`*.out`).

It reads with the rights of whoever runs it, so only their own logs. `FACTORY_SESSION_USAGE=off`
switches it off for one person, `sessionUsage: off` in the stack profile for the project; in-session
stages are then unknown. A committed `.dca-factory/evidence/` carries token counts, models, times and the stages'
final messages — leave `.dca-factory/evidence/` out of the repository where that is internal.

## What it carries, and what it does not

It carries no architecture method of its own. Markers, rules, the knowledge catalog and the
project description belong to `dca-core`, the glossary, the context map and the general review
perspectives to `dca-craft`; build commands belong to the project's stack profile. The dependency
runs one way: the factory uses those skills where they are installed — as carriers named in the
profile, the description skill in `/factory-setup` — calls none that writes code, and none of them
knows about the factory. This plugin owns only the process: which stage runs when, which file it hands over, and
what must be true before the next one starts.

## Skills

| Skill | Does |
|---|---|
| `factory-run` | runs one story (an adopted story — `status: adopted`, behaviour the project already has — runs plan, test, judge and the adopt gate, which maps every scenario to a green test and applies a break to every test the adoption wrote, on a scratch copy; contract 9: the happy path end to end, every other scenario integrated, the test gate holding the levels; a `kind: journey` item runs plan, test, judge, document and is green at its test gate): gate → plan → test → gate → build → gate → tidy → gate → reviews (one process per perspective, at once) → judge → document → gate; owns the file contracts, the escalation and the tier it runs the stages in. Several stories: `factory.sh backlog` reads every story's state off the files, and `factory.sh run` without `--story` runs them in that order. `/factory-run <your words>` takes a wish: the gate tells an id from a wish (`--resolve`), `factory-backlog` writes the story with fixed questions (`reference/questions.md`: which epic, the criteria, run now), and the run follows once it is released |
| `stage-plan` | story → `.dca-factory/runs/<story>/plan.md`: elements that change, criteria, test shape per criterion (e2e for the happy path, the use case through its port, an adapter for its translation), the invariants of every domain type it changes |
| `stage-test` | plan → tests plus `.dca-factory/runs/<story>/tests.md` with the criterion-to-test table, and a unit test of its own per invariant rule the plan names, in the `gate:invariants` table `--files-skeleton` writes (the test gate's `invariants`); from contract 15 one row per `Then`/`And` of every scenario with the line that asserts it and its level (`clauses`) — a clause about what is stored is asserted through the input port, never against a stub |
| `stage-build` | red tests → production code plus `.dca-factory/runs/<story>/build.md` |
| `stage-tidy` | a green build → the refactor half of red–green–refactor inside the story's footprint, plus `.dca-factory/runs/<story>/tidy.md`; changes no test and no behaviour |
| `stage-judge` | the change → `.dca-factory/runs/<story>/judge.md`: ddd, hexagonal and clean-code in one verdict, plus any perspective the profile adds (`reviews: dca` with `review.dca: dca-audit` — the method's audit, worth it for adoption work; the setup does not write it) |
| `stage-document` | the change → `.dca-factory/runs/<story>/document.md`: glossary, context map and reader documentation follow the code |
| `stage-integrate` | a merge conflict between a story's worktree and the main line → the conflicted files, both changes holding, and `.dca-factory/runs/<story>/integrate.md`; the runner commits, squashes and gates the result |
| `factory-setup` | sets the factory up and does only what is missing: the project description (through the description skill), git, the runner, the profile lines detection finds (`factory.sh setup [--check \| --write]`). Idempotent; never touches an installed runner |
| `factory-discover` | before the backlog: a problem or a wished deliverable becomes `project/discovery/<topic>/discovery.md` — problem, users and evidence, options, outcome, risks, proposed epics each with its outcome event — from a fixed question catalogue, with every claim citing a source (web with the date read, a project file, an anonymised excerpt under `sources/`; the originals stay in a git-ignored `originals/`). Applies the `product-discovery` craft (`carrier.discover:`); `factory.sh discover --check <topic>` checks the report; writes an epic only once the person releases a proposal, through `factory-backlog`, linked by `discovery:` |
| `factory-backlog` | writes and checks the backlog a run reads — also a story from a wish `/factory-run` hands it, asked from its question catalogue: an epic with its outcome event, or one story small enough for a run. Asks for the four epic fields rather than inventing them, stops while the project description is missing, and checks every story against it at creation |
| — `<story>/findings.md` | the judge's confirmed minors, kept in the story's folder when it is delivered (the run folder is disposable, these are not): one row per finding with file, line, fix and `Status`; `factory-cli.py --findings` lists the open ones, the status brief counts them |
| — `decisions/` | the questions a run may not answer, one file each under `<story>/decisions/<nn>.md` in the story's folder, committed with the project: the stage that asks writes it, a human answers it under `## Answer`, the gate blocks the story while it is open and stamps it applied once the asking stage ran with the answer (`skills/factory-run/reference/file-contracts.md`) |
| `factory-update` | brings the project's gate, runner, hook and skill copies up to the newest pipeline on the machine, for the tools it uses, links as links and copies as copies; migrates an older layout once (profile to the root, `project/backlog/` → `project/epics/`, each story into a folder of its own, records into their stories' folders, run artefacts out of `tasks/`, the delivery mark into the story) and prints every move. Reports the versions and the profile's contract line; commits nothing |
| `factory-status` | one look at the pipeline from any session in the project: which stage runs (and since when), which decisions wait for a human, every story's state and what comes next, the tokens spent per story, and per stage for one (`factory.sh status [--story <id>]`). Reads files; changes and starts nothing |
| `factory-decisions` | the inbox for those records: lists what waits on a human (`factory.sh decisions`), explains one from its files and the story it blocks, and writes the human's `## Answer` — exact wording, their name, the time — only on their explicit confirmation. Answers nothing itself; the stage that asked applies the answer. A structural answer — a new bounded context, a new relationship, a surface an actor lacks — also brings `project/domain.md` and the product description in line |
| `factory-help` | the factory explained in one fixed view (`factory.sh help`): the flow from describing the project to accepting a story with this project's place in it, every command for agent and shell, the marks, the files, what to do next. Reads files; changes and starts nothing |
| `factory-verify` | checks the pipeline itself: every gate check against throwaway fixtures, the runner's stage order, verdict handling and install shapes, and — when asked — one tiny story delivered end to end. Reports; it repairs nothing |

## The gate

`skills/factory-run/scripts/story-gate.py` — one dependency-free Python script, copied into the
project as `.agents/factory/story-gate.py` so every tool and every CI run execute the same check. It
*decides*: the readers, the backlog, the checks per stage, the decision records, `--change`, `--parity`
and the file contract. Everything that *shows or coordinates* — status, help, usage and cost, the
session logs, the checkout claim, the schedule, `--resolve` — is `factory-cli.py` beside it, which
imports the gate and reads every project file through its readers; the runner asks the cli for a
profile value, a verdict, a needs-human section or an open record instead of parsing the file
itself, so one file has one reader. A flag that moved is handed over by the gate, so an older hook or
instruction file still gets its answer:

```
python3 .agents/factory/story-gate.py --story <id> --stage <plan|test|build|tidy|document>
```

| Stage | Checks |
|---|---|
| `plan` | the story names a context that is **on the context map**, has keyed criteria and is not left in `draft`; its epic has `intent`, `goal`, `metric`, `domain_contact`; the repeat counter is below three; a note when the instruction file exceeds what a tool loads |
| `test` | every criterion mapped to a test; that test exists in the sources; test sources compile; every mapped test **red** |
| `build` | every mapped test **green**, and the same version of it the test stage saw fail (`red-proof`); the required suites whole; the profile's `architecture:` and `format:` commands succeed |
| `tidy` | the build gate's checks again — the tidy stage's whole claim is that it changed no behaviour |
| `document` | every file, path and identifier the document stage claims **exists**; every claim names how it was checked; every term the plan proposed has landed in a glossary or is named as open |
| test, build, tidy | a test that existed before the story still expects what it did — added cases pass, and so does a change around its assertions that keeps every assertion with its words and literals in order (a type the test builds gained a field; a note); any other changed or removed line passes only when the plan lists it under `## Changed tests`, backed by the story's `## Changed expectations` or by an answered decision (`tests-kept`, from the plan gate's git baseline) |
| every stage | the story's **decision records** (`<story>/decisions/` in each story's folder): a `## needs-human` names one; an open one blocks the story and says where to answer; an answered one is applied by the stage that asked and stamped `## Applied` |

A command the stack profile does not declare is skipped and named in the report — never failed,
unless the profile's `required:` names it (below).
The gate is a build-level check, not a hook and not a stage's self-assessment: a stage cannot
declare its own work done.

**Outside a story** the same script checks any change — a direct edit, a commit, a CI run — with
one command and one verdict for one tree:

```
python3 .agents/factory/story-gate.py --change            # the working tree, e.g. in CI
python3 .agents/factory/story-gate.py --change --staged   # what the commit contains
```

It runs the profile's `compile`, test, `architecture` and `format` commands. A test command passes
only when its reports show executed cases — a runner that matched nothing exits 0 too. The profile's
`required:` line (`required: compile test architecture`) makes checks mandatory — each test command
by its own key (`test`, `test.integration`, `e2eTest`), so an end-user suite that needs a running
system stays optional: a required check that is not declared, not run in this scope or ran nothing
fails, and a red check outside the policy is reported without deciding the verdict. Without it nothing
is mandatory: a declared command that runs red fails, one that is not declared is skipped and named. `--staged` checks the Git index, including the temporary one `git commit -a` uses, and
**refuses** when the working tree differs from it — modified-not-staged or untracked files — because
tests passing against an unstaged fix say nothing about the commit.

`templates/githooks/pre-commit` is exactly that command (`git config core.hooksPath .githooks`; where
another hook manager already set `core.hooksPath`, the install leaves it and says to call
`.githooks/pre-commit` from there). The agent tools' own folders (`.claude/`, `.codex/`, `.opencode/`)
are no input to the check, so skill links and settings the install left untracked do not refuse a commit.
`FACTORY_PRECOMMIT_CHECKS="compile architecture"` narrows the hook on a slow stack, and a required check
left out is reported as not run here, never as passed. That is the enforcement boundary — a tool's
own hooks are a fast feedback loop, but only git is common to every tool, and a hook can be skipped
with `--no-verify`, so CI runs `--change` as well.

**Several implementations of one behaviour** — a port, a second language, a rewrite — prove the
same scenarios from their own reports:

```
python3 .agents/factory/story-gate.py --parity parity.conf
```

`parity.conf` names the scenario contract (`scenarios: <file>`) and one `implementation.<name>:
<report glob>` per implementation. Every `Runs: always` scenario must appear in each
implementation's reports, by its title as the test's name, and pass; missing, failed or skipped
fails. Each implementation is held to the contract, not to the other one.

## Portability

Skills are plain `SKILL.md` folders and the gate is a script, so the same folder works in any
agent tool that reads the Agent Skills format. No stage depends on a plugin manifest, agent
frontmatter or a tool's hooks. The runner (`factory.sh`) is optional — a session runs the stages
without it; the git pre-commit hook is the one hook the pipeline relies on, because every tool
commits through git; Claude Code's SessionStart hook only tells a session where the pipeline stands.
Where a tool can start a subagent per stage, `factory-run` uses it; where it cannot, the file
contracts plus the gate keep an in-session run honest.

## What is actually supported

Portable *in form* is not the same as verified *in fact*, and the difference is worth stating
rather than leaving a reader to find it in a failing run.

**Agent tools.** Claude Code, Codex and OpenCode have an adapter in `factory.sh`; any other tool
plugs in through `FACTORY_TOOL_CMD`. Run the stage skills in-session and no adapter is needed at
all — the file contracts and the gate are what make a run honest, not the runner.

**What a runner stage sees.** Only the project. Each tool gets the isolation it offers:

| Tool | Isolation the runner applies | Not isolated |
|---|---|---|
| Claude Code | `--setting-sources project` (no user skills, user plugins or user settings), `--strict-mcp-config` (no MCP server), `--tools` with the stage tools only, `--exclude-dynamic-system-prompt-sections` (no per-machine text in the system prompt, so every stage shares one cached prefix); flags an older CLI does not know are left out | Claude Code's own built-in skills |
| OpenCode | `--pure` (no external plugins); usage read from `--format json` | its tool set: unrestricted by default; `FACTORY_OPENCODE_PERMISSIONS=on` hands it the pipeline's shell list and protected folders as an `OPENCODE_CONFIG_CONTENT` permission block — not yet probed against a signed-in OpenCode, so off until it is |
| Codex | `--ignore-user-config` (no `~/.codex/config.toml`: its MCP servers, profiles and model stay out; the login stays) — a model then comes from `FACTORY_CODEX_ARGS` | user skills under `~/.codex/skills` |

Carriers the profile names (`carrier.<stage>`, `review.<perspective>`, `knowledge`) are therefore installed into
the project: `setup --tool claude` puts them into `.claude/skills/` (one entry per skill, linked or copied like
the pipeline's own, beside them), and the runner stops before the first stage when one is missing. The reviewer
agents of `dca-craft` are not installed: a skill works in every tool, an agent only where its plugin is enabled,
so a runner stage — and a Codex or OpenCode session — runs the review skills the profile names, and the judge says
so; the agents are a comfort for a Claude Code session with the plugin. `FACTORY_ISOLATION=off` runs the stages
with the tool's full setup instead, and says so. Measured in a small project (claude 2.1.281): the first turn of a
stage starts at 16.2k tokens instead of 25.9k. For a local model through OpenCode and LM Studio, the runner reads
the loaded context window and warns below `FACTORY_LOCAL_CONTEXT_MIN` (default 65536 tokens). The journal records
each invocation's wall-clock time, and `status <story>` shows it.

**Operating systems.** The gate is standard-library Python 3 and runs wherever Python does. The
runner and the commit hook are bash, so both want a POSIX shell. Linux, macOS and **Windows under
Git Bash** are what the pipeline's own suite runs on in CI. On Windows the install copies the skills
where `ln -s` cannot link (a symlink needs developer mode and `MSYS=winsymlinks:nativestrict`;
without them `ln -s` makes a silent copy anyway, so the installer probes and says which it did), the runner picks `python3` or `python`, whichever the machine has (`FACTORY_PYTHON`
overrides), and the gate runs the profile's commands through Git's bash — found beside `git`, never the
WSL launcher in `System32`; `FACTORY_BASH` names another — so a profile is written for a POSIX
shell on every platform. WSL is the same route with a Linux userland and needs
none of that. A project on Windows can still use the gate on its own: it is one file and one
command line.

**Test stacks.** The criterion-to-test mapping is a selector of the form `<class>#<method>`, and
the gate needs three things to line up behind it: a filter the runner accepts (`filterFlag`,
`filterFormat`), a source file it can find, and a report that names the case (JUnit XML or TRX,
matched on class plus method or a declared display name). Two shapes resolve the class part to a
file:

- **a file named after the class** — `com.example.WidgetTest` in `WidgetTest.java`, wherever it
  is. **JUnit on Gradle and Maven**, **xUnit, NUnit and MSTest on `dotnet test`**, Kotlin and any
  JVM language that keeps one class per file.
- **a file named by the module path** — `tests.test_widgets` in `tests/test_widgets.py`, and
  `tests.test_widgets.TestWidgets` in the same file. The class part is read as a dotted path and
  the longest prefix that is a file (by path, never by a stray basename) is the module; the
  remaining segments must be declared in it. **pytest** is the stack the suite drives, with real
  pytest: located, selected by `filterFormat: "{file}::{method}"` — `{file}` is the located
  source, the handle a runner that selects by path needs — and read back from the JUnit XML that
  `--junitxml` writes. A parametrised test is one test in that reading, and one failing case
  fails it.

What still does not hold: selecting a pytest method that sits in a class (it is *found*, but
`{file}::{method}` names the function level, so pytest runs nothing and the gate says so), and
stacks whose tests carry no dotted identity at all — Jest's `describe`/`it` strings, Go's
package-level functions. Each of those is one more shape, to be added for a concrete stack when
one asks for it, never in the abstract.

## Versions, and what a version answers

The gate is **copied** into a project, so two questions come apart that a single version number
would run together. Both are stated in `story-gate.py` (the cli beside it carries the same `VERSION`,
and the runner refuses a pair that differs) and readable with `python3 .agents/factory/story-gate.py --version`:

| | What it answers | Who checks it, and how it ends |
|---|---|---|
| **file contract** (`CONTRACT`, and `contract:` in the stack profile) | can this gate read this project's files at all | the **gate**, on every run. A profile written for a higher contract is **refused**: this script would ignore whatever the newer contract added, and a key ignored in silence is a check that has quietly gone |
| **script version** (`VERSION`) | which release governs this project | the **runner**, comparing `.agents/factory/gate.installed` — five machine-neutral lines (plugin, version, contract, the files of the release and their SHA-256) written at install time and **committed with the project** — against the pipeline it finds beside it. A project on an older release of the same contract is valid and says so: an update to run, never a reason to refuse a story |

The current file contract is 17: a story's evidence beside its run folder, in `.dca-factory/evidence/<story>/`. `factory.sh update` says when a profile's `contract:` line is to
be raised.

The gate cannot answer the second one alone: a copied script has nothing to compare itself
against. The record holds the *identity* of the pipeline — plugin, version, contract — and never a
path or a timestamp, because those describe the machine that happened to run the install and would
be wrong in every other checkout. Where the plugin lives is resolved when the comparison is made:
`FACTORY_PLUGIN_DIR`, the checkout the runner is started from, or the skill links an install left.
When none of them resolves there is nothing to compare, and the runner says nothing rather than
guessing.

## Project knowledge

None is baked in. Everything project-specific comes from two places the project owns: the
**stack profile** (`dca-factory.profile.yaml` — build and test commands, `format:` and
`formatFix:`, `browser:`, `acceptance:` and `run:`, the carriers) and `project/` with the
**description, backlog**, beside the glossaries and the context map. A skill that would break in a project without a
particular domain concept would be wrong.

A stage may treat a knowledge skill as an authority only when the profile names it —
`knowledge: <skill>` — and then it cites the node it read. A catalog that merely happens to be
installed is never adopted: a vendored copy of an older release names rules and markers that no
longer exist, and a citation would make that wrongness look verified. Unnamed, the stages work from
the project's own rules, markers, glossary and documents, which is what the gate checks anyway.
`knowledge.read: <path>, …` names nodes inside that catalog a stage reads once before it writes code — the node
that lists the API the code implements, a design system's component list; the prompt gives them as paths.
`factory.sh setup` takes it from the method's conventions file where the method names one.

A stage's *craft* — how this project writes end-user tests, how it implements, which review
perspectives it adds — is bound in the profile too: `carrier.<stage>:` and
`review.<perspective>:`/`reviews:`. A skill named there works in every tool; an agent only where a
tool has agents, and a carrier this tool cannot offer falls back to the stage's own description
with that fact in the report.

See `skills/factory-run/reference/backlog-contract.md`, `.../file-contracts.md` and `.../stage-common.md` — the rules
every stage holds to (the knowledge source, the carrier, the decision record, the gate as the test run, the
formatter), said once; each stage skill names them in a line and points there.

## Troubleshooting

**"no test report from this run names it."** The gate reads what a runner *executed* from its
report, because an exit code says how a process ended and a message says what it printed — neither
says a test ran. A runner that answers "no tests found for <selector>" produces a different exit
code and a different line for every selector while executing nothing. Let the runner write a report
(JUnit XML is the default on the JVM and an option in every other ecosystem — pytest, jest,
gotestsum, nextest, PHPUnit, RSpec; the .NET platform needs `--logger trx`), point `testReport:` at
it if it lands somewhere unusual, or accept the weaker check with `testEvidence: exit-code` and
read that line in every report it produces.

**"the report holds N cases for that class and none is named …"** The runner reported display names
rather than method names, and more than one test of that class ran — so no case can be attributed
to the mapped test without guessing. Give the test a name the report carries, or declare the
display name where the test is declared (`@DisplayName`, `[Fact(DisplayName = …)]`,
`[Test(Description = …)]`): the gate reads it from there and matches on it.

**"no declared test command covers this test."** A mapped test lives in a source set the profile
does not mention. Add it as `test.<name>: <command>`. The gate refuses rather than guessing,
because a run that matched no test exits successfully on one runner and unsuccessfully on another —
neither is evidence.

**"<command> did not run the test."** The command could not start (a missing runner, a typo, an
unbuildable project). That is not a red test, and the gate will not record it as one.

**"never recorded red by the test stage."** A green test is only evidence if the same test failed
before the code existed. Run `--stage test` first, or say why this criterion's test cannot fail.

**A skill I added to the source does not show up.** The entries are made one per skill, so a *new*
skill needs `factory.sh update`; an edited one is live where the project holds links, and needs the
update where it holds copies. `.dca-factory-skills` beside them says which.

**A skill link points nowhere.** The version it pointed into was removed from the plugin cache after
an update, or the checkout moved. `factory.sh update` relinks into the newest pipeline it finds;
`update --copy` makes the project independent of the cache. `status --brief` names such a link.

**The gate says a command was "skipped and named".** The profile does not declare it. Deliberate: a
gate that fails on something nobody configured gets switched off, and then nothing is checked at
all.

## Author

**Christoph Bloemer** — [@chbloemer](https://github.com/chbloemer)
