---
id: STAGE-FILES-14
part: told
section: The change policy — `required:` in the stack profile
retired: describes a file's form for every reader, not what a stage does — it stays reference text in factory-run/reference/file-contracts.md
---

# STAGE-FILES-14

`story-gate.py --change` checks a change outside a story; `--staged` checks the Git index and refuses
when the working tree differs from it. The profile's `required:` line lists the checks that must
hold: `compile`, `architecture`, `format`, and each test command by its own profile key (`test`,
`test.<name>`, `e2eTest`), so an end-user suite that needs a running system can be declared without
every commit waiting for one. A required check fails when its command is not declared (at the build and tidy gates too) or — for
a test command — when no report written by the run shows an executed case. A required check outside
this run's scope (`--checks`) is reported as not run here, for a later scope such as CI to run; this
run does not fail on it. Once `required:` is declared, the policy decides: a check outside it that
ran red or ran nothing is reported, and does not fail the verdict.
