# factory-backlog — the questions for a story from a wish

A wish is a user story in the person's words, handed over by `/factory-run <words>`. The skill drafts the
story from it, then asks **only the open entries below — all at once, in this order, word for word** —
followed by what the question pass (the skill's step 6) turns up, in that list's order. Nothing is asked
later; an answer goes where the entry says.

Each entry has the same fields: **look up** (where the answer already is — found there, the question is
not asked), **asked** (when the question is put at all), **question** (word for word), **options**,
**default** (the first choice offered, `—` where there is none) and **answer goes to**. A question that
depends on an answer still open in the same pass is asked with its condition in front ("For a new epic:
…"), and its answer is dropped where the condition turns out false.

**The question pass's findings** come after the entries, one question at most per item of the skill's step 6,
in that list's order, with the item's id — PASS-CONTEXT, PASS-SURFACE, PASS-TECH, PASS-DEPENDENCY, PASS-INPUTS,
PASS-DEFAULTS, PASS-FAILURE, PASS-STATE, PASS-CHANGED, PASS-ALREADY-GREEN, PASS-ABUSE, PASS-COVERAGE,
PASS-OUT-OF-SCOPE — and in the catalogue's language, like the entries. An item that turns up nothing asks
nothing. What a finding says depends on the code and the description; which ids it may carry, their order and
their number do not.

### WISH-EPIC
- look up: —
- asked: always
- question: Which epic does this story belong to?
- options: every epic under the backlog by its folder name, in the backlog's order · a new epic, with this story as its first
- default: —
- answer goes to: the folder the story is written into

### WISH-EPIC-INTENT
- look up: —
- asked: when WISH-EPIC is "a new epic", or is itself open in this pass
- question: For a new epic: why should this work exist — the problem someone has?
- options: —
- default: —
- answer goes to: `intent:` in the new `epic.md`

### WISH-EPIC-GOAL
- look up: —
- asked: as WISH-EPIC-INTENT
- question: For a new epic: what is true for that someone once the epic has delivered?
- options: —
- default: —
- answer goes to: `goal:` in the new `epic.md`

### WISH-EPIC-METRIC
- look up: the events the project publishes (the designed map, the code)
- asked: as WISH-EPIC-INTENT
- question: For a new epic: which event does the project publish when the epic has worked for someone — the event whose appearance in production is the evidence?
- options: an event the project publishes, where one fits · none yet — the event is part of the work
- default: —
- answer goes to: `metric:` in the new `epic.md`

### WISH-EPIC-CONTACT
- look up: the `domain_contact:` of the other epics
- asked: as WISH-EPIC-INTENT
- question: For a new epic: who answers questions about it?
- options: the domain contact the other epics name, where they name one person
- default: —
- answer goes to: `domain_contact:` in the new `epic.md`

### WISH-CONTEXT
- look up: the designed map (`project/domain.md`) — one context only means no question
- asked: when the map carries more than one context
- question: Which bounded context does the behaviour belong to?
- options: the contexts of the designed map, in its order, the one the draft names first
- default: the one the draft names
- answer goes to: `context:` in the story

### WISH-CRITERIA
- look up: —
- asked: always
- question: Are these the acceptance criteria — the rules and scenarios drafted from your words?
- options: the draft, shown in full · the draft with your changes
- default: the draft
- answer goes to: the story's `## Acceptance criteria`

### WISH-RELEASE
- look up: —
- asked: always
- question: Run it now, or keep it as a draft?
- options: run it now · keep it as a draft
- default: run it now
- answer goes to: `status: approved` (run it now) or `status: draft`; `/factory-run` runs an approved story at once
