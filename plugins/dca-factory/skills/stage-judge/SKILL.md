---
name: stage-judge
description: Judge stage of a factory run — reviews the story's change from three perspectives (ddd, hexagonal, clean-code) plus any the profile adds, keeps only defects it can confirm in the code, and returns one verdict. Use after the tidy stage of a story, when the orchestrator asks for the review, or on "/stage-judge". Reports defects; it does not fix them. Internal stage of the pipeline — factory-run starts it; by hand only to redo this one stage of a story that has the ones before.
---

# Judge one story's change

Input: the story and its epic (`epic.md` beside it), `.dca-factory/runs/<story>/plan.md`, `tests.md`, `build.md`, the diff of the change —
`.dca-factory/runs/<story>/.verify/story.diff`, which the pipeline writes; open a whole file only where the
diff's context does not carry the question, and explore no further than a finding needs — the
product and the technical description (`project/product.md`, `project/tech.md`, or where the
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

The change is reviewed from **ddd**, **hexagonal** and **clean-code**, one pass each, kept apart in the
report. These three are part of the method, not project configuration: they always run and no
profile switches them off. The passes are not yours where a review file exists: the pipeline starts
one reviewer per perspective before you, each applying its skill in its own context, and you
**converge** — read `reviews/<perspective>.md`, confirm every must-fix and should-fix in the code at the
file and line it names (or drop it, with the reason), deduplicate across the files, and judge. A
reviewer that did not build and a judge that did not review is the point of the split; a judge who
reviews again in its own context puts the bias back that the files took out. Only a perspective
**without** a file is yours to run — load its carrier and say so. There is no fourth built-in: the method's own audit skill, where a
project has one, is an *added* perspective the profile names — worth it for an adoption, where the
question is how the existing code stands against the method, and not for a story that the rule
suite already holds to it.

What the project configures is what it *adds* and *who runs it*:

| Profile key | Meaning |
|---|---|
| `reviews: dca, security` | **additional** perspectives, on top of the three. Default: none |
| `review.ddd: <carrier>` | the reviewer that should carry a perspective — for the three built-ins too (`review.hexagonal:`, `review.clean-code:`, `review.<added>:`) |

A **carrier** is whatever this tool can actually run under that name: a review skill (portable —
every tool reads skills) or, in a tool that has separate review agents, such an agent. Resolve each
perspective in this order:

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

1. **ddd** — is the model right? (`review-ddd`: aggregates and invariants, entity against value
   object, events, the language, repository against store.)
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

4. Deduplicate findings that describe the same defect and drop anything the project's own rule
   suite already enforces — a rule catches it every run, a review comment does not.
5. Discard style preferences, speculative concerns and anything you cannot point at in the code.
   Every remaining finding names a file, a line and the fix.
5a. An **unplanned invariant** the build file names — a guard it found necessary and left out, since the plan
   did not name it — is a confirmed `minor` against the plan (`plan` perspective), with the rule as its fix; a
   guard in a changed domain type that the plan's `## Invariants` does not name and no unit test covers is
   the same finding, whoever wrote it.
6. Check the story once more against the criteria: is each one actually met by behaviour, not just
   by a green test? A test that asserts too little is a **test** defect and belongs in the report.

## Ask, do not recall

Where the profile names `knowledge: <skill>`, ask it instead of your recollection whenever an
answer would decide something, and cite the node by its path inside the catalog; never adopt a
knowledge source the profile did not name. The rule in full: `factory-run/reference/stage-common.md`,
beside this skill.

## The verdict has three values, not two

Which value you choose decides where the run goes back to, and that is the point of this stage:

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
| Perspective | File:line | Severity | Defect | Fix |

## Considered and dropped
- <finding>: <why it is not a defect>

## Criteria re-checked
- <criterion key>: met | met only nominally — <what the test does not assert>

## Previous round                  (repeat rounds only)
- <defect the previous verdict confirmed>: fixed — <file:line that shows it> | withdrawn — <why it
  was not a defect after all> | still open — listed above
```

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

A `minor` you confirm is not lost with the run folder: when the story is delivered, the pipeline copies every
row of `## Confirmed defects` into `<story>.findings.md` beside the story (`| # | Perspective | File:line |
Severity | Defect | Fix | Status |`, `open` until a person or a later story closes it). So a row you write
here is a row somebody will read later — file and line exact, the fix one sentence.

`verdict: pass` means the change is deliverable. Say it plainly when it is true; inventing a
finding to look thorough costs a build round and teaches the pipeline nothing. Every finding
names the file and line it stands on — a finding without that is a suspicion and is marked as one.

## Adopt mode

For a story with `status: adopted`, the change is not code but a claim: each mapped test proves its
scenario. Read every test against its scenario — does it arrange the `Given`, perform the `When` and
assert every `Then` and `And` with the scenario's values? A test that passes without asserting the outcome,
or asserts another one, is **major**. A break that changes something the test does not depend on is major
too. The verdict is `pass` only when every scenario is proved; nothing else is reviewed — nothing was built.

## Do not

- Do not edit code or tests.
- Do not report what the architecture rule suite already fails on — the gate runs it in the build
  stage, so a finding it catches is already blocking; repeating it double-counts one defect.
- Do not rate style, formatting or personal preference.
