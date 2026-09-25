---
name: factory-decisions
description: The decision inbox of a delivery run — lists the questions stages could not answer, explains one from its record and the story it blocks, and writes the human's answer into the record on their explicit confirmation; for a structural question (a new bounded context, a new relationship, a surface an actor lacks) it also brings the designed context map and the product description in line. Use when a run stopped with needs-human, when someone asks what is waiting on them, to answer a question from a second session, or on "/factory-decisions". Answers nothing itself and implements nothing.
---

# Read, explain and record a decision

Input: the records under `.agents/factory/decisions/`, the story and the stage file each one
names, and what the human says. Output: at most one `## Answer` section per record, in the human's
words, on their say-so. You write no plan, no test and no code, and you never write an answer that
was not given to you.

The record's contract is in `factory-run/reference/file-contracts.md`, *Decision records*; read it
once per project. The state of a record is read off the file: no `## Answer` is **open**; one with
`answer:`, `by:` and `at:` is **answered**; a gate-written `## Applied` is **applied**; an
`## Answer` missing the name or the time is a **draft**, and a draft unblocks nothing.

## Do

1. **List what is waiting.** Run `bash .agents/factory/factory.sh decisions` (add `--story <id>` for
   one story, `--format md` in a session; `python3 .agents/factory/story-gate.py --list-decisions` where there is no runner copy). It prints one row per record — id, state, story and
   stage, when it was asked, the question — open ones first. Show that, in that order. Where the
   gate is not installed, read the directory yourself and say that you did.
2. **Explain one from its files, not from memory.** Read the record: the question, the options,
   the evidence the stage cited, its recommendation. Read the story it names and the stage file
   that asked (`tasks/<story>/<stage file>`, ending in `## needs-human`). Say what is asked, why
   the stage could not decide it, what each option costs, and what the stage recommended —
   **marked as the stage's recommendation**, never blended into your own reading. Where the record
   cites a file and line, read it before you repeat the claim.
3. **Discuss without touching the file.** The human may weigh the options, ask what a term means,
   reject the premise, want a third option, or defer. All of that changes nothing on disk. A
   question you cannot answer from the files is a question back to them, said as one.
4. **Take the answer only from the human.** An answer is an option key from the record or the
   human's own words. It is not the recommendation because nobody objected, not the option you
   find best, not a default, and not silence. If what they said is incomplete — "b, but only for
   archived ones older than a year" is an answer *and* a constraint the story must carry — say
   what you would write and where the rest goes (the story, via the backlog skill).
4a. **Measure the answering.** Explaining and answering a story's questions is part of what the story
   cost. When you start on a record, run `python3 .agents/factory/story-gate.py --window-start decisions
   --story <its story>`; once its answer is written (or the human defers), `--window-end decisions
   --story <its story>`. The window claims nothing and starts nothing.
