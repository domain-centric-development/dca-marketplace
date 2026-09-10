---
name: factory-backlog
description: Writes and checks the backlog a delivery run reads — an epic with its outcome event, or one story small enough for a single run, in the markdown-with-front-matter contract. Use when a story or an epic is to be added, split or repaired, when the plan gate refused a story as incomplete, or on "/factory-backlog". Never invents an intent, a goal, a metric or a domain contact.
---

# Write one backlog item

Input: what the human tells you, plus the project's context map and glossaries.
Output: `backlog/<epic>/epic.md`, `backlog/<epic>/<story>.md`, or a correction to one of them.
You write no plan, no test and no code. Run the pipeline separately once the item stands.

The full contract is in `factory-run/reference/backlog-contract.md`; read it before your first
item in a project. The templates are `factory-run/templates/backlog/{epic,story}.md.tmpl`.

## Do

1. **Find out what is being asked for.** An epic and a story are different things: an epic states
   why a body of work exists and how anyone will know it delivered; a story describes one piece of
   observable behaviour small enough for one run. If what you were told is one sentence about a
   button, it is a story; if it is a problem someone has, it is an epic and its first story.
2. **Never invent the four epic fields.** `intent`, `goal`, `metric` and `domain_contact` are the
   fields the gate refuses a story for, and it refuses it for a reason: a stage that cannot read
   the intent invents one. If the human has not stated them, ask — one question per missing field,
   in their words, not a form. A placeholder is worse than a missing file, because the gate passes
   it.
3. **The metric is an outcome event, not a count.** Ask which domain or integration event the
   project publishes when the epic has actually worked for someone — the event whose appearance in
   production is the evidence. A story count, a burndown or "feature shipped" is not a metric. If
   the project publishes no such event yet, say so in the epic: the event is then part of the work.
4. **Name the bounded context, and check the map.** A story's `context` must be a context the
   project's map already carries. If the behaviour would need a new context or a new relationship
   between contexts, do not write the story: say that it is a scoping question and what it would
   need. That decision is not one a story may smuggle in.
5. **Write criteria as observable behaviour, with keys.** One `- <key>: <criterion>` line each; the
   key is lowercase, hyphenated and names the behaviour (`shows-empty-state`). It is committed —
   the test stage records it next to the test that proves it — so never a number and never renamed
   later. Every concrete detail the human states (wording, order, placement) is its own criterion:
   a detail that is not a criterion is a detail no test will cover.
6. **Use the project's own words.** Read the context's glossary first and write the story in those
   terms. A term the story needs that no glossary carries goes into `## Assumptions` as a question
   for the domain contact, not into the story as if it were established.
7. **Assumptions are questions, never decisions.** Each line is `open:` or `answered:`. What the
   team decided itself belongs in the criteria or in a plan, not here. A story whose criterion
   contradicts one of its own open assumptions is not ready — the judge will stop the run for it,
   so resolve it now: either the assumption is answered, or the criterion is not yet a criterion.
8. **Leave `status: draft` unless the human releases it.** The gate refuses to plan a draft story,
   which is the one check no script can replace. Say plainly that the story is waiting for their
   release, and set `approved` only when they say so.
9. **Check it with the gate, not with your own judgement:**
   `python3 .agents/factory/story-gate.py --story <id> --stage plan`. Every finding it reports is
   yours to fix before you hand the item over. Report what it said.

## Splitting

A story one run cannot deliver is two stories, not a bigger one. The tell is not length but
seams: two actors, two contexts, a criterion that only makes sense after another has shipped.
Split along the seam, give each part its own keys, and put the order in `depends_on` — never a
"part 1 / part 2" pair whose halves are meaningless alone.

## Repairing an item the gate refused

Fix exactly what the gate named. An incomplete epic gets its missing fields from the human, not
from you; a story without a context gets one only if the map already has it; a criterion without a
key gets a key that names its behaviour. Do not rewrite the parts the gate did not complain about
— a story's wording is the domain contact's, not yours.

## Do not

- Do not write a plan, a test shape, an implementation hint or a file path into a story. What
  changes in the code is the plan stage's answer, and a story that prescribes it stops being a
  statement about behaviour.
- Do not migrate an existing backlog wholesale. The contract applies to new items; the gate only
  ever looks at the story it is called with, and rewriting finished work invents intents nobody
  stated.
- Do not touch `tasks/` — those are run artefacts, not backlog.
