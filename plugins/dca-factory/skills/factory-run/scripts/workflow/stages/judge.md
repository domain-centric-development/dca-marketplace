---
name: judge
order: 5
hand_over: judge.md
window: verifier
kinds:
- story
- journey
- adopt
- task
traits:
- in_order
---

# judge

Reviews the story's change from the review perspectives and returns one verdict, which decides what comes after it; no gate of its own. Its skill: `stage-judge`.

<!-- frame: what the stage is told, each rule by its marker -->

First read `factory-run/reference/stage-common.md` — the rules every stage holds to: a session the
runner started, one session that carries several stages, a repeat round, the shell, the gate. The
runner's prompt names its path and repeats none of it.

Input: the story and its epic (`epic.md` beside it), `.dca-factory/runs/<story>/plan.md`, `tests.md`, `build.md`, the diff of the change —
`.dca-factory/evidence/<story>/story.diff`, which the pipeline writes; open a whole file only where the
diff's context does not carry the question, and explore no further than a finding needs — the
product and the technical description (`product/overview.md`, `product/tech.md`, or where the
profile's `product:` and `tech:` point) — **the review files** `.dca-factory/runs/<story>/reviews/<perspective>.md`,
one per perspective, written by the reviewers the pipeline started before you (each in a context of
its own, at the same time) — and, in a repeat round, the previous verdict,
`.dca-factory/runs/<story>/.judge-previous.md`. Nothing else. A change that contradicts the product description
— a surface it does not list, state kept where it says otherwise, a page without its stated look or
accessibility, something under `## Not part of the product` — is a finding like any other, and so
is a change that brings in what the technical description excludes: a second persistence, a client
framework where the pages are server-rendered, an integration it does not list.
Output: `.dca-factory/runs/<story>/judge.md`. You change no code.

## Do

<!-- rule: STAGE-JUDGE-1 -->

What the project configures is what it *adds* and *who runs it*:

| Profile key | Meaning |
|---|---|
| `reviews: dca, security` | **additional** perspectives, on top of the three. Default: none |
| `review.ddd: <carrier>` | the reviewer that should carry a perspective — for the three built-ins too (`review.hexagonal:`, `review.clean-code:`, `review.<added>:`) |

<!-- rule: STAGE-JUDGE-2 -->

1. the carrier its `review.<name>:` names — a review **skill** installed in the project is offered by every
   tool: load it and run its pass; only an **agent** can be missing;
2. otherwise a review skill of the project whose own description covers that perspective — a skill
   named for the perspective (`review-ddd`, `review-hexagonal`, `review-clean-code`) is the obvious
   case, but match on what a skill's description says it reviews, never on its name alone;
3. otherwise, for the three built-ins, the question below — the fallback for a project that has no such
   skill installed, never a shortcut where one is.

Say in the report which of the three it was. A named carrier that this tool does not offer is a
missing *preference*, not a missing review: the built-in pass still runs, and the report says so
("in-session; `<carrier>` not available here"). An **added** perspective is different — it has no
built-in description, so if its carrier is unavailable it is reported as **not covered** and nothing
silently stands in for it.

<!-- rule: STAGE-JUDGE-3 -->
2. **hexagonal** — do the dependencies point inward? (`review-hexagonal`: framework-free domain,
   ports inside and adapters outside, no raw cross-context import, command/query/result shape,
   translation at the edge, an adapter that keeps what its port promises.)
3. **clean-code** — is it readable? (`review-clean-code`: names, one level of abstraction, no
   duplication that carries a decision twice, no dead code, no comment on history.)

Each perspective is described in **one** place — the review skill named in parentheses, the one the
profile's `review.<name>:` points at and `factory.sh setup` installs beside the pipeline. This file
holds the question each asks, not the description. Where the skill is installed you load it — the
question is what you review from only in a project without it, and then `## Perspectives covered`
says so.

Where the profile names a browser runner (`browser:` other than `none`), an end-user test that reads a page's script or markup as
text in place of driving the browser is a **major** finding: it proves the wording, not the behaviour,
and the project has the runner that would prove the behaviour.

**Test levels are major findings too.** A browser test for a scenario that is neither the story's happy
path nor `browser-only` with a reason in the plan; an adapter the plan changed that no integration test
passes through; a port mocked where the plan changed its adapter — each is **major**: the first makes the
suite slow and flaky where an integrated test would do, the other two leave the translation untested. A
clause about what is stored (stays, unchanged, done afterwards) asserted in an adapter test against stubbed input
ports is **major**: it reads back the stub. So is a `Then` or `And` of a scenario that no test asserts — check each
clause against tests.md's `## Clauses` row and the line it names, not only the criterion's test name. A
journey test that stops short of the epic's outcome event is **major** as well, and so is a change that names the
epic's outcome event otherwise than its `metric:` does — a synonym, a translation (`TaskAdded` where the epic says
`TaskCreated`): the outcome is then measured by an event nobody publishes. A test that rebuilds the
application context per method where a data reset would do (`@DirtiesContext` on every test, a new host
per fact) is **minor**: it makes the suite slow for nothing, and the project's own reset convention is
the fix.

Across the three, check the change against the story itself. A criterion written as a scenario is
covered only when its test arranges the `Given`, performs the `When` and asserts every `Then` and
`And` with the scenario's values: an outcome the test does not assert is a finding. Behaviour listed
under the story's `## Out of scope`, or under the product description's `## Not part of the product`, that
the change delivers anyway is a finding too.

An added perspective is one more pass with its own rows in the report. Adding one is a profile
line plus the skill that carries it — never an edit to this file.

Then converge:

<!-- rule: STAGE-JUDGE-4 -->
<!-- rule: STAGE-JUDGE-4A -->
<!-- rule: STAGE-JUDGE-5 -->
<!-- rule: STAGE-JUDGE-5C -->
<!-- rule: STAGE-JUDGE-5A -->
<!-- rule: STAGE-JUDGE-5B -->
<!-- rule: STAGE-JUDGE-6 -->

## Ask, do not recall

Where the profile names `knowledge: <skill>`, ask it instead of your recollection whenever an
answer would decide something, and cite the node by its path inside the catalog; never adopt a
knowledge source the profile did not name. The rule in full: `factory-run/reference/stage-common.md`,
beside this skill.

## The verdict has three values, not two

<!-- rule: STAGE-JUDGE-VERDICT -->

| Verdict | Means | The run goes back to |
|---|---|---|
| `pass` | no blocking defect left | nowhere — the story is deliverable |
| `changes-requested` | the code deviates from the plan or is wrong — or a test asserts less than its criterion | `stage-build`, or `stage-test` with `back: test` |
| `story-conflict` | the **plan or the story itself** was wrong: a criterion contradicts another, the design cannot meet it, or meeting it would need a decision nobody took | the story — a human, never `stage-build` |

Only `blocker` and `major` findings prevent `pass`. A review that finds something everywhere is
ignored and therefore worthless: rank, and let `minor` findings be recorded without blocking.
The perspectives rank in their own words — `must-fix`, `should-fix`, `nit` — and you translate, from
what you confirmed in the code, never by copying: a `must-fix` is `major`, and `blocker` where it
breaks a criterion, the architecture suite or the product description; a `should-fix` is `minor`,
and `major` where you confirm it deviates from the plan; a `nit` is `minor`.
**Three domain defects are `major` whatever the perspective called them**, and whatever the plan says — you rank
what the code does: a rule over an aggregate's state decided outside the aggregate (`domain-invariant:`); a
precondition the command does not check again after an earlier read — a choice shown on one request and acted on by
the next, a snapshot and its reload, a remote answer and the step that confirms it (`domain-invariant:`); a result
that encodes three or more outcomes as flags or nullables a caller must decode, an impossible combination
representable (`domain-concept:`) — found-or-not as one nullable is two outcomes, not this.
A `story-conflict` is a question to a human, so it is a **decision record** like any other (`factory-run/reference/stage-common.md`):
`## needs-human` in the judge file naming it, and the record's `stage:` is the stage that will
**apply** the answer, not yourself — `plan` when the story or the plan has to change, `test` when an
agreed expectation has to change. Say in `## Question` that the judge asked. The run waits for the answer and resumes at that stage; everything after it runs again.
Never resolve a `story-conflict` by quietly reinterpreting the criterion — a correction that
changes an agreed decision belongs in the story, where a human decides it, or after five rounds the story describes
something the code no longer does and nobody notices.