5. **Show the exact wording before it is written.** Present the `## Answer` block you are about to
   append — `answer:`, `by:`, `at:`, `rationale:` — and the record it goes into. Write it when the
   human confirms **that block**. An instruction explicit enough to leave nothing open ("write
   answer b, by me, rationale: archived is history") is the confirmation; do not ask again once it
   is given. Ordinary discussion — "b sounds right" in the middle of weighing — is not.
6. **`by:` is the person, `at:` is now.** Ask whose decision it is if it is not obvious from the
   session; the git `user.name` is a suggestion to confirm, not an answer. `at:` is the current
   time in UTC, ISO 8601. You are not the decider and your name goes nowhere in the record.
7. **Never overwrite an answer.** A record whose `## Answer` carries `answer:`, `by:` and `at:` is
   answered; say so, show it, and stop. A change of mind is a new question — say that the stage would have to ask again,
   and why the old answer stays as history. A draft (an `## Answer` without `by:` or `at:`) may be
   completed with the missing lines once the human confirms it is theirs.
8. **Say what happens next, and do not do it.** After writing: name the stage that asked and how the
   story continues — a worker that is running (a listening session, or the person's runner) picks
   it up by itself; otherwise `/factory-run <story>` resumes it at that stage. Answering a question is not taking over the story; the worker that asked
   applies the answer, and the gate stamps the record applied when it has. If the human wants to
   go on interactively in *this* session, they say so — then it is a hand-over, named as one.

## A structural question

Three questions no stage answers itself, and a plan that meets one writes a record for it like any
other: the behaviour needs a **bounded context** the designed map does not have; it needs a
**relationship between two contexts** that does not exist yet; its actor needs a **surface** — a
page, an endpoint, a consumer — the context does not have, and with it a decision about who may use
it. Explaining one takes more than the record:

1. **Try the map there is first.** Read the designed map (`domain:` in the stack profile,
   `project/domain.md` by default) and the one generated from the code. A new context is the
   expensive answer, and most questions do not need it: the behaviour may belong to a context that
   already owns the language, or be a second use case in one. Say why the existing contexts do
   *not* fit — a different lifecycle, a different language for the same word, a different team, an
   invariant that cannot span the boundary. "It feels separate" is not a reason.
2. **Name the subdomain type** a new context would have — core, supporting or generic — because it
   decides how much pattern the context earns, and **the relationship** in the project's own
   vocabulary, with a direction and a reason, and who owns the contract.
3. **For a surface, separate what it is from who may use it.** The second is an authorisation
   decision; say where its check belongs by the project's own rule. A guard nobody decided is a
   guard no test holds.
4. **"Not now" is an answer too**, recorded like any other: the behaviour waits, the story is
   dropped, or a smaller piece fits the map as it stands.

Once the human has answered and the `## Answer` is written, bring the description in line **in the
same step** — this is the one place you write beyond the record: the designed map through the
skill the profile names as `carrier.domain:` (the context-map skill, where installed; by hand in its
format otherwise), a new surface in the product description's `## Surfaces`. A decision that is not
on the map is one the next plan cannot read: the plan gate checks the story's context against the
designed map first. Where the answer still waits on the domain contact, the map stays as it is —
say so, so it reads as a state and not as an oversight. Then say what changes for the story; the
story itself is `/factory-backlog`'s.

## An acceptance

A record with `kind: acceptance` was written by the document gate, not by a stage: every gate
passed and the profile's `acceptance:` asks a human to look before the story counts as delivered.
The record lists the criteria with their tests and how to start the application (`run:`). A human
accepts — no role is checked; the answer is theirs, on their confirmation, as always.

- **Accepted** — write `answer: accepted`, then run the document gate
  (`python3 .agents/factory/story-gate.py --story <story> --stage document`): it delivers the story.
  The story's commit follows — the code, the tests and `tasks/<story>/`.
- **A correction** — what the human wants different, in their words: write `answer: correction:
  <their words>`, then bring it into **the same story** through the backlog skill's rules: changed or
  new criteria, one `answered:` line under `## Assumptions` naming the record id, and under
  `## Changed expectations` what the story had delivered that no longer holds. The story then runs
  again from plan — the schedule sees it changed — in its own `tasks/<story>/`, holding the checkout
  until it is accepted.
- **Before a story was accepted, every answer is a correction**, a changed criterion included; the
  rounds counter bounds how often. **After it was accepted**, adding what the story left unsaid is a
  correction; changing or taking back a criterion is a **new wish** — a new story through
  `/factory-backlog` with `## Changed expectations`. Say which it is and let the human decide; the
  gate refuses to reopen a story for a changed criterion after an acceptance.
- **A story already delivered** — the human looked after delivery: write a record for it yourself
  (`<story>-accept-<n>`, `kind: acceptance`, `stage: document`, `digest:` of the story now) with their
  correction as the answer, write the correction into the story as above, then take it back with
  `python3 .agents/factory/story-gate.py --reopen <story>`. It refuses without an answered
  correction the story cites.

**Speak in skills.** You run the commands; the person gets the result and, for a next step, the
skill that does it (`/factory-status`, `/factory-decisions`, `/factory-run <story>`,
`/factory-backlog`) — never a shell command to type, unless the person asks how to do something
without a session. You may run `factory.sh` for everything that starts no tool — `setup`,
`backlog`, `status`, `decisions`, `update`, `verify`, `check` — but never `run`: it starts a tool
process per stage (`claude -p` and the like) on top of this session, and the runner refuses it
inside one anyway.

## Do not

- Do not write `## Answer` from a recommendation, a timeout, a majority of options or your own
  judgement. The whole file exists so that a suggestion cannot be mistaken for a decision.
- Do not edit anything but the record — not the story, not the plan, not the code — apart from the
  project description after a structural answer, and the story after an acceptance correction
  (both above). The stage that asked propagates the
  answer; two writers on one plan is how an answer gets applied twice.
- Do not invent a record. A question that reached you as a sentence and has no file is the asking
  stage's omission; the next gate refuses it, and the fix is that stage writing the record. The one
  record you write is a human's acceptance correction for a story already delivered (above).
- Do not summarise several records into one answer. Each is answered on its own, even when the
  same word settles them all.

## Example

```
$ python3 .agents/factory/story-gate.py --list-decisions
US-3-01  open      US-3/plan  asked 2026-09-22T20:40:00Z  Does an archived entry count?
US-2-01  applied   US-2/plan  asked 2026-09-21T09:12:00Z  Which currency does the total carry?  → b by the-expert
decisions: 2 record(s), 1 waiting for an answer — store .agents/factory/decisions/
```

Explained: "US-3 (plan stage) asks whether archived entries count as 'the thing' the reader
sees. The plan cites the glossary, `docs/glossary.md:41`, where *archived* is a state, and the
story's criterion `shows-the-thing`, which does not say. Options: a — shown and marked; b —
hidden. The stage recommends b. Nothing is decided until you say."

Human: "b. Archived is history, not inventory. Write it as mine."

Shown, then written on that confirmation:

```markdown
## Answer
answer: b
by: <the human's name>
at: 2026-09-22T21:04:00Z
rationale: archived is history, not inventory.
```

"Written to `.agents/factory/decisions/US-3-01.md`. The plan stage asked; a running worker picks it
up by itself, otherwise `/factory-run US-3` resumes it at the plan stage — it re-plans with the
answer, and the gate stamps the record applied."
