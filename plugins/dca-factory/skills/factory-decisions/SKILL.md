---
name: factory-decisions
description: The decision inbox of a delivery run — lists the questions stages could not answer, explains one from its record and the story it blocks, and writes the human's answer into the record on their explicit confirmation. Use when a run stopped with needs-human, when someone asks what is waiting on them, to answer a question from a second session, or on "/factory-decisions". Answers nothing itself and implements nothing.
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

1. **List what is waiting.** Run `bash .agents/factory/factory.sh decisions` (add `--story <id>`
   for one story; `python3 .agents/factory/story-gate.py --list-decisions` does the same). It prints one line per record — id, state, story and
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
5. **Show the exact wording before it is written.** Present the `## Answer` block you are about to
   append — `answer:`, `by:`, `at:`, `rationale:` — and the record it goes into. Write it when the
   human confirms **that block**. An instruction explicit enough to leave nothing open ("write
   answer b, by me, rationale: archived is history") is the confirmation; do not ask again once it
   is given. Ordinary discussion — "b sounds right" in the middle of weighing — is not.
6. **`by:` is the person, `at:` is now.** Ask whose decision it is if it is not obvious from the
   session; the git `user.name` is a suggestion to confirm, not an answer. `at:` is the current
   time in UTC, ISO 8601. You are not the decider and your name goes nowhere in the record.
7. **Never overwrite an answer.** A record that already has `## Answer` is answered; say so, show
   it, and stop. A change of mind is a new question — say that the stage would have to ask again,
   and why the old answer stays as history. A draft (an `## Answer` without `by:` or `at:`) may be
   completed with the missing lines once the human confirms it is theirs.
8. **Say what happens next, and do not do it.** After writing: name the stage that asked and how the
   story continues — a worker that is running (`/factory-run --watch`, `/loop /factory-run`) picks it
   up by itself; otherwise `/factory-run <story>` resumes it at that stage. Answering a question is not taking over the story; the worker that asked
   applies the answer, and the gate stamps the record applied when it has. If the human wants to
   go on interactively in *this* session, they say so — then it is a hand-over, named as one.

**Speak in skills.** You run the commands; the person gets the result and, for a next step, the
skill that does it (`/factory-status`, `/factory-decisions`, `/factory-run <story>`,
`/factory-backlog`) — never a shell command to type. A command belongs in your answer only when the
person asks how to do it without a session.

## Do not

- Do not write `## Answer` from a recommendation, a timeout, a majority of options or your own
  judgement. The whole file exists so that a suggestion cannot be mistaken for a decision.
- Do not edit anything but the record — not the story, not the plan, not the code. The stage that
  asked propagates the answer; two writers on one plan is how an answer gets applied twice.
- Do not invent a record. A question that reached you as a sentence and has no file is the asking
  stage's omission; the next gate refuses it, and the fix is that stage writing the record.
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
