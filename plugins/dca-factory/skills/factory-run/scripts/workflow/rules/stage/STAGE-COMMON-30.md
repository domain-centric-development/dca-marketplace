---
id: STAGE-COMMON-30
part: told
why: a stage question lived only in its transcript, so no other session found it and its answer had no place to land
section: A question is a decision record
order: 30
---

# STAGE-COMMON-30

A stage that cannot go on still writes its file, with `## needs-human` naming a **decision record**:
`decision: <story>-<nn>`, at `<story>/decisions/<nn>.md` (`nn`: the story's next two-digit number) — the question, the
options, the evidence read, your recommendation, never an answer. The story file and every `## Answer` are the
person's; a change to them stops the story. Shape: `factory-run/templates/decision.md.tmpl`; the gate reads exactly
this front matter and refuses a record whose `id:` differs from the file name (`GATE-DECISIONS`):
