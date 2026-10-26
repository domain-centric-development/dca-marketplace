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

---

## Aggregate Roots

### Story (Story)

**Definition:** One work order small enough for a single run: acceptance criteria under keys, the feature it changes,
its dependencies. Its state is in its front matter: a draft until a person releases it, approved until a gate
delivers it, delivered after; history once delivered — what holds is the spec's.

**Type:** Aggregate Root

**Identity:** `StoryId` — the `id:` of its front matter, else its folder's name

**Related terms:**
- `Epic` (referenced by its id — the folder the story stands in)
- `Decision record` (beside the story, referenced by the story's id)
- `Assumption` (Value Object, a line under `## Assumptions`)
- `Delivery` (Value Object, its delivered lines)

**Operations:** release (`release`) — a draft becomes approved, its release an answered assumption; deliver
(`deliver`); reopen (`reopen`) — a delivered story taken back for a correction; adopt for proof
(`adopt_for_proof`) — a claimed delivery handed to the adopt path, the claim returned to be kept; deliver by hand
(`deliver_by_hand`) — a story a person built, delivered and claimed by them

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

**Operations:** answer (`answer`); accept (`accept`) — an acceptance answered `accepted`; correct (`correct`) — an
acceptance answered with a reason code; apply (`apply`) — the stage that applied the answer stamps it

### Epic (Epic)

**Definition:** A body of work with an intent, a goal, an outcome event to measure it (`metric:`) and a domain contact;
over once its stories are delivered.

**Type:** Aggregate Root

**Identity:** `EpicId` — the epic's folder, or the `id:` of its `epic.md`

**Operations:** create from a proposal (`epic-from`) — at discovery's release

---

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

**Definition:** A story's delivered lines: when (`delivered:`, as written) and who claims it — `gate`, `hand:<who>`,
or nothing for a story delivered before the line existed.

**Type:** Value Object

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

### Kind word (KindWord)

**Definition:** A story's `kind:` as written, and what the story is by it: `journey` — a guard over an epic's
delivered stories —, `task` — a change no actor sees —, an adoption where the story's status is `adopted` —
behaviour the project already has —, else a story. The kind decides the stages it runs.

**Type:** Value Object

**Operations:** kind (`kind`)

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
the rounds did not converge — is the domain service
`StoryRoute`; the use case `run_story` walks it through the port `StoryStages`, a round one more pass of its loop,
and `integrate_story` brings the delivered story onto the main line through `StoryIntegration`.

**Type:** Concept

### Check · Finding (Finding) · Stage evidence (StageEvidence)

**Definition:** A gate is a set of checks, each a domain service over the story as the gate reads it (`StageStory`)
— `StoryChecks`, `ProfileChecks`, `BacklogChecks`, `DecisionChecks`, `TestChecks`, `DesignChecks`, `KeptChecks`,
`SpecChecks`, `DeliveryChecks`, `IntegrationChecks`, `TestVerdicts`, `SuiteChecks`, `BreakChecks`, `ChangeChecks`,
`AcceptanceRules`. The use case `check_stage` registers them against the stage table and runs them, those that start
no process first; what they run or write goes through output ports (`StageTests`, `StageRuns`, `StageMarks`,
`DecisionStamps`, `StageDelivery`). Outside a stage the same checks run as use cases of their own: `check_backlog`
over every story not yet done (`BacklogEntries`), `check_change` over a commit or the working tree (`ChangeIndex`,
`StageRuns`) and `check_parity` over the reports of every implementation (`ParityReports`). A check returns findings: passed, failed, skipped (unproven),
noted, or waiting for a person — and what it says, for a refusal the stage's next instruction. What a check alone
needs and only reads — the profile, the run folder, the epic, the context map — it asks the domain gateway
`StageEvidence`; a story naming no epic there is gets a fact, so the `epic` check refuses it and the others run.

**Type:** Concept

### Evidence · Journal

**Definition:** What a run leaves to prove it: the reports and snapshots, and the story's journal — one line per event,
the story's record.

**Type:** Concept

### Request (request)

**Definition:** A person's press, kept as one file until it is done: an asynchronous command for one of the use cases
— write a wish, release, answer, accept, correct, run, stop. No term of the model: the folder is an incoming adapter
and a store; the runner takes the next one through `RequestQueue`, works it with the use case `work_request`, and
`settle` decides which press needs no judgement and executes its use case.

**Type:** Concept

**Operations:** write (`write`), take back (`drop`), retry (`retry`), settle (`settle`), work (`work`)
