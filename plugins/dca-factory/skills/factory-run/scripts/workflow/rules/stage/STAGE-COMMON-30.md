---
id: STAGE-COMMON-30
part: told
why: a stage question lived only in its transcript, so no other session found it and its answer had no place to land
section: A question is a decision record
order: 30
---

# STAGE-COMMON-30

A stage that cannot go on writes its file anyway, with a `## needs-human` section naming a
**decision record**: `decision: <story>-<nn>`, the record at `<story>/decisions/<nn>.md` in the
story (`nn` — the next two-digit number among this story's records) with the question, the options
you see, the evidence you read and your recommendation — never an answer. The story file and every
`## Answer` are the person's: the window's end compares them with its start, and a change stops the story
until a person confirms it. The full shape is
`factory-run/templates/decision.md.tmpl`, beside this file; the gate reads exactly this front matter,
and a record without `id:` equal to the file name is refused:
