# dca-craft

Craft skills and agents that are **independent of the architecture style**: how a test, a name, a
decision record, a glossary, a context map and a review are done. Usable on any project; nothing in
the skills or agents names an artifact of Domain-Centric Architecture. That is what makes its
reviewers an **outside view** — they read what any project has: the code, the glossary, the context
map, `AGENTS.md`.

It pairs with [dca-core](../dca-core/), which adds the DCA method, and with
[dca-factory](../dca-factory/), whose stages use these skills as carriers where they are installed.

## Start here

Pick the skill for what you are about to do — `/tdd` before writing new behaviour, `/clean-code`
while editing, `/adr` when a decision needs to outlive the conversation, `/e2e-testing` when a
user-visible flow needs a test (or a project has no browser runner yet), `/ubiquitous-language` when
a term enters the model, `/context-map` when a context or a relationship changes, one of the three
`/review-*` perspectives before a change is merged. Nothing has to be set up first.

## What's inside

### Skills (9) — applied while writing and reviewing

| Skill | Purpose | When it triggers |
|---|---|---|
| `/tdd` | Red-Green-Refactor workflow guidance | Adding new behaviour |
| `/clean-code` | Naming, function size, SLAP, smells, Boy-Scout-Rule | Any code edit |
| `/adr` | Architecture Decision Records (Michael Nygard format, immutable after Accepted) | Non-trivial architectural choice |
| `/e2e-testing` | The end-user-testing craft: Page Objects, stable selectors, one flow per test, explicit waits, diagnosis-first when a test breaks — and setting up a browser runner where there is none, ending in a smoke test shown to fail | Adding or fixing an end-user test; a project without a runner |
| `/ubiquitous-language` | One glossary per bounded context, naming consistency, polysemy | Adding or renaming a domain concept |
| `/context-map` | The designed strategic map: relationship patterns, subdomain types, the map's structure; draft from the code, update, validate against the code, explain a pattern | Introducing a context, changing an integration |
| `/review-ddd` | The **ddd** review perspective: real invariants, entity vs. value, aggregate boundaries, ubiquitous language, event hygiene, repository vs. store | Reviewing a change from the model's point of view |
| `/review-hexagonal` | The **hexagonal** review perspective: dependency direction, port granularity, adapter direction, framework leaks, input-port shape, translation at the edge | Reviewing a change from the ports-and-adapters point of view |
| `/review-clean-code` | The **clean-code** review perspective: naming, function size and SLAP, SOLID, smells, DRY with judgement | Reviewing a change for readability |

### Agents (4) — the same craft in an isolated context

| Agent | Applies | Adds |
|---|---|---|
| `e2e-tester` | `/e2e-testing` | own context, write tools — for a long test-writing session |
| `ddd-reviewer` | `/review-ddd` | own context, read-only tools — no "fix" slips into a review |
| `hexagonal-reviewer` | `/review-hexagonal` | the same, for the hexagonal perspective |
| `clean-code-reviewer` | `/review-clean-code` | the same, for the clean-code perspective |

**Knowledge lives in the skill, isolation in the agent.** Each agent is a thin wrapper that applies
its skill and adds nothing to it: an agent exists only in a tool that has agents, so craft held in
an agent alone would be unavailable everywhere else. Where agents exist, the three reviewers can run
in parallel, each in its own context — overlaps are real findings, divergences judgement calls.

## Where a project's conventions are

The skills read the conventions file the project instructions (`AGENTS.md`) name, and the designed
context map and the glossary where those instructions place them. Without such a line they fall
back to sensible defaults — `docs/context-map.md` for the designed map, `glossary.md` beside each
context's code — and to what the code itself shows.

## Pairing with dca-core

With [dca-core](../dca-core/) installed, the method's skills use these as their craft: the modelling
skill enters a new term through `/ubiquitous-language`, the description skill writes the designed map
through `/context-map`, and `dca-review` adds the DCA conformance review beside the three general
perspectives here. The pointers run that way only: nothing here depends on dca-core, and a check in
the marketplace keeps DCA artifacts out of this plugin's skills and agents.

## What this plugin deliberately does NOT include

- **Anything specific to one architecture style** — see dca-core for DCA.
- **Code generators / scaffolds.**
- **Formatter / static-analysis replacement.**
- **BDD / Cucumber** — separate concern, not yet captured here.

## Installation

```
/plugin marketplace add domain-centric-development/dca-marketplace
/plugin install dca-craft@dca-marketplace
/plugin install dca-core@dca-marketplace       # optional: the DCA method on top
```

## Author

**Christoph Bloemer** — [@chbloemer](https://github.com/chbloemer)
