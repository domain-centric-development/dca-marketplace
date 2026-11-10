# Glossary — Bounded Context: delivery

What is built next, by whom it is decided, and how it is delivered: the backlog, the decisions a person takes, the
stages and their gates, the project description every stage reads, and what it all cost. One model — story, epic,
decision record, journal — shared by five features; the story moves draft → approved → delivered across them.

Code: `dca_factory/delivery/` — `domain/model/` flat, `application/<feature>/` one module per use case,
`application/shared/` the output ports, `adapter/incoming/` and `adapter/outgoing/`.

---

## Features

### Backlog (backlog)

**Definition:** What is to be built: epics and their stories, drafts written and released, journeys proposed for a
delivered epic.

**Type:** Feature

**Related terms:** `Epic`, `Story`, `Draft`, `Release`, `Journey` — use cases `release_stories`,
`backfill_created`, `check_backlog`, `run_backlog`

### Decisions (decisions)

**Definition:** What a run may not decide itself and a person does: a question answered, a delivery accepted or
corrected.

**Type:** Feature

**Related terms:** `Decision record`, `Answer`, `Acceptance`, `Correction` — use cases `answer_question`,
`accept_delivery`

### Delivery (delivery)

**Definition:** A story run through its stages, each closed by its gate, with the evidence and the journal it leaves.

**Type:** Feature

**Related terms:** `Stage`, `Gate`, `Evidence`, `Journal`, `Round`, `Delivery` — use cases `run_story`,
`integrate_story`, `reopen_story`, `prove_delivery`, `deliver_by_hand`, `confirm_owned`, `claim_story`, `check_spec`,
`show_spec_delta`, `take_back_delivery`

### Description (description)

**Definition:** The project description every stage reads: the product (overview), the technical decisions (tech),
the designed domain (domain).

**Type:** Feature

### Cost (cost)

**Definition:** What a story's delivery used, in tokens and in money: a process's usage measured, priced and booked
on the stories it worked on.

**Type:** Feature

**Related terms:** `Usage`, `Price` — use cases `book_request_cost`

### Setup (setup)

**Definition:** The pipeline put into a project and kept up to date: its files beside the gate, the tools' skill
folders — linked into a checkout or copied from a plugin cache —, the stack profile against what detection finds.

**Type:** Feature

**Related terms:** `Skill mode` (link or copy), `Proposal` — use cases `install_pipeline`, `refresh_pipeline`,
`check_detected_profile`, `write_detected_profile`; `factory.sh setup` and `update` are their command line

---

## Aggregate Roots

### Story (Story)

**Definition:** One work order small enough for a single run: acceptance criteria under keys, the feature it changes,
its dependencies. Its state is in its front matter: a draft until a person releases it, approved until a gate
delivers it, delivered after; history once delivered — what holds is the spec's. What it says — criteria, context, dependencies, what it
publishes, its status as written — is its `content` (`StoryContent`), read with it and never changed by it; the gate
checks it.

**Type:** Aggregate Root

**Identity:** `StoryId` — the `id:` of its front matter, else its folder's name

