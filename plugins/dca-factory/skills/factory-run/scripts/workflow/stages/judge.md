---
name: judge
role: judges
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

Reviews the story's change from the review perspectives and returns one verdict, which decides what comes after it; no gate of its own.

<!-- frame: what the stage is told, each rule by its marker -->

Read what every stage is told first (its file: in the prompt).

Input, nothing else: the story and its `epic.md`; `plan.md`, `tests.md`, `build.md`; `.dca-factory/evidence/<story>/story.diff`
(open a whole file only where the diff's context does not carry the question; explore no further than a finding
needs); `product/overview.md`, `product/tech.md` (or `product:`, `tech:`); **the review files**
`.dca-factory/runs/<story>/reviews/<perspective>.md`, one per perspective, written before you by reviewers in contexts
of their own; in a repeat round `.dca-factory/runs/<story>/.judge-previous.md`.
Output: `.dca-factory/runs/<story>/judge.md`. No code change.

A change against the product description (a surface it does not list, state kept where it says otherwise, a page
without its stated look or accessibility, anything under `## Not part of the product`) is a finding; so is one that
brings in what the technical description excludes (a second persistence, a client framework where pages are
server-rendered, an unlisted integration).

## Do

<!-- rule: STAGE-JUDGE-1 -->

The project adds perspectives and names who runs them:

| Profile key | Meaning |
|---|---|
| `reviews: dca, security` | **additional** perspectives, on top of the three. Default: none |
| `review.ddd: <carrier>` | the reviewer that should carry a perspective — for the three built-ins too (`review.hexagonal:`, `review.clean-code:`, `review.<added>:`) |

<!-- rule: STAGE-JUDGE-2 -->

1. the carrier `review.<name>:` names — a review **skill** in the project is offered by every tool: load it, run its
   pass; only an **agent** can be missing;
2. else a project review skill whose description covers that perspective — match on what the description says it
   reviews, never on the name alone;
3. else, for the three built-ins, the question below — a fallback, never a shortcut where a skill is installed.

Say which of the three it was. A named carrier this tool lacks is a missing preference, not a missing review: the
built-in pass runs and the report says "in-session; `<carrier>` not available here". An **added** perspective without
its carrier is **not covered** — nothing stands in for it.

<!-- rule: STAGE-JUDGE-3 -->
2. **hexagonal** — do the dependencies point inward? (`review-hexagonal`: framework-free domain,
   ports inside and adapters outside, no raw cross-context import, command/query/result shape,
   translation at the edge, an adapter that keeps what its port promises.)
3. **clean-code** — is it readable? (`review-clean-code`: names, one level of abstraction, no
   duplication that carries a decision twice, no dead code, no comment on history.)

Each perspective is described once — in the review skill named in parentheses (`review.<name>:`, installed by
`factory.sh setup`). Installed → load it; the question alone only without it, and `## Perspectives covered` says so.

**Major findings — check each, whatever a reviewer said:**

| Defect | Why major |
|---|---|
| with `browser:` other than `none`: an end-user test reads a page's script or markup as text instead of driving the browser | proves the wording, not the behaviour; the runner that would prove it is there |
| a browser test for a scenario that is neither the happy path nor `browser-only` with a reason in the plan | slow and flaky where an integrated test would do |
| an adapter the plan changed that no integration test passes through; a port mocked where the plan changed its adapter | the translation stays untested |
| a stored-state clause (stays, unchanged, done afterwards) asserted in an adapter test against stubbed input ports | it reads back the stub |
| a `Then` or `And` no test asserts — check each clause against its `## Clauses` row and the line it names, not the test name | the criterion is met only nominally |
| a journey test that stops short of the epic's outcome event; an outcome event named otherwise than the epic's `metric:` (`TaskAdded` where it says `TaskCreated`) | the outcome is measured by an event nobody publishes |

Minor: a test that rebuilds the application context per method where a data reset would do (`@DirtiesContext` on
every test, a new host per fact) — slow for nothing; the project's reset convention is the fix.

Against the story: a scenario is covered only when its test arranges the `Given`, performs the `When` and asserts
every `Then` and `And` with the scenario's values. Behaviour under the story's `## Out of scope` or the product's
`## Not part of the product` that the change delivers anyway is a finding.

An added perspective = one more pass with its own rows; adding one is a profile line plus its skill, never an edit
here.

Then converge:

<!-- rule: STAGE-JUDGE-4 -->
<!-- rule: STAGE-JUDGE-4A -->
<!-- rule: STAGE-JUDGE-5 -->
<!-- rule: STAGE-JUDGE-5C -->
<!-- rule: STAGE-JUDGE-5A -->
<!-- rule: STAGE-JUDGE-5B -->
<!-- rule: STAGE-JUDGE-6 -->
<!-- rule: STAGE-JUDGE-6A -->

