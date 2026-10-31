# Glossary — Bounded Context: rulebook

Every rule the factory holds a story to, by one id, placed in the flow of a story. The gate and the runner decide by
their rules; each stage's brief tells it its own. The rulebook decides nothing: it reads the rules where they are
written — every rule's file and where it is bound or placed, through delivery's `api`; the skills' text for the ids
it cites — and shows them, so a rule can be listed, linked and drawn, and two rules that say different things about one
trigger stand side by side.

Code: `dca_factory/rulebook/` — `domain/model/` flat, `application/show_rulebook.py` the one use case,
`application/shared/` the output ports, `adapter/outgoing/delivery/` and `adapter/outgoing/skills/` what it reads,
`adapter/incoming/cli/` `factory.sh rules`.

---

### Rule (rule)

**Definition:** One thing the factory holds a story to: its id, when it applies (trigger), how it comes out
(outcomes), why it exists (reason) and where it is written (source); for an instructed rule, what the stage is told.

**Type:** Value

**Related terms:** `Rule id`, `Enforcement`, `Outcome`, `Part`

### Rule id (rule id)

**Definition:** A rule's name for its life and after: `GATE-<CHECK>` for what the gate checks or does
(`GATE-TESTS-KEPT`, one per name a check reports under — `GATE-HAPPY-PATH` under `plan`), `RUN-<AREA>-<n>` for what
the runner decides (`RUN-ROUTE-3`), `STAGE-<STAGE>-<n>` for what a stage is told (`STAGE-PLAN-9A`, its number the
skill's own; `COMMON`, `FILES` and `BACKLOG` for what every stage, the hand-over files and the backlog contract say).
A rule that goes keeps its id as retired.

**Type:** Identifier

### Enforcement (enforcement)

**Definition:** Who holds a rule: `gate` — the story gate decides it, deterministically; `runner` — the runner decides
it; `instructed` — a stage is told it in its skill and holds it itself, checked only where a gate rule mirrors it.

**Type:** Concept

### Part (part)

**Definition:** Where a rule sits in the flow: a gate's `check`, what a passing gate does (`pass`), a `decision` of the
runner or of the gate outside a stage, or an `instruction` to a stage.

**Type:** Concept

### Outcome (outcome)

**Definition:** How a rule comes out, with what it says then: `pass`, `fail`, `skip`, `note`, `wait`, or `ask` — a
stage writes a decision record and stops.

**Type:** Value

### Trigger · Reason · Source

**Definition:** When a rule applies; why it exists; where it is written — the rule's file (`workflow/rules/…`) for a
rule of the gate or the runner, beside the place in the package that binds it (`<path>:<line>`), or — for what a stage is
told — the frame that places it (`workflow/every-stage.md`, a stage's file). A stage of the flow is written too: its file (`workflow/stages/<name>.md`) and what it is for.

**Type:** Value

### Flow (flow)

**Definition:** A story kind's way through the workflow's stages, as delivery publishes them (`StageRow`, each with
its file and what it is for): per stage the gate before it, what it is told, the gate after
it, what a passing gate does and what the runner decides there; the checks every gate holds said once. What no stage
holds — the run as a whole, the commit hook, every stage alike — stands outside the flow.

**Type:** Concept

**Operations:** show (`show_rulebook`) — the rules, at a stage or for a kind, each kind's flow and the problems

### Edge (edge)

**Definition:** Where an outcome sends a story, from the stage its rule sits at: an earlier stage (back), a later one,
the same one `again`, or `stop` — the run ends and a person looks. Written beside the rule as `goes=`. Delivery's run jumps by it
(see *Jump* in delivery's glossary) — an edge is what the factory does, not a description beside it.

**Type:** Value

### Fired (fired)

**Definition:** How a rule came out at a stage of one story — read from the gate report the runner filed for its last
gate run there; with the refusals the journal counts per name, the story's overlay on the flow.

**Type:** Value

### Marker (`<!-- rule: <id> -->`)

**Definition:** The line in a frame — `workflow/every-stage.md` or a stage file's body — where an instructed rule's
words go when a brief is assembled. The rule itself is its file (`workflow/rules/stage/<id>.md`, `part: told`, the
section and the stages and kinds it holds for, its words); one no frame places says where the rest of it stands
(`see:`). A marker in a skill is a problem: the words stand in the rule's file, never in a copy.

**Type:** Concept

### Citation (citation)

**Definition:** A rule id a skill names in its text outside a marker; one no rule has, or a retired one, is a problem.

**Type:** Value

### Problem (problem)

**Definition:** What does not hold in the rulebook itself: an id used twice, a stage no row has, a cited id no rule
has. `factory.sh rules --check` exits 1 on one.

**Type:** Value
