# dca-factory

The **delivery pipeline** for a Domain-Centric Architecture project: a backlog contract, four
stage skills with file hand-overs, a deterministic story gate and one orchestrator.

## Install

```
/plugin marketplace add domain-centric-development/dca-marketplace
/plugin install dca-factory@dca-marketplace
/plugin install dca-core@dca-marketplace          # the method the stages call
```

Then, once per project — this writes the gate, the stack profile and the commit hook into the
repository, because that is where a process has to live to survive a change of tool:

```
bash <plugin>/skills/factory-run/scripts/factory.sh install --tool claude
```

`--tool codex`, `--tool opencode` or `--tool all` instead, for a project used with those. The
installer reads what the project already states — build tool, verification command — and leaves
a command it could not detect *out* rather than writing a placeholder the gate would try to run.
Check the file it wrote before the first run:

```
.agents/factory/factory.profile.yaml     your build and test commands, one per test source set
.agents/factory/story-gate.py            the gate, callable from a terminal and from CI
.githooks/pre-commit                     the change check on what every commit contains (core.hooksPath)
```

## Your first story

```
/factory-backlog
```

(Installed as a plugin, the skills are namespaced: `/dca-factory:factory-backlog`. The bare
`factory.sh` and gate commands below are the same in every tool.)

Say what the behaviour is. It writes `backlog/<epic>/epic.md` and one story, asks for the four
epic fields rather than inventing them (`intent`, `goal`, `metric`, `domain_contact`), and leaves
the story `status: draft` until you release it — the one check no script can replace.

```
/factory-run
```

Six stages, a gate between them, one hand-over file each under `tasks/<story>/`. It stops and says
so when a stage escalates, when the judge finds the *story* wrong, or when three rounds did not
converge. Where the project has the runner script, the highest isolation is one process per stage:

```
bash .agents/factory/factory.sh run --story STORY-1 --tool claude
```

Several stories are one command. It runs them in dependency order, runs past a story that waits
for a decision, and with `--watch` picks that story up again at the stage that asked, once the
answer is written (`--max-stages` caps the agent invocations, `.agents/factory/stop` ends it):

```
bash .agents/factory/factory.sh backlog --tool claude --watch
```

```
/factory-verify
```

Two modes: **observe** the run that just happened — the stages' claims against the repository, the
gate reports and the run journal — or **check the machinery** itself against throwaway fixtures
(every gate check, the runner's loop and the install shapes). Either way it reports three things: what
did not hold, what held, and what it could not observe. The last one is not decoration: a check
that was not observed is not a check that passed.

## What it carries, and what it does not

It carries no architecture method of its own. Markers, rules, the knowledge catalog, glossary
and context map belong to `dca-core`; build commands and templates belong to the project's stack
profile. The dependency runs one way: the factory calls `dca-core`'s skills — the bootstrap that
installs the architecture once, the scaffolding, the review perspectives, the knowledge catalog —
and none of them knows about the factory. This plugin owns only the process: which stage runs when, which file it hands over, and
what must be true before the next one starts.

## Skills

| Skill | Does |
|---|---|
| `factory-run` | runs one story: gate → plan → test → gate → build → gate → tidy → gate → judge → document → gate; owns the file contracts, the escalation and the tier it runs the stages in. Several stories: `story-gate.py --schedule` reads every story's state off the files, and `factory.sh backlog` runs them in that order |
| `stage-plan` | story → `tasks/<story>/plan.md`: elements that change, criteria, test shape per criterion |
| `stage-test` | plan → tests plus `tasks/<story>/tests.md` with the criterion-to-test table |
| `stage-build` | red tests → production code plus `tasks/<story>/build.md` |
| `stage-tidy` | a green build → the refactor half of red–green–refactor inside the story's footprint, plus `tasks/<story>/tidy.md`; changes no test and no behaviour |
| `stage-judge` | the change → `tasks/<story>/judge.md`: domain, boundaries and craft in one verdict, plus any perspective the profile adds |
| `stage-document` | the change → `tasks/<story>/document.md`: glossary, context map and reader documentation follow the code |
| `factory-backlog` | writes and checks the backlog a run reads: an epic with its outcome event, or one story small enough for a run. Asks for the four epic fields rather than inventing them |
| — `decisions/` | the questions a run may not answer, one file each under `.agents/factory/decisions/<story>-<nn>.md`, committed with the project: the stage that asks writes it, a human answers it under `## Answer`, the gate blocks the story while it is open and stamps it applied once the asking stage ran with the answer (`skills/factory-run/reference/file-contracts.md`) |
| `factory-decisions` | the inbox for those records: lists what waits on a human (`story-gate.py --list-decisions`), explains one from its files and the story it blocks, and writes the human's `## Answer` — exact wording, their name, the time — only on their explicit confirmation. Answers nothing itself; the stage that asked applies the answer |
| `factory-scope` | answers the question a run may not answer itself — a new bounded context, a new relationship, a surface its actor lacks — as a recorded decision plus the map, never as code |
| `factory-verify` | checks the pipeline itself: every gate check against throwaway fixtures, the runner's stage order, verdict handling and install shapes, and — when asked — one tiny story delivered end to end. Reports; it repairs nothing |

## The gate

`skills/factory-run/scripts/story-gate.py` — one dependency-free Python script, copied into the
project as `.agents/factory/story-gate.py` so every tool and every CI run execute the same check:

```
python3 .agents/factory/story-gate.py --story <id> --stage <plan|test|build|tidy|document>
```

| Stage | Checks |
|---|---|
| `plan` | the story names a context that is **on the context map**, has keyed criteria and is not left in `draft`; its epic has `intent`, `goal`, `metric`, `domain_contact`; the repeat counter is below three; a note when the instruction file exceeds what a tool loads |
| `test` | every criterion mapped to a test; that test exists in the sources; test sources compile; every mapped test **red** |
| `build` | every mapped test **green**; the profile's `architecture:` and `format:` commands succeed |
| `tidy` | the build gate's checks again — the tidy stage's whole claim is that it changed no behaviour |
| `document` | every file, path and identifier the document stage claims **exists**; every claim names how it was checked; every term the plan proposed has landed in a glossary or is named as open |
| test, build, tidy | a test that existed before the story still expects what it did — added cases pass; a changed or removed line passes only when the plan lists it under `## Changed tests`, backed by the story's `## Changed expectations` or by an answered decision (`tests-kept`, from the plan gate's git baseline) |
| every stage | the story's **decision records** (`.agents/factory/decisions/`): a `## needs-human` names one; an open one blocks the story and says where to answer; an answered one is applied by the stage that asked and stamped `## Applied` |