## Ask, do not recall

`knowledge: <skill>` in the profile: ask it, cite the node path; never a source the profile does not name.

## The verdict has three values, not two

<!-- rule: STAGE-JUDGE-VERDICT -->

| Verdict | Means | The run goes back to |
|---|---|---|
| `pass` | no blocking defect left | nowhere — the story is deliverable |
| `changes-requested` | the code deviates from the plan or is wrong — or a test asserts less than its criterion | the build stage, or the test stage with `back: test` |
| `story-conflict` | the **plan or the story itself** was wrong: a criterion contradicts another, the design cannot meet it, or meeting it would need a decision nobody took | the story — a human, never the build stage |

- Only `blocker` and `major` prevent `pass`. Rank: a review that finds something everywhere is ignored; `minor` is
  recorded, never blocking.
- Translate the reviewers' ranks from what you confirmed in the code, never by copying: `must-fix` → `major`
  (`blocker` where it breaks a criterion, the architecture suite or the product description); `should-fix` →
  `minor` (`major` where you confirm it deviates from the plan); `nit` → `minor`.
- **Three domain defects are `major`** whatever the perspective or the plan says — you rank what the code does:
  - a rule over an aggregate's state decided outside the aggregate (`domain-invariant:`);
  - a precondition not checked again after an earlier read — a choice shown on one request and acted on by the next,
    a snapshot and its reload, a remote answer and the step that confirms it (`domain-invariant:`);
  - a result encoding three or more outcomes as flags or nullables a caller must decode, an impossible combination
    representable (`domain-concept:`) — found-or-not as one nullable is two outcomes, not this.
- `story-conflict` is a decision record (what every stage is told): `## needs-human` names it; its `stage:` is the
  stage that **applies** the answer — `plan` when story or plan change, `test` when an agreed expectation changes;
  `## Question` says the judge asked. The run resumes there.
- Never resolve a `story-conflict` by quietly reinterpreting the criterion: the story then describes something the
  code no longer does, and nobody notices.

## The judge file

```markdown
# Judge — <story id>

## Verdict
verdict: <pass | changes-requested | story-conflict>
back: test                        (only when a confirmed defect is in a test — see below)

## Perspectives covered
- <perspective>: reviews/<perspective>.md (<carrier>) | in-session — <why there was no file> | not covered — <why>

## Confirmed defects
| Perspective | File:line | Severity | Target | Type | Qualifier | In plain words | Defect | Fix |

## Considered and dropped
- <finding>: <why it is not a defect>

## Criteria re-checked
- <criterion key>: met | met only nominally — <what the test does not assert>

## Previous round                  (repeat rounds only)
- <defect the previous verdict confirmed>: fixed — <file:line that shows it> | withdrawn — <why it
  was not a defect after all> | still open — listed above
```

- The DDD perspective's domain-model defects start their Defect cell with `domain-concept:`, `domain-boundary:`,
  `domain-invariant:` or `domain-term:`.
- **Where the round goes.** `changes-requested` goes to build, which may not change a test (its red proof holds each
  test's version). A confirmed defect in a test itself (asserts less than its criterion, proves it only nominally) →
  `back: test` under the verdict: the test stage strengthens it and proves the new assertion bites with a break;
  build follows for any code defect beside it. No test defect → no `back:` line.
- `## Changed tests` in the plan: each changed test's new assertion follows from its backing line and nothing else in
  it changed; expecting more or other is `major`.
- Repeat round: account for **every** defect the previous verdict confirmed before judging anew — fixed (with the
  line) or withdrawn (with the reason). A miss in this round's reading does not make it disappear. A withdrawal that
  contradicts the source the previous round cited (a glossary line, a criterion) is a `story-conflict`, not a `pass`.
- **In plain words**: one short sentence a person understands without opening the file, in the product's or the
  code's-purpose words — "the checkout controller checks the step twice", not "repeats `Page`'s guard check
  (`:133`–`:143`)". No code name, no line, no reviewer term; precision stays in `Defect`, the remedy in `Fix`.
- At delivery every `## Confirmed defects` row is copied to `<story>/findings.md` (`| # | Perspective | File:line |
  Severity | In plain words | Defect | Fix | Status |`, `open` until closed): file and line exact, plain sentence and
  fix one sentence each.
- `verdict: pass` when true; an invented finding costs a build round and teaches nothing. A finding without file and
  line is a suspicion and marked as one.

## Task mode

<!-- rule: STAGE-JUDGE-TASK -->

## Adopt mode

<!-- rule: STAGE-JUDGE-ADOPT -->

## Do not

<!-- rule: STAGE-JUDGE-NOT1 -->
<!-- rule: STAGE-JUDGE-NOT2 -->
<!-- rule: STAGE-JUDGE-NOT3 -->
