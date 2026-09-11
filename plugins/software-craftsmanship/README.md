# software-craftsmanship

Project-agnostic craftsmanship skills and a reviewer agent. Usable on any
Java or .NET project — **no DCA assumptions**. Pairs naturally with
[dca-core](../dca-core/) for the full Domain-Centric Architecture practice,
but stands on its own.

## Start here

Pick the skill for what you are about to do — `/tdd` before writing new behaviour, `/clean-code`
while editing, `/adr` when a decision needs to outlive the conversation, `/e2e-testing` when a
user-visible flow needs a test. Nothing has to be set up first, and none of it assumes DCA.

## What's inside

### Skills (5) — applied while writing

| Skill | Purpose | When it triggers |
|---|---|---|
| `/tdd` | Red-Green-Refactor workflow guidance | Adding new behavior |
| `/clean-code` | Naming, function size, SLAP, smells, Boy-Scout-Rule | Any code edit |
| `/adr` | Architecture Decision Records (Michael Nygard format, immutable after Accepted) | Non-trivial architectural choice |
| `/e2e-testing` | The end-user-testing craft: Page Objects, stable selectors, one flow per test, explicit waits, diagnosis-first when a test breaks | Adding or fixing an end-user test |
| `/review-craft` | The **craft** review perspective: naming, function size and SLAP, SOLID, smells, DRY with judgement | Reviewing a change for readability |

### Agents (2) — the same craft in an isolated context

| Agent | Applies | Adds |
|---|---|---|
| `e2e-tester` | `/e2e-testing` | own context, write tools — for a long test-writing session |
| `clean-code-reviewer` | `/review-craft` | own context, read-only tools — no "fix" slips into a review |

**Knowledge lives in the skill, isolation in the agent.** Each agent is a thin wrapper that applies
its skill and adds nothing to it: an agent exists only in a tool that has agents, so craft held in
an agent alone would be unavailable everywhere else.

## Why these are separate from dca-core

These four bricks are **valuable independent of DCA**:

- `/tdd` works in any codebase with a test runner.
- `/clean-code` and `clean-code-reviewer` apply to any Java or C# code,
  whether the architecture is hexagonal, layered, MVC, or none of the above.
- `/adr` is a project-management practice — useful even on a quick-and-dirty
  service.

Keeping them in a separate plugin means projects can adopt craftsmanship
without buying into DCA's architectural commitments.

## Pairing with dca-core

When both plugins are installed, several useful interactions emerge:

| Pairing | Effect |
|---|---|
| `/tdd` + `/dca-discipline` (from dca-core) | TDD cycles with DCA invariants checked on each Green |
| `/adr` + `/dca-discipline` | When a DCA rule is bent intentionally, ADR records the exception with reasoning |
| `/adr` + `/context-map` (from dca-core) | Strategic context-map changes get recorded as architectural decisions |
| `clean-code-reviewer` ∥ `ddd-reviewer` ∥ `hexagonal-reviewer` (parallel) | Three perspectives, three reports |

`software-craftsmanship` works **without** dca-core; the pairings above
become available when dca-core is also installed.

## Conventions overlay

Skills and agents read this optional file if present:

```
<project-root>/.claude/dca/conventions.md
```

(The `dca/` subpath is historical from this marketplace's origin — the
file works for both plugins.)

It can override:
- Test source set paths (`src/test/`, `src/test-integration/`, etc.)
- Test framework choice (JUnit 5, Spock, xUnit)
- Formatter command (e.g. `./gradlew spotlessApply`, `dotnet format`)
- ADR storage path

Falls back to `<project-root>/CLAUDE.md`, then to sensible defaults.

## What this plugin deliberately does NOT include

- **DCA-specific tooling** — see dca-core.
- **Code generators / scaffolds.**
- **Formatter / static-analysis replacement.**
- **BDD / Cucumber** — separate concern, not yet captured here.

## Installation

```
/plugin marketplace add domain-centric-development/dca-marketplace
/plugin install software-craftsmanship@dca-marketplace
/plugin install dca-core@dca-marketplace                  # optional companion
```

## Author

Christoph Bloemer · neuland Büro für Informatik
