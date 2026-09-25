---
name: factory-setup
description: Sets up the delivery pipeline in a project and does only what is missing — the project description (through the project's description skill), a git repository, the runner, gate and commit hook, and the stack-profile lines for what the project's code has gained. Idempotent, in any order relative to the code — before the first line of code, after it, or in an existing project. Use when a project has no factory yet, when the backlog skill says the project description is missing, after a browser runner or a formatter was added, or on "/factory-setup". Writes no story and no code, and never updates an installed pipeline (that is /factory-update).
---

# Set up the factory

The factory has three parts, and this skill sees to each one: a **project description** (what is to
be built), a **backlog** of epics and stories, and a **runner** that works through them. Input: the
project. Output: what was missing, and one line for everything that was already there.

```
project/                   what is to be built (a person writes it)
  product.md · tech.md · domain.md
  backlog/<epic>/epic.md · <story>.md
.agents/factory/           how it is worked through (the machine: profile, gate, runner)
tasks/<story>/             the stages' hand-overs
docs/                      what exists and why — written after the code, some of it generated
```

## Do — check each, do only what is missing

1. **The project description.** Run `python3 .agents/factory/story-gate.py --project` where the
   gate is installed; otherwise look for the files the `AGENTS.md` section
   `<!-- dca-describe: start -->` names, `project/product.md` and `project/tech.md` by default.
   Missing or incomplete → use the project's description skill where it is installed — the skill
   whose description says it writes the project description (in a DCA project `dca-describe`) —
   and let it write the files with the person. Where no such skill is installed, say so, name
   the skill and the headings the guide gives the description (product: what and for whom,
   surfaces, how it works, look and feel, qualities, not part of the product; tech: stack, frontend
   approach, persistence, runtime, integrations, version policy), and write no template yourself.
   The designed domain (`project/domain.md`) is optional here.
2. **Git.** `git rev-parse --is-inside-work-tree`. Not a repository → offer `git init` and run it on
   the person's confirmation. The pipeline's commit hook and its worker lock live in `.git`; the
   setup script stops without one, so a repository is never created behind anyone's back.
3. **The runner.** No `.agents/factory/factory.sh` → run the pipeline's setup from this skill's
   pipeline, for the tool you are:
   `bash <this skill's folder>/../factory-run/scripts/factory.sh setup --tool <claude|codex|opencode>`,
   and report what it printed. It works without code: what it cannot detect it leaves out of the
   stack profile. It writes the profile first — the build commands the presets detect, and a
   carrier line only for a method skill that is installed beside the pipeline — then links the
   skills, copies the gate, the runner and the observer, installs the commit hook and the pipeline's
   section in `AGENTS.md`.
4. **What the profile does not know yet.** The runner is there → run
   `bash .agents/factory/factory.sh setup --check`. It lists the detected keys the profile lacks
   (a browser runner, a formatter, a carrier skill installed since) and the values that differ from
   detection. Show them. On the person's confirmation run `setup --write`; it adds the missing keys
   and never overwrites a value a person wrote. A differing value is theirs to keep or to replace
   (`setup --write --replace <key>`, on their word).
4a. **Acceptance.** Where the product description's `## Surfaces` names web pages and the profile
   has no `acceptance:`, propose `acceptance: pages` — a story with something to see then waits for a
   human's look before it is delivered — and a `run:` line with how a person starts the application.
   Write both on the person's confirmation; `none` is their answer too.
5. **Everything present** → say so in one line per part, and name the next step: `/factory-backlog`
   for the first epic, or `/dca-new` where the project has a description and no code yet.

The three ways in all end at the same files:

```
/factory-setup → /dca-new → /factory-setup → /factory-backlog → /factory-run      description first
/dca-new → /factory-setup → /factory-backlog → /factory-run                       code first
/factory-setup                                                                    an existing project
```

## Structural questions

A plan that needs a new bounded context, a new relationship between contexts or a surface an actor
lacks writes a decision record like any other question; `/factory-decisions` takes the answer and
brings the project description in line. This skill does not answer them.

**Speak in skills.** You run the commands; the person gets the result and, for a next step, the
skill that does it (`/factory-backlog`, `/factory-status`, `/factory-run`) — never a shell command
to type, unless the person asks how to do something without a session. You may run `factory.sh` for
everything that starts no tool — `setup`, `backlog`, `status`, `decisions`, `update`, `verify`,
`check` — but never `run`: it starts a tool process per stage on top of this session.

## Do not

- Do not write a story, an epic or code, and no description text of your own — the description is
  the person's, written through the description skill.
- Do not touch an installed runner, gate or hook: replacing them is `/factory-update`, kept apart on
  purpose so a setup never changes what governs a project.
- Do not run `git init`, `setup --write` or a move without the person's confirmation.
- Do not call a skill that writes code (`/dca-new`, `/dca-init`) yourself; name it as the next step.