A command the stack profile does not declare is skipped and named in the report — never failed.
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
fails, and a red check outside the policy is reported without deciding the verdict. Without it the check is
report-only. `--staged` checks the Git index, including the temporary one `git commit -a` uses, and
**refuses** when the working tree differs from it — modified-not-staged or untracked files — because
tests passing against an unstaged fix say nothing about the commit.

`templates/githooks/pre-commit` is exactly that command (`git config core.hooksPath .githooks`);
`FACTORY_PRECOMMIT_CHECKS="compile architecture"` narrows it on a slow stack, and a required check
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
agent tool that reads the Agent Skills format. Nothing in the pipeline depends on a plugin
manifest, an orchestration script, agent frontmatter or hooks. Where a tool can start a
subagent per stage, `factory-run` uses it; where it cannot, the file contracts plus the gate
keep an in-session run honest.

## What is actually supported

Portable *in form* is not the same as verified *in fact*, and the difference is worth stating
rather than leaving a reader to find it in a failing run.

**Agent tools.** Claude Code, Codex and OpenCode have an adapter in `factory.sh`; any other tool
plugs in through `FACTORY_TOOL_CMD`. Run the stage skills in-session and no adapter is needed at
all — the file contracts and the gate are what make a run honest, not the runner.

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
would run together. Both are stated in `story-gate.py` and readable with
`python3 .agents/factory/story-gate.py --version`:

| | What it answers | Who checks it, and how it ends |
|---|---|---|
| **file contract** (`CONTRACT`, and `contract:` in the stack profile) | can this gate read this project's files at all | the **gate**, on every run. A profile written for a higher contract is **refused**: this script would ignore whatever the newer contract added, and a key ignored in silence is a check that has quietly gone |
| **script version** (`VERSION`) | which release governs this project | the **runner**, comparing `.agents/factory/gate.installed` — three machine-neutral lines written at install time and **committed with the project** — against the pipeline it finds beside it. A project on an older release of the same contract is valid and says so: an update to run, never a reason to refuse a story |

The gate cannot answer the second one alone: a copied script has nothing to compare itself
against. The record holds the *identity* of the pipeline — plugin, version, contract — and never a
path or a timestamp, because those describe the machine that happened to run the install and would
be wrong in every other checkout. Where the plugin lives is resolved when the comparison is made:
`FACTORY_PLUGIN_DIR`, the checkout the runner is started from, or the skill links an install left.
When none of them resolves there is nothing to compare, and the runner says nothing rather than
guessing.

## Project knowledge

None is baked in. Everything project-specific comes from two places the project owns: the
**stack profile** (`.agents/factory/factory.profile.yaml` — build and test commands) and the
**backlog, glossary and context map**. A skill that would break in a project without a
particular domain concept would be wrong.

A stage may treat a knowledge skill as an authority only when the profile names it —
`knowledge: <skill>` — and then it cites the node it read. A catalog that merely happens to be
installed is never adopted: a vendored copy of an older release names rules and markers that no
longer exist, and a citation would make that wrongness look verified. Unnamed, the stages work from
the project's own rules, markers, glossary and documents, which is what the gate checks anyway.

A stage's *craft* — how this project writes end-user tests, how it implements, which review
perspectives it adds — is bound in the profile too: `carrier.<stage>:` and
`review.<perspective>:`/`reviews:`. A skill named there works in every tool; an agent only where a
tool has agents, and a carrier this tool cannot offer falls back to the stage's own description
with that fact in the report.

See `skills/factory-run/reference/backlog-contract.md` and `.../file-contracts.md`.

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

**A skill I added to the source does not show up.** For Claude Code the pipeline's folder is linked
as a whole, so it appears at once. For Codex and OpenCode the skills come from several sources and
are linked individually — a *new* one needs another `install`; an edited one is live either way.

**The gate says a command was "skipped and named".** The profile does not declare it. Deliberate: a
gate that fails on something nobody configured gets switched off, and then nothing is checked at
all.

## Author

**Christoph Bloemer** — [@chbloemer](https://github.com/chbloemer)
