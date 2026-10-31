---
id: STAGE-COMMON-32
part: told
section: A question is a decision record
marked: factory-run/reference/stage-common.md
---

# STAGE-COMMON-32

The gate refuses a `## needs-human` that names no record. When you run again on a story whose
record is answered — asked by your stage, or answered `applies: <your stage>` — read the answer,
apply it, and cite the id in your file where it landed (`Decision <id> answered <option>: …`); the
gate stamps the record applied only then, and refuses a file that does not cite it.
