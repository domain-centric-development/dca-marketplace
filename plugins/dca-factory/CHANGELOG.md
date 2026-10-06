# dca-factory — changelog

How the delivery pipeline grew, from the first six stages to today. The milestones group the versions that
worked on one theme, and what each made more deterministic — decided by a rule, a script or a recorded answer
instead of by the model; the table below them names every version and what it changed against the one before.

## Milestones

| Versions | Theme | What it brought | What makes it more deterministic |
|---|---|---|---|
| 0.1 – 0.4 | **The pipeline** | Six stages from story to documentation (plan, test, build, tidy, judge, document), a deterministic gate between them, and test cases that verify the pipeline itself | A script decides whether a stage is done, not the model's own report — the same files get the same verdict every time |
| 0.6 – 0.8, 0.11 | **Ask, never guess** | A question a stage may not answer becomes a decision record beside the story; an inbox to answer it; the backlog runs on past an open question; a story that contradicts itself is a question, not a guess | An open point is answered once by a person and recorded; every later run reads that answer instead of guessing anew |
| 0.10, 0.12 – 0.14 | **Rounds and proof** | A refused gate loops back into a round; existing tests keep what they expect; a story that changes behaviour says so; the red proof holds for one version of a test | "Done" rests on evidence — the test was red before the change and green after, for that exact version of the test |
| 0.15 – 0.24 | **Visible and bounded** | Cost per story and per stage, with a ceiling; `/factory-status` from any session; update a project to the newest pipeline; one worker per checkout | One writer per checkout, and a cost ceiling that ends a run the same way each time |
| 0.25 – 0.30 | **Smaller context, lower cost** | The product scope before the first story; a stage sees only the project; every stage is handed what the story changed; a model per stage; plan to tidy in one shared session (−37 % cost on one story) | Every stage starts from the same small input — the project and what the story changed — not from whatever lies around |
| 0.31 – 0.38 | **Set up and used by a person** | Stack presets and guided setup; `dca-new`, `dca-init`, `dca-add`; acceptance before delivery; a self-explanatory status view; `/factory-help`; `/factory-run <wish>` turns a sentence into a story; one test level per scenario | The same questions in the same order and the same report: two fresh sessions asked the same 22 questions, word for word; the happy path is marked in the story, never picked by a plan |
| 0.39 – 0.41 | **Existing code** | Adopt behaviour a project already has: map its tests, prove each can break; scenario titles as test names; the browser suite starts the application itself | A test proves it can fail — a patch that breaks the code must turn it red — for adopted code as for new |
| 0.42 – 0.49 | **Hardened by review** | Review findings closed; an integration test level; deterministic installs; the gate split from the CLI; the story carries its own state, the run folder is protocol only | The same files from the same source on every install; each piece of state lives in one place |
| 0.50 – 0.52 | **Faster** | One test process per command, cheap checks first, test runs reused on an unchanged tree, the hand-over's file list and plan lines written by the pipeline, leaner hand-overs — four stories from 54.9 to 39.7 minutes at the same quality | What a model would type and could get wrong — file lists, plan lines — the pipeline writes |
| 0.53 – 0.54 | **Independent reviews** | Three reviewers run side by side in their own contexts, the judge confirms only what it finds in the code (16 instead of 5 confirmed findings); minor findings stay beside the story for later | Each perspective in a fresh context, uninfluenced by the others; a finding counts only with the file and line it stands on |
| 0.55 – 0.57 | **Test quality** | The plan names every domain type's invariants, each gets a unit test of its own in a table the pipeline writes; the use case is tested once at its port, each adapter for its translation — branch coverage 81 → 92 % | Which unit tests exist follows from the plan's invariants and a table the pipeline writes and the gate checks — not from a model's habit |
| 0.56 | **A deterministic domain model** | Two runs of the same story name the same operations and events: a story's verbs come from the glossary, never from a translation; a verb that could mean creating or adding is decided by its effect (does the thing exist before this step?); the journey reads as a timeline of commands and events. Found by the bench: the epic said `TaskCreated`, the code published `TaskAdded` | A word in the code comes from the glossary, and an ambiguous verb is decided by one fixed question — not by how a model happens to translate |
| 0.58 – 0.59 | **Validation** | The epic's outcome event, named and checked: the story that completes the flow declares `publishes:`, the plan gate holds the name to the epic's `metric:`, the document gate to the code — the type exists and something the story changed raises it; the reviewers and the judge read the epic. A delivered epic without a journey test is shown as unguarded until it names one or decides against it | Whether the outcome can happen is a check on files, not a reviewer's attention — the bench's `TaskCreated` against `TaskAdded` is refused by name |
| 0.60 | **Ideation** | `/factory-discover` before the backlog: a fixed question catalogue, research where every claim cites a source (web with the date read, project files, anonymised excerpts of the interviews and tickets handed over — the originals stay out of git), a report and proposed epics with their outcome events; the person releases one, the backlog writes it | The questions, the report's shape and its citations are fixed and checked (`--check-discovery`); the research is not, so it stays a proposal and the decision a person's |
| 0.62 – 0.63 | **A foundation and a cycle** | The person's view in two parts — describe and set up once, then discover → backlog → run → decide → delivered; every epic in the status, also before its first story, with its outcome and discovery; the project description as it stands in the status; `discover --list`; a discovery may propose a description change; the backlog skill's argument forms (`epic <id> --from <report>`, `stories <epic>`, `release <story> …`, `journey <epic>`) | What a view showed by reading files itself — epics, proposals, the description — the factory now says in JSON, the same for every tool; one word per act from a person, a view or another tool |
| 0.64 | **Watched, shared by default** | A shared process's stages shown one by one, with their share of the cost; a stage's output as it happens — `factory.sh follow` and the cockpit show what a stage reads, edits and runs, whoever started it; the shared builder and verifier are the default, separate stages a profile line | What the default run is no longer depends on a flag a person remembers; what a stage does is visible from its own stream, not inferred from its hand-over at the end |

## Every version

| Version | Date | Change against the version before |
|---|---|---|
| 0.1.0 | 2026-09-10 | The first pipeline: six stages from the story to the documentation |
| 0.2.0 | 2026-09-10 | The plugin manifest names what it contains |
| 0.3.0 | 2026-09-10 | The pipeline verifies itself with its own test cases |
| 0.4.0 | 2026-09-11 | Gaps from the first review closed: evidence, robustness, versions |
| 0.5.0 | 2026-09-22 | Python tests (pytest) and Windows |
| 0.6.0 | 2026-09-22 | A question a stage may not answer becomes a decision record, and so does its answer |
| 0.7.0 | 2026-09-22 | The decision inbox: list, explain, record an answer |
| 0.8.0 | 2026-09-22 | Run the whole backlog, past an open question and back to it |
| 0.9.0 | 2026-09-22 | One change check for edits, commits and CI |
| 0.9.1 | 2026-09-23 | Fixes from the first joint acceptance run |
| 0.10.0 | 2026-09-23 | A refused gate loops back into a round; only the gate marks a story delivered |
| 0.10.1 | 2026-09-23 | Stories are read only from epic folders |
| 0.11.0 | 2026-09-23 | A story that contradicts itself makes the judge ask instead of guess |
| 0.12.0 | 2026-09-23 | A test that existed before the story keeps what it expects |
| 0.13.0 | 2026-09-23 | A story that changes behaviour says so; the plan finds the affected tests |
| 0.14.0 | 2026-09-23 | The red proof holds for one version of a test |
| 0.15.0 | 2026-09-23 | Cost per story and per stage, with a ceiling |
| 0.16.0 | 2026-09-23 | `/factory-status`: where the pipeline stands, from any session |
| 0.17.0 | 2026-09-23 | Update a project to the newest pipeline |
| 0.18.0 | 2026-09-23 | The journal names a session by its id, never by a path |
| 0.19.0 | 2026-09-23 | One worker per checkout; the runner can run in the background |
| 0.20.0 | 2026-09-23 | A new session knows at once where the pipeline stands |
| 0.21.0 | 2026-09-23 | `/factory-run` runs the stages in the session; the runner only when asked |
| 0.21.1 | 2026-09-23 | Skills name skills to the person, not shell commands |
| 0.22.0 | 2026-09-23 | No skill and no hook starts `factory.sh`; only the person does |
| 0.22.1 | 2026-09-23 | The runner refuses to start inside an agent session |
| 0.22.2 | 2026-09-23 | Skills use `factory.sh` again, except for run and backlog |
| 0.23.0 | 2026-09-23 | A waiting runner shows a sign of life |
| 0.24.0 | 2026-09-23 | The status shows the cost per story and per stage |
| 0.25.0 | 2026-09-24 | The product scope comes before the first story |
| 0.26.0 | 2026-09-24 | A stage sees only the project — a smaller context |
| 0.27.0 | 2026-09-24 | Every stage is handed what the story changed |
| 0.28.0 | 2026-09-24 | A model per stage |
| 0.29.0 | 2026-09-24 | Plan to tidy in one shared session, the judge fresh |
| 0.30.0 | 2026-09-24 | A browser runner before the first page |
| 0.30.1 | 2026-09-24 | The gate's false greens closed |
| 0.30.2 | 2026-09-24 | Runner, installer and hook defects fixed |
| 0.30.3 | 2026-09-24 | Contracts, skills and runner say the same thing |
| 0.31.0 | 2026-09-25 | Stack presets and `factory.sh setup` |
| 0.32.0 | 2026-09-25 | Guided setup; the project description under `project/` |
| 0.33.0 | 2026-09-25 | One naming scheme: `/dca-new`, `/dca-init`, `/dca-add` |
| 0.33.1 | 2026-09-25 | Seven defects from the first run on an empty directory fixed |
| 0.33.2 | 2026-09-25 | The last stage's cost is recorded reliably |
| 0.33.3 | 2026-09-25 | Update restores skill links in a clone |
| 0.33.4 | 2026-09-25 | Test names are read as the runtime sees them |
| 0.33.5 | 2026-09-25 | Catalog citations are recognised as citations |
| 0.34.0 | 2026-09-25 | Acceptance by a person before delivery |
| 0.34.1 | 2026-09-25 | Reopening waits while another story holds the checkout |
| 0.34.2 | 2026-09-25 | UTF-8 output on a Windows console |
| 0.34.3 | 2026-09-25 | A copying install brings the same craft as a linking one |
| 0.35.0 | 2026-09-25 | The status as a self-explanatory view |
| 0.35.1 | 2026-09-25 | The view's refinements reach installed plugins |
| 0.35.2 | 2026-09-25 | An epic is ✓ once every one of its stories is delivered |
| 0.35.3 | 2026-09-25 | Open questions marked in the view like the backlog |
| 0.35.4 | 2026-09-25 | Questions in a session: a narrow table, the questions listed below |
| 0.35.5 | 2026-09-25 | Every skill shows a view as it is |
| 0.35.6 | 2026-09-25 | Paths with `/` on every platform |
| 0.36.0 | 2026-09-25 | The same questions and the same report every time; `/factory-help` |
| 0.36.1 | 2026-09-25 | One id per question; the help marks where the project is |
| 0.36.2 | 2026-09-25 | The help as a numbered flow |
| 0.36.3 | 2026-09-25 | The flow starts with `/dca-new project` |
| 0.37.0 | 2026-09-25 | `/factory-run <wish>`: a sentence becomes a story that runs |
| 0.37.1 | 2026-09-25 | The question pass's findings carry fixed ids |
| 0.38.0 | 2026-09-25 | A test level per scenario; journey tests as guards (contract 9) |
| 0.38.1 | 2026-09-25 | The backlog requires a happy path too |
| 0.38.2 | 2026-09-26 | An open question is named by its id alone |
| 0.39.0 | 2026-09-26 | Adopt existing behaviour: map its tests, prove each can break |
| 0.38.3 | 2026-09-26 | The browser suite starts the application itself, on a free port (documentation, committed after 0.39.0) |
| 0.39.1 | 2026-09-26 | A small follow-up |
| 0.39.2 | 2026-09-26 | The browser suite starts the application from the first day |
| 0.39.3 | 2026-09-26 | Adoption finds a test class by its short name |
| 0.39.4 | 2026-09-26 | A test committed earlier is not the story's change |
| 0.39.5 | 2026-09-26 | An answer that changes a test is applied by the test stage |
| 0.39.6 | 2026-09-26 | A scenario's title is its browser test's name, checked by the gate |
| 0.39.7 | 2026-09-26 | An external interface names each field's type |
| 0.39.8 | 2026-09-26 | Delivered stays delivered |
| 0.39.9 | 2026-09-26 | Break patches with Windows line endings apply |
| 0.40.0 | 2026-09-26 | A run starts where the story's files say |
| 0.40.1 | 2026-09-26 | Scenario titles with quotes are recognised |
| 0.41.0 | 2026-09-27 | Update never links skills onto themselves; setup names the three reviewers |
| 0.41.1 | 2026-09-27 | The shared builder's changed files are checked against its hand-overs |
| 0.42.0 | 2026-09-28 | The review's high findings closed; an integration test level |
| 0.43.0 | 2026-09-28 | A DCA project names its method catalog and plan carrier |
| 0.44.0 | 2026-09-28 | The review's medium findings closed |
| 0.45.0 | 2026-09-28 | Deterministic installs: copies from a cache, links from a checkout |
| 0.46.0 | 2026-09-28 | The gate split from the CLI, one parser |
| 0.46.1 | 2026-09-28 | The review's small findings: names explained, internal stages marked |
| 0.47.0 | 2026-09-28 | The review's low findings and the greenfield run's gaps |
| 0.48.0 | 2026-09-28 | The plan reads the project's conventions file |
| 0.49.0 | 2026-09-28 | The story carries its state; the run folder is protocol only |
| 0.49.1 | 2026-09-28 | Deleted files raise no false alarm |
| 0.49.2 | 2026-09-28 | The project's runner copy finds the CLI beside its gate |
| 0.49.3 | 2026-09-28 | A stage the runner started knows it is meant |
| 0.49.4 | 2026-09-28 | A test put back to its red version is a restoration, not a new change |
| 0.50.0 | 2026-09-29 | Judge and documentation in one shared session; every stage is told where things are |
| 0.50.1 | 2026-09-29 | Skill links under old names are pruned |
| 0.50.2 | 2026-09-29 | A test the judge finds too weak goes back to the test stage, with a break as proof |
| 0.50.3 | 2026-09-29 | The builder sees an unlisted file; a refused re-check is a round |
| 0.50.4 | 2026-09-29 | A defect in a test's own code goes back to the test stage, not to a person |
| 0.51.0 | 2026-09-29 | One test process per command instead of one per test |
| 0.51.1 | 2026-09-29 | Cheap checks first, test suites last |
| 0.51.2 | 2026-09-29 | Test runs reused on an unchanged tree |
| 0.51.3 | 2026-09-29 | The pipeline writes the hand-over's file list |
| 0.51.4 | 2026-09-30 | A refused break keeps the earlier red proof |
| 0.51.5 | 2026-09-30 | The gate is the stage's test run — no suite run twice |
| 0.51.6 | 2026-09-30 | Hand-overs have a measure; the pipeline writes the plan's lines |
| 0.52.0 | 2026-09-30 | Leaner hand-overs; the stages' shared rules said once |
| 0.52.1 | 2026-09-30 | The measure counts only the stage's own text; the judge loads its review skills |
| 0.52.2 | 2026-09-30 | A stage may use the reading tools without asking |
| 0.53.0 | 2026-09-30 | Three reviews side by side in their own contexts; the judge converges |
| 0.53.1 | 2026-09-30 | `cd`, `echo`, `printf`, `pwd` without asking too (committed with 0.54.0) |
| 0.54.0 | 2026-09-30 | The judge's minor findings stay beside the story (`<story>.findings.md`) |
| 0.55.0 | 2026-09-30 | Invariants named in the plan, each with a unit test; the use case tested once at its port |
| 0.55.1 | 2026-10-01 | A test defect the session repaired itself causes no extra round |
| 0.56.0 | 2026-10-01 | A story's verbs come from the glossary, never from a translation — so two runs name the same operations |
| 0.56.1 | 2026-10-01 | The backlog looks up a new verb in the story's context; an ambiguous verb is decided by its effect |
| 0.57.0 | 2026-10-02 | Every invariant rule gets a unit test of its own, in a table the pipeline writes |
| 0.57.1 | 2026-10-02 | A build whose gate passed after the tests were rewritten holds for the pass; a refused round runs on from the stage that is out of date |
| 0.58.0 | 2026-10-02 | The story after which the epic's outcome event can happen says so (`publishes:`); the gate holds it to the epic's metric and to the code |
| 0.59.0 | 2026-10-02 | A delivered epic without a journey test is shown as unguarded; deciding against one is written down (`none:`) |
| 0.60.0 | 2026-10-02 | `/factory-discover`: from a problem to a report with sources and proposed epics, each with its outcome event |
| 0.60.1 | 2026-10-02 | The stage a later gate sent the story back to — alone, in the shared builder too — reads that gate's report; `factory.sh discover --check`; the outcome event's own file and an import are no raise, an event nested in its aggregate and constructed there is; `publishes:` on a story that did not introduce the event is named as such; an invariant line that names no element is skipped, a kind in parentheses is kept; a camel-cased test source set is no production code; the backlog check holds `publishes:` to the metric |
| 0.61.0 | 2026-10-02 | `update --adopt`: a method skill's copy the install did not make is taken over and follows the plugin from then on; an identical one without a question |
| 0.62.0 | 2026-10-03 | A foundation once (describe, set up), then the cycle (discover, backlog, run, decide, delivered) in `/factory-help`, with the backlog skill's argument forms among the commands; `status` lists every epic with its title, goal, outcome and discovery — an empty one's next step is cutting its stories — and carries the project description as it stands; `factory.sh discover --list`; `## Proposed description changes` in a discovery report, checked |
| 0.63.0 | 2026-10-03 | `/factory-backlog journey <epic>`: a delivered, unguarded epic gets its journey — the timeline from the delivered stories' operations and events to the outcome event, and the journey item as a draft, or the `none:` line; the status hint names this form with the epic, so a view acts on it without guessing, and a draft's hint names `/factory-backlog release <story>`; `/factory-help` lists it. Only a `## Journey` heading counts as the epic's journey section; a list-valued front-matter field of an epic is shown as text; an epic without a story shows no sums; `/factory-discover` without a topic lists the discoveries; the discovery gate reads `- Change:` as `- change:`, refuses an empty `## Proposed description changes` and names the position of that section only when both neighbours are there |
| 0.64.0 | 2026-10-06 | Shared stages are the default: one builder process for plan to tidy, one verifier process for judge and document — never the builder's; the profile's `stages: separate` or `run --separate-stages` starts one process per stage (`--shared-builder`/`--shared-verifier` are accepted and change nothing, `FACTORY_SHARED_*=0` separates one half). Claude's stages write `stream-json`, so a stage's output grows while it runs; the cost is read from the stream's result event. `factory.sh follow [--story] [--once --format json]` prints what the stage in flight reads, edits and runs, for Claude, Codex and OpenCode, whoever started it; `/factory-help` lists it |
| 0.64.1 | 2026-10-06 | A shared builder's and verifier's stages shown beneath them in `status --story` — split where the process loads each stage's skill, time and input and cache tokens from the stream, output and cost shared out (`≈`); the running stage named (`builder · test`), also in the JSON views |
| 0.64.2 | 2026-10-06 | `follow --process <name>` reads one process's output — also of a delivered story — and `follow --story <id> --all` every process in the order they began; a shared process's stages are headings (`── test`) |