**Related terms:**
- `Epic` (referenced by its id — the folder the story stands in)
- `Decision record` (beside the story, referenced by the story's id)
- `Assumption` (Value Object, a line under `## Assumptions`)
- `Delivery` (Value Object, its delivered lines)

**Operations:** every change of its state is one of these, each guarded and raising its event; no adapter writes
a status past them.
- release (`release`) — a draft becomes approved, its release an answered assumption naming who and the request
  (`StoryReleased`);
- deliver by the gate (`deliver_by_gate`) — a released, adopted or unmarked story, built or adopted, delivered by
  the gate; a draft or an unknown status is refused (`NotReleased`), a superseded one too (`NothingToDeliver`)
  (`StoryDeliveredByGate`);
- deliver by hand (`deliver_by_hand`) — a story a person built, delivered and claimed by them
  (`StoryDeliveredByHand`); where the project requires a release (`Releasing`, the profile's `release: required`), a
  draft — or a story without `status:`, which then counts as one — is refused, by hand as by the gate;
- adopt on plan (`adopt_on_plan`) — the plan found every scenario holding: adopted, the plan's finding its answered
  line (`StoryAdoptedOnPlan`);
- split off (`split_off`) — the plan found some scenarios holding: they move into an adopted story `<id>-holds`,
  which it returns (`ScenariosSplitOff`, and `StoryAdoptedOnPlan` for the new one);
- take an answer (`take_answer`) — an answer a stage applied becomes an answered line, once per record (`AnswerTaken`);
- reopen (`reopen`) — a delivered story taken back for the correction it cites (`CitedCorrection`) (`StoryReopened`);
- take back a publication (`take_back_publication`) — a delivery published on its branch, taken back: what it was
  published over again (`PublicationTakenBack`);
- adopt for proof (`adopt_for_proof`) — a claimed delivery handed to the adopt path, the claim returned to be kept
  and carried by its event (`StoryAdoptedForProof`).

### Decision record (DecisionRecord)

**Definition:** A question a stage or a request's skill could not answer itself, kept beside its story (or the
project's own, without one): the options, a recommendation, and the person's answer once given. Open until answered;
answered, a stage applies it. An answer is never overwritten — a change of mind is a new question.

**Type:** Aggregate Root

**Identity:** `RecordId` — the `id:` of its front matter, else its file's name

**Related terms:**
- `Option` (Value Object — a key and its text)
- `Answer` (Value Object — the answer, by whom, when)
- `Acceptance` (a decision record that asks for a look at a delivered story)

**Operations:** every change of its state is one of these, each guarded and raising its event.
- ask for an acceptance (`ask_acceptance`) — a new record, open, asked at the stage that delivers
  (`AcceptanceAsked`);
- answer (`answer`) — once; the events carry who answered and what (`QuestionAnswered`; for an acceptance
  `DeliveryAccepted` where the answer begins with `accept`, else `CorrectionAsked`);
- choose (`choose`) — an option of an open record that offers it (`NotOpen`, `OptionNotOffered`);
- accept (`accept`) — an acceptance answered `accepted`;
- apply (`apply`) — the stage that applied an answered record (`NotAnswered` otherwise) (`AnswerApplied`).

**Queries — the record decides, never a copy of it:** whether it waits (`waits`), what was given (`given`),
whether an acceptance accepts (`accepts`) or asks for a correction (`corrects`), whether its answer backs a change
of what holds (`backs_change`), and the sentence it leaves in its story (`answer_sentence`, over its
`OptionLine`s). A correction's code is one of `ReasonCode`.

### Epic (Epic)

**Definition:** A body of work with an intent, a goal, an outcome event to measure it (`metric:`) and a domain contact;
over once its stories are delivered.

**Type:** Aggregate Root

**Identity:** `EpicId` — the epic's folder, or the `id:` of its `epic.md`

**Operations:** create from a proposal (`epic-from`) — at discovery's release

---

### Request (Request)

**Definition:** A person's press, kept as one file until it is done: an asynchronous command for one of the use cases
— write a wish, release, answer, accept, correct, run, stop. Two processes change one request — the page and the cli
queue it, the runner takes, parks, fails, queues again and settles it — so it is one consistency boundary. Queued
until one worker takes it, running until its skill ends: waiting where it asked a person, failed where it ended
without a result, done where it did its part — then its file goes. What it asks (its kind, what it names, the
person's words) is read with it and never changed by it; listings and the runner read it as `RequestFacts`, a read
model. The files under `.dca-factory/requests/` are its inbox and its repository (`RequestRepository`); the runner
takes the next one through `RequestQueue`, works it with the use case `work_request`, and `settle` decides which press
needs no judgement and executes its use case.

**Type:** Aggregate Root

**Identity:** `RequestId` — `<stamp>-<kind>`, its file's name

**Related terms:** `RequestState` (queued, running, waiting, failed, done, dropped), `Worker` (who works it), `Why` (why it
failed), `Decision record` (the record it waits on, by its path)

**Operations:** every change of its state is one of these, each guarded (`RequestNotInState`) and raising its event.
- write (`written`) — a new request, queued (`RequestQueued`);
- take (`take`) — one worker takes a queued request, its attempt counted (`RequestTaken`);
- wait (`wait`) — a running request whose skill asked a person, only on the record that asks (`NoRecord`)
  (`RequestWaiting`);
- wake (`wake`) — a waiting request whose records are answered, queued with the answers; ask again (`ask_again`) —
  one whose record is gone (`RequestQueued`);
- requeue an orphan (`requeue_orphan`) — running for another worker than the one that holds the claim now; requeue a
  stopped one (`requeue_stopped`) — its process stopped by a signal (`RequestQueued`);
- fail (`fail`) — a request in hand that no longer holds or whose skill ended without a result; leave uncommitted
  (`leave_uncommitted`) — its skill did its part and its commit was refused, its work marked done (`RequestFailed`);
- retry (`retry`) — only a failed one, queued again as written (`RequestQueued`);
- settle (`settle`) — worked to its end, its file gone (`RequestSettled`);
- take back (`drop`) — a person removes one that does not run, its file gone (`RequestDropped`; `allows`,
  `RequestOperation`).

**Queries — the request decides, never a copy of it:** whether it is queued (`queued`), waits (`waiting`), is in
hand (`in_hand`), is an orphan of another worker (`orphaned_by`), and what a person may do with it (`allows`).

## Value Objects

### Story id (StoryId) · Record id (RecordId) · Epic id (EpicId)

**Definition:** The name of one story, decision record or epic for its whole life — one word, no path.

**Type:** Value Object

### Story status (StoryStatus)

**Definition:** Where a story stands in its life: `draft`, `approved`, `delivered`, `superseded`, `adopted` (the
code exists — the adopt path checks it and builds nothing).

**Type:** Value Object

### Decision state (DecisionState)

**Definition:** Where a record stands: `open` (no answer), `draft` (an answer section not yet complete), `answered`,
`applied`.

**Type:** Value Object

### Option (Option) · Option key (OptionKey)

**Definition:** One choice a record offers, under a key of one to three letters or digits (`a`, `B`, `1`).

**Type:** Value Object

### Answer (Answer)

**Definition:** The person's answer to a record — an option's key or their words —, who gave it and when.

**Type:** Value Object

### Person (Person)

**Definition:** Who asks or answers, as they name themselves — a repository's `user.name` where they did not say.

**Type:** Value Object

### Moment (Moment)

**Definition:** When something happened, in UTC to the second (`2026-10-25T10:00:00Z`).

**Type:** Value Object

### Assumption (Assumption)

**Definition:** A line under a story's `## Assumptions`; `answered:` where a person settled it — a release by a
request is one.

**Type:** Value Object

### Delivery (Delivery) · Delivered on (DeliveredOn) · Delivered by (DeliveredBy)

**Definition:** A story's delivered lines: when (`delivered:`, as written) and who claims it — the `Deliverer`
(`gate`, `hand` with the `Person`, or `unknown` for a story delivered before the line existed or under a word the
factory does not know, which a save leaves as written).

**Type:** Value Object (`Deliverer`: Enum)

### Gate pass (GatePass)

**Definition:** Whether the pass of the gate that delivered a story is on record — a delivery by the gate with its
pass on record has nothing to prove.

**Type:** Value Object

### Usage (Usage)

**Definition:** What one process used: tokens read, read from the cache, written to the cache, written — on a model —
and its cost where it was priced. A request's usage is booked in even shares on the stories it worked on.

**Type:** Value Object

**Operations:** share (`share`)

### Stack profile (StackProfile)

**Definition:** The project's stack profile as delivery reads it, its pairs in the profile's order: the model a tool
runs a stage on (`model.<tool>.<stage>`, else `model.<tool>`, never another tool's), the heads of the commands a stage
may run, the skills it names as carriers, the judge's perspectives. The file is the project's; what its keys mean for
a run is decided here.

**Type:** Value Object

**Operations:** model for (`model_for`), command heads (`command_heads`), carriers (`carriers`), perspectives
(`perspectives`)

### Perspective (Perspective)

**Definition:** One way the judge looks at a story — the three built-ins `ddd`, `hexagonal`, `clean-code` and any the
profile's `reviews:` adds — with the skill it looks with (`review.<name>:`, else `review-<name>`).

**Type:** Value Object

### Tool name (ToolName) · Skill name (SkillName) · Profile key (ProfileKey) · Profile value (ProfileValue)

**Definition:** An agent tool by its record's name; a skill by its folder's name without its plugin; a key of the
profile and what the profile says under it, as written.

**Type:** Value Object

### Run argument (RunArgument) · Argument meaning (ArgumentMeaning)

**Definition:** What follows `/factory-run`, and what it asks for: nothing is the backlog; one word naming a story is
that story; one word naming none is an unknown id — refused, never taken for a new story, so a typo stays a typo;
more than one word is a wish the backlog turns into a story. A page's button that offers one unknown word offers it
as a wish, since the page wrote the words itself.

**Type:** Value Object

**Operations:** meaning (`meaning`)

### Refusal kind (RefusalKind)

**Definition:** What a refused gate cost: `form` when every check it names is about how a hand-over is written
(`FORM_CHECKS`: files listed, story pass, tests mapped, test titles, plan levels, levels, documented, decisions,
reviews, layout) — a round spent with the work right —, else `substance`.

**Type:** Value Object

### Current pass · Journal marks (JournalMarks)

**Definition:** Which of a story's hand-overs say where it stands, read from the journal's order alone: each file by
the number of its latest write (a file gated after it is written also by its gate's later pass or hold), none that
was marked an earlier pass's since. Up the run order, the first file older than one before it ends the current pass —
a stage that ran again makes every later file history. The rules: the workflow's (`Workflow.written_at`,
`Workflow.holding`).

**Type:** Concept

### Test edit (TestEdit)

**Definition:** What a story did to a test that existed before it: `kept` (lines added only), `arranged` (rewritten,
every assertion kept), `switched off`, or `changed` what it expects — in that order of weight, switched off first.
What a diff of the test showed (`TestDiff`) decides it (`TestDiff.edit`).

**Type:** Enum, decided by a Value Object (`TestDiff`)

### Claim · Worker (Worker) · Meeting (Meeting) · Fate (Fate)

**Definition:** Several factories on one backlog (WP-93) claim a story by its branch on a shared remote. A worker is a
factory that claims — a person on a host. Where a claim exists already, the meeting is `own` (this factory's), a
`collision` (the same id claimed for another epic or title — a person gives one another id) or `others` (another
factory runs it). After a fetch a claim's fate is to hold, to be `released` (its story is delivered on the remote main
line) or to be an `orphan` (the main line has no such story, and no published mark or story branch says it is on its
way) — what a fetch traced of the claim decides it (`ClaimTrace.fate`). Only a worker's own claim is released
without force; a delivered story's id never comes free again — the next id follows the highest in use, as wide as it
(`IdPrefix`). The rules are the values' own (`Claim.meets`, `Claim.released_by`, `ClaimTrace.fate`).

**Type:** Value Object

### Named kind (NamedKind)

**Definition:** A story's `kind:` as its front matter names it — `journey`, `task`, or none (any other word names
none) —, and what the story is by it: `journey` — a guard over an epic's delivered stories —, `task` — a change no
actor sees —, an adoption where the story's status is `adopted` — behaviour the project already has —, else a story.
The kind decides the stages it runs.

**Type:** Enum

**Operations:** kind (`kind`)

### Words (Words)

**Definition:** What a person typed into a request: at most `MAX_LENGTH` characters, no control character but a line
break, a return and a tab, no direction mark — what is read is what was shown. A run takes them as the request's
data, never as instructions to it.

**Type:** Value Object

### Handed file (HandedFile) · Handed file id (HandedFileId) · Project path (ProjectPath)

**Definition:** A file a person hands over beside their words — a picture, a PDF or a text, known by its content and
kept under a reduced name; at most `MAX_FILES` go with one request (`HandedFiles`), none with a kind that takes no
words. Its id is the factory's own, drawn fresh (`fresh`); the files no live request names go once older than
`KEEP_DAYS`. A project path is a path in the project with `/` between its folders.

**Type:** Value Object

**Operations:** kind of (`kind_of`), draw an id (`fresh`)

### Shown path (ShownPath) · Shown file (ShownFile) · Refusal (Refusal)

**Definition:** A file the page shows: its path relative, without `..`, beneath one of the places a file is shown
from (`shown_places`: the project's description and backlog, and the factory's own folder); shown as a picture, a
PDF or a text, or a mockup as a page of its own. A refusal says why not — of the wrong form, nothing there, too
large, of no kind shown —, never in a protocol's numbers.

**Type:** Value Object

**Operations:** places (`shown_places`), show (`of`)

### Shot (Shot) · Taken file (TakenFile) · Run origin (RunOrigin)

**Definition:** A picture a story's end-user tests took, brought to the story's place: a picture by its content, not
older than the run that took it — a run the step reused counts from the window before the step (`taken_since`) —,
the newest first, at most `SHOWN` (`kept`, `shown`), named for what took it.

**Type:** Value Object

**Operations:** taken since (`taken_since`), keep (`kept`), show (`shown`), name (`shot_name`)

### Tree observation (TreeObservation) · Observed file (ObservedFile) · Changed file (ChangedFile)

**Definition:** The working tree at one edge of a stage window, taken once at its start and once at its end: the files
that differ from HEAD with the sha256 of their bytes (`Digest`, `deleted` for one gone) and whether git tracks them
(`tracked`), HEAD, and — at the end, and at the start of a story's first window — the tree object of everything as it
is (`ObjectName`). A stage's changes are the difference of its two edges; the story's are its base tree against the
end's tree. An observation without content digests (`Hashing`) proves nothing and is read as none.

**Type:** Value Object

**Operations:** what changed since an earlier edge (`changes_since`, the paths HEAD itself moved counted too),
whether HEAD moved (`head_moved_from`), the digests by path (`digests`)

### Reach (Reach) · Network (Network) · Shell head (ShellHead) · Home folder (HomeFolder)

**Definition:** What one run may reach. A stage builds: its shell runs the project's commands, the common reading
verbs and the whole cli, with the network. A request's skill reads and records: the cli flags and factory verbs of
the dialog skills, no build and no verb that takes a path, offline — unless its kind researches the web, which gives
it the network and the tools to search. No run reads the home's secret folders. A person's words widen none of it;
how each tool is told is the adapters'.

**Type:** Value Object

**Operations:** a stage's (`stage`), a request's (`request`)

### Guarded set (GuardedSet) · Guarded pattern (GuardedPattern) · Guarded change (GuardedChange)

**Definition:** What decides whether a gate is green, kept out of the judged stage's reach: the stack profile (always)
and the globs of the profile's `guarded:` — the commit hook, the architecture suite's rule selection and test classes.
A guarded change is one path of it a plan announces under `## Guarded changes`, with its reason; only those a stage
may change, and the acceptance shows them first.

**Type:** Value Object

**Operations:** whether a path is guarded (`covers`), the globs that cover an announced path (`opened`), what the
runner walls off for a stage — every glob, an opened one file by file without the announced paths (`walled`); the
guarded paths a story changed and the ones of them nobody announced (`GuardedFacts.touched`, `unannounced`)

### Refusal history (RefusalHistory) · Gate refusal (GateRefusal) · Fresh restart (FreshRestart) · Repetition

**Definition:** A story's refused gates as the runner met them, with the fresh restarts between them, since its rounds
were last counted from nought. A refusal repeats the one before when the stage, the failed checks and the failing
tests are the same — the report's text is never compared. A repeat starts the next round fresh; a repeat after the
fresh restart stops the run for a person.

**Type:** Value Object

**Operations:** whether one refusal repeats another (`GateRefusal.repeats`), the last refusal against the one before
(`RefusalHistory.repetition`: new, repeated, repeated after a fresh restart)

---

## Concepts

### Draft

**Definition:** A story with `status: draft`: written, not yet released — no stage runs it.

**Type:** Concept

### Release (release)

**Definition:** A person's go for a draft: it becomes approved and runs. The factory releases a draft itself only
where its question pass ran on it as it stands and no record holds it.

**Type:** Concept

### Question pass (questioned)

**Definition:** The pass of a backlog skill over the drafts it wrote, asking what they leave open; the factory marks
each draft it covered with the story's digest (`questioned`).

**Type:** Concept

### Journey

**Definition:** An end-to-end path through a delivered epic, proposed as an item of its own (`kind: journey`); spec
keeps the journeys that hold.

**Type:** Concept

### Acceptance

**Definition:** A decision record that asks a person to look at a delivered story: answered `accepted`, or a
correction with a reason code.

**Type:** Concept

### Stage · Gate · Round

**Definition:** A step of a story's run — plan, test, build, tidy, judge, document — closed by its gate, the
deterministic check that lets the next stage start; a round is one more pass after a refusal. The route — which
stage runs in its own process and which a shared window carries, which a kind skips, the gates around each, the
reviews before the judge for every kind that changes the code (an adoption changes nothing and gets none), where a
refusal, the build stage or the judge sends the story back (the judge's `back:` holds for a resumed story too), when
the rounds did not converge — is the workflow's
(`Workflow.steps`, `jump`, `after_refusal`, `judged_back`; the readers of a gate's report and a verdict are those values'); the use case `run_story` — the executive of the story's process — walks it, reading where the story stands from its journal (the store `StoryRunJournal`) and taking each step through the port `StageSteps`, a round one more pass of its loop,
and `integrate_story` brings the delivered story onto the main line through `StoryIntegration`.

The run is a **process manager** in the shape the guide names (no marker): `run_story` is its executive — it decides
each next step with the workflow and holds no state of its own —, the journal is its tracker (a store), every step a
command through a port; where a step is another use case (the integration), the composition root wires that use
case behind the port. A round is counted in one place; `Rounds` decides whether they converged. The run, a gate and a
merge of the main line end in outcomes, never in exit codes: `RunOutcome` (ran through, failed, not set up, waits for
a person, at a limit, checkout taken, changed under it), `GateOutcome` (passed, refused, waits for a person) and
`MergeOutcome` (merged, conflicts, failed) — the runner's adapter translates them to and from its exit codes.

The factory's own steps ask for a stage by its **role** (`Role`: plans, tests, builds, tidies, judges, delivers,
adopts, integrates — the stage file's `role:`), never by its name: `Workflow.role`, and `stage_of` for an adapter.

How the project's policy ranks a check is a `Requirement` — undeclared (every check decides), required, or optional
(red is reported and does not decide).

**Type:** Concept

### Jump (Jump) · Target (Target) · Next (Next)

**Definition:** Where an element of the workflow — a gate's rule, a runner's decision — sends a story: the rule
(`RuleId`, `GATE-RED-PROOF`) and its targets for the outcome it came to, each a stage, `again` or `stop`, as its
`goes=` says. The workflow turns jumps into the next step (`Next`: a stage, or none — the run ends): a refused gate
by the rules of its failed checks (`after_refusal` — `stop` beats every way, else the earliest stage any of them or the
story's state names), a runner's decision by its own rule (`jump`), a choice the run's facts make (the judge's
`back:`) only within the rule (`chosen`). The runner names no stage it goes to; it asks the rule.

**Type:** Value

### Workflow rule (WorkflowRule) · Rule id (RuleId) · Outcome (Outcome) · Workflow rule repository (WorkflowRuleRepository)

**Definition:** A rule of the gate or the runner as data: its id (`GATE-<CHECK>`, `RUN-<AREA>-<n>`), the part of the
code that binds it (check, pass action, decision), when it applies and why, its outcomes — each with what it means and
where it sends the story (`goes`) — and the stages, kinds and report names where it is narrower than its code. An
aggregate, kept by the `WorkflowRuleRepository`: Markdown files under `workflow/rules/` today, another store later. The code
binds a rule by its id and says *how* it is checked or decided; the rule says *what* it holds and *where* the story
goes. A rule that goes keeps its file, `retired:` with the reason. Whether a target is a stage is the workflow's
question: the rules are loaded after it, and one that sends a story to no stage of it stops the load. What a stage
is *told* is a rule too (`STAGE-<STAGE>-<n>`, `part: told`): no outcome, its words the file's body, its section and
the stages and kinds it holds for; a frame places it, and one no frame places says where the rest of it stands
(`see:`).

**Type:** Aggregate

### Workflow (Workflow) · Workflow name (WorkflowName) · Workflow repository (WorkflowRepository)

**Definition:** The stages a story runs through, in their order, each with what it writes, the shared window that may
carry it, the kinds that run it, its traits (gated, gated after its file, tested, red, listing its files, guarded,
running the suite, in the run order), its role, the profile commands its gate runs and the hand-overs it weighs —
validated as a whole: each stage named once, each hand-over written by one stage, each file a gate weighs written by
a stage of it, each role played by one stage (`InconsistentWorkflow`; a role nobody plays is `MissingRole`). An
aggregate root without a transition: a person changes the stage files, the factory reads them as one unit — the
consistency boundary of those invariants.
An aggregate named `delivery`, kept by the `WorkflowRepository`: one Markdown file per stage under `workflow/stages/`
today, another store later. Every question about a stage — a kind's run order, a stage's file, a window's stages — is
the workflow's; its methods answer it (the route, the current pass), the domain services take it (`KeptChecks`, `StoryStanding`),
the composition root loads it once per process (`pipeline_workflow.load`, then the rules), and what registers against
the stages — the gate's checks, its pass actions — is placed once it is loaded. A stage's file carries its frame too —
what the stage is told, around its told rules, each rule a `<!-- rule: <id> -->` line where its words go — and
`workflow/every-stage.md` the frame every stage reads first.

**Type:** Aggregate

### Stage brief (StageBrief) · Brief (Brief) · Told (Told) · Measure (Measure) · Carrier (Carrier)

**Definition:** What a stage is told for one story, decided over the workflow and the rules: the stage (what it is
for, what it writes, the window that carries it), every stage's frame and then its own with each told rule's words
where its marker stands — a rule that does not hold for the story's kind left out, a section all of whose rules were
left out left out whole, a told rule no frame places after them —, the gate rules its work is measured by
(when each applies, what a refusal by it says) and the skills the profile names for its craft, its guard, its
frontend craft and the method's knowledge. The domain service `StageBrief` takes the workflow; the use case `show_brief` gathers the story's
kind, the rules and the profile; `factory.sh brief <story> <stage>` prints it, Markdown or JSON. The same story and
stage give the same brief. It holds what every stage is told (`common`) apart from the stage's own (`own`): the runner
writes the first once per window, each stage's own beside it, into the story's evidence folder under `brief/`, and
names both files in the stage's prompt; `<stage>.digest` beside them is what the stage's hand-over names on its first
line (`brief: <digest>`), and the gate after the stage compares (`GATE-BRIEF`, `Workflow.briefed_at`).

**Type:** Domain service

### Check · Finding (Finding) · Stage evidence (StageEvidence)

**Definition:** A gate is a set of checks, each a domain service over the story — the aggregate `Story`, its
`content` what the gate reads — and its evidence: `StoryChecks`, `ProfileChecks`, `BacklogChecks`, `DecisionChecks`,
`TestChecks`, `DesignChecks`, `ThenChecks`, `KeptChecks`, `SpecChecks`, `DeliveryChecks`, `IntegrationChecks`,
`BreakChecks`, and `ProfileChecks` over the workflow. What concerns no story is a method of the value it reads: a
suite's run (`SuiteJudged.of`), a command's (`CommandRun.finding`, `verdict`), the commit's snapshot and parity
(`Snapshot`, `ParityFacts`, `CheckKeys` in `change`), the profile against the gate (`GateRelease`), a break
(`BreakResult`, `RuleProof`), a test run (`TestsJudged.of`), the acceptance (`AcceptanceStep`). The use case `check_stage` registers them against the workflow's stages and runs them, those that start
no process first; what they run or write goes through output ports (`StageTests`, `StageRuns`, `StageMarks`,
`DecisionStamps`, `StageDelivery`). Outside a stage the same checks run as use cases of their own: `check_backlog`
over every story not yet done (`BacklogEntries`), `check_change` over a commit or the working tree (`ChangeIndex`,
`StageRuns`) and `check_parity` over the reports of every implementation (`ParityReports`). A check returns findings: passed, failed, skipped (unproven),
noted, or waiting for a person — and what it says, for a refusal the stage's next instruction. What a check alone
needs and only reads — the profile, the run folder, the epic, the context map — it asks the domain gateway
`StageEvidence`; a story naming no epic there is gets a fact, so the `epic` check refuses it and the others run.

**Type:** Concept

### Domain event · Delivery event (DeliveryEvent)

**Definition:** Something that happened to a story, a decision record or a request, named in the past tense and raised by the
aggregate in the operation that made it happen — every event of the context carries its moment and the story it
concerns (`DeliveryEvent`), or none for a record of the project's own. A use case saves the aggregate and publishes
its events in one transaction; the journal records each as a line of kind `event` — the story's journal, or the
factory's own. The journal is what reads them today: a person, and the views over it.

**Type:** Concept

### Evidence · Journal

**Definition:** What a run leaves to prove it: the reports and snapshots, and the story's journal — one line per event,
the story's record.

**Type:** Concept
