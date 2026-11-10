---
id: STAGE-COMMON-32
part: told
why: an answered question was not visibly applied, so nobody could tell whether the stage had followed it
section: A question is a decision record
order: 32
---

# STAGE-COMMON-32

The gate refuses a `## needs-human` that names no record. When you run again on a story whose
record is answered — asked by your stage, or answered `applies: <your stage>` — read the answer,
apply it, and cite the id in your file where it landed (`Decision <id> answered <option>: …`); the
gate stamps the record applied only then, and refuses a file that does not cite it.
