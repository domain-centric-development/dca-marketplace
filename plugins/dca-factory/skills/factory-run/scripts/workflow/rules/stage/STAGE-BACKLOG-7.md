---
id: STAGE-BACKLOG-7
part: told
why: work built outside the pipeline either looked undelivered or counted as delivered without any check
section: Delivered by hand
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/backlog-contract.md
---

# STAGE-BACKLOG-7

A story a person built — by hand, with another tool, where the factory never ran — is delivered by hand:
`status: delivered`, `delivered:` (UTC) and `delivered_by: hand:<who>`, written by hand or by
`factory-cli.py --deliver-by-hand <story> --by <who>`, committed with the trailer `Story: <id>`. The views
read it as **delivered, claimed**; the schedule never runs it. `factory-cli.py --prove <story>` sets it
`status: adopted` and removes the three lines (the claim is kept in the story's evidence as `claim`); the adopt
path then checks it — every criterion on a green test, a break for every test it writes, a fresh judge — and the
adopt gate delivers it with `delivered_by: gate`. A delivered story is not delivered a second time: a change of
delivered behaviour is a new story with `## Changed expectations`.
