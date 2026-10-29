# Kinds of backlog items, and a change without one

Part of the `factory-run` skill: what its *Other kinds of item* section points to — an adopted story, a story
delivered by hand, a journey item, several factories on one backlog, and a change outside any story.

## Outside a story

A direct edit gets the same checks without a story: `python3 .agents/factory/story-gate.py
--change` runs the profile's compile, test, architecture and format commands and fails a required
one (the profile's `required:` line) that is missing, left out or ran no test. `--staged` checks
what a commit contains and refuses when the working tree differs from the index; the commit hook
is that command, and CI runs `--change` on its checkout. Recommend it when someone asks whether a
change is ready to commit — do not invent a story for it. `--parity <config>` checks that several
implementations each prove a scenario contract from their reports (`reference/file-contracts.md`).


## An adopted story

A story with `status: adopted` describes behaviour the project already has (`--kind` prints `adopt`). It
runs **plan, test, judge**, then the **adopt gate** (`story-gate.py --story <id> --stage adopt`) — skip
build, tidy and document, nothing is built. The stages work in adopt mode: the plan names where each
scenario's behaviour lives and which existing test covers it, and the invariants of the domain types the
scenarios exercise; the test stage maps those tests, gives every invariant a unit test of its own, writes a
characterization test with its break for a scenario or a rule without one, and changes no production code and
no existing test; its gate expects every mapped test **green**. The judge confirms each test asserts its
scenario. The adopt gate checks it all again, applies every break to a scratch copy, and delivers the
story — `status: delivered`, `delivered_by: gate`, the same end state as a built story. A judge's
`changes-requested` or a refused adopt gate sends it back to the test stage.


## A story delivered by hand

A person who built a story themselves marks it `factory-cli.py --deliver-by-hand <story> --by <who>`
(`status: delivered`, `delivered:`, `delivered_by: hand:<who>`): delivered, claimed; the schedule never runs
it. `factory-cli.py --prove <story>` sets it `status: adopted`, and the next run checks it as an adopted story
above — the gate then writes `delivered_by: gate`. Neither is the way to change a delivered story: a change of
delivered behaviour is a new story.


## Several factories on one backlog

With `claim_remote:` in the profile the runner claims each story on that remote before it runs it, skips one
another factory claimed, and publishes a delivered story on its branch instead of moving `main`. Running a story's
stages in a session yourself, claim it first: `python3 .agents/factory/factory-cli.py --claim-story <id>` — exit 3
means another factory has it: stop and say who.


## A journey item

A backlog item with `kind: journey` (`factory-cli.py --story <id> --kind` prints it) is a guard over
delivered stories. It runs **plan, test, judge, document** — skip build and tidy, there is nothing to
build — and its test gate expects the journey test **green**, the inverse of a story. A judge's
`changes-requested` sends it back to the test stage, not the build stage. Everything else — the gates,
the rounds, the decisions — is a story's.