## The judge file

```markdown
# Judge — <story id>

## Verdict
verdict: <pass | changes-requested | story-conflict>
back: test                        (only when a confirmed defect is in a test — see below)

## Perspectives covered
- <perspective>: reviews/<perspective>.md (<carrier>) | in-session — <why there was no file> | not covered — <why>

## Confirmed defects
| Perspective | File:line | Severity | In plain words | Defect | Fix |

## Considered and dropped
- <finding>: <why it is not a defect>

## Criteria re-checked
- <criterion key>: met | met only nominally — <what the test does not assert>

## Previous round                  (repeat rounds only)
- <defect the previous verdict confirmed>: fixed — <file:line that shows it> | withdrawn — <why it
  was not a defect after all> | still open — listed above
```

A defect the DDD perspective confirms about the domain model starts its Defect cell with what it gets wrong —
`domain-concept:`, `domain-boundary:`, `domain-invariant:` or `domain-term:` — the same codes a person's
correction carries, so a run's domain misses can be counted beside them.

**Where the round goes.** A `changes-requested` goes to the build stage, which may not change a test —
its red proof holds each test's version. When a confirmed defect is in a test itself (it asserts less
than its criterion, it proves the scenario only nominally), write `back: test` under the verdict: the
round then starts at the test stage, which strengthens the test and proves with a break that the new
assertion bites, and the build follows for whatever code defect you confirmed beside it. Without a test
defect, write no `back:` line.

Where the plan lists `## Changed tests`, check each changed test against the line that backs it:
the new assertion follows from that line, and nothing else in the test changed. A changed test
that expects more or other than its backing line says is a `major` defect.

In a repeat round, account for **every** defect the previous verdict confirmed before you judge
anew. A defect does not disappear because this round's reading missed it: it is fixed, with the
line that shows it, or withdrawn, with the reason — and a withdrawal that contradicts the source
the previous round cited (a glossary line, a criterion) is a `story-conflict`, not a `pass`.

**In plain words.** Every confirmed defect carries one short sentence a person understands at once, without
opening the file: what is wrong, in the words of the product or the code's purpose — "the checkout controller
checks the step twice", not "repeats `Page`'s guard check (`:133`–`:143`)". No code name, no line, no reviewer
term; the precise account stays in `Defect`, the remedy in `Fix`. A person deciding in the inbox reads this
sentence first and opens the rest only when it matters.

A `minor` you confirm is not lost with the run folder: when the story is delivered, the pipeline copies every
row of `## Confirmed defects` into `<story>/findings.md` in the story's folder (`| # | Perspective | File:line |
Severity | In plain words | Defect | Fix | Status |`, `open` until a person or a later story closes it). So a row
you write here is a row somebody will read later — file and line exact, the plain sentence and the fix one
sentence each.

`verdict: pass` means the change is deliverable. Say it plainly when it is true; inventing a
finding to look thorough costs a build round and teaches the pipeline nothing. Every finding
names the file and line it stands on — a finding without that is a suspicion and is marked as one.

## Task mode

<!-- rule: STAGE-JUDGE-TASK -->

## Adopt mode

<!-- rule: STAGE-JUDGE-ADOPT -->

## Do not

<!-- rule: STAGE-JUDGE-NOT1 -->
<!-- rule: STAGE-JUDGE-NOT2 -->
<!-- rule: STAGE-JUDGE-NOT3 -->
