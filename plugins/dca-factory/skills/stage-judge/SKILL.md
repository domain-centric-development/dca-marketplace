---
name: stage-judge
description: Judge stage of a factory run — reviews the story's change from three perspectives (domain, boundaries, craft), keeps only defects it can confirm in the code, and returns one verdict. Use after the build stage of a story, when the orchestrator asks for the review, or on "/stage-judge". Reports defects; it does not fix them.
---

# Judge one story's change

Input: the story, `tasks/<story>/plan.md`, `tests.md`, `build.md`, the diff of the change —
`tasks/<story>/.verify/story.diff`, which the pipeline writes; open a whole file only where the
diff's context does not carry the question, and explore no further than a finding needs — the
product scope — and, in a repeat round, the previous verdict, `tasks/<story>/.judge-previous.md`.
Nothing else. A change that contradicts the product scope — a surface it does not list, state kept
where it says otherwise, a page without its stated look or accessibility, something under
`## Not part of the product` — is a finding like any other.
Output: `tasks/<story>/judge.md`. You change no code.

## Do

Review the change from **domain**, **boundaries** and **craft**, one pass each, kept apart in the
report. These three are part of the method, not project configuration: they always run and no
profile switches them off.

What the project configures is what it *adds* and *who runs it*:

| Profile key | Meaning |
|---|---|
| `reviews: security, performance` | **additional** perspectives, on top of the three. Default: none |
| `review.domain: <carrier>` | the reviewer that should carry a perspective — for the three built-ins too |

A **carrier** is whatever this tool can actually run under that name: a review skill (portable —
every tool reads skills) or, in a tool that has separate review agents, such an agent. Resolve each
perspective in this order:

1. the carrier its `review.<name>:` names, when this tool offers it;
2. otherwise a review skill of the project whose own description covers that perspective — a skill
   named for the perspective (`review-domain`, `review-boundaries`, `review-craft`) is the obvious
   case, but match on what a skill's description says it reviews, never on its name alone;
3. otherwise, for the three built-ins, the description below — you run the pass yourself.

Say in the report which of the three it was. A named carrier that this tool does not offer is a
missing *preference*, not a missing review: the built-in pass still runs, and the report says so
("in-session; `<carrier>` not available here"). An **added** perspective is different — it has no
built-in description, so if its carrier is unavailable it is reported as **not covered** and nothing
silently stands in for it.

1. **domain** — is the model right? Real invariants inside the aggregate rather than an anemic
   record with setters; the correct choice between entity and value object; aggregate boundaries
   that one transaction can hold; domain events in the past tense, published where the fact
   occurs; the vocabulary of the criteria and the glossary in the code, with no synonym drift; a
   repository only for an aggregate root.
2. **boundaries** — do the dependencies point inward? The domain free of framework types; ports
   declared in the inner layers and implemented in adapters; no raw import across a bounded
   context; input ports carrying commands, queries and results rather than domain objects;
   translation at the edge, not in the middle.
3. **craft** — is it readable? Names that say what a thing is; functions on one level of
   abstraction; no duplication that carries a decision twice; no dead code, no leftover stub, no
   comment describing history instead of the present state.

Where the profile says `browser: playwright`, an end-user test that reads a page's script or markup as
text in place of driving the browser is a **major** finding: it proves the wording, not the behaviour,
and the project has the runner that would prove the behaviour.

Across the three, check the change against the story itself. A criterion written as a scenario is
covered only when its test arranges the `Given`, performs the `When` and asserts every `Then` and
`And` with the scenario's values: an outcome the test does not assert is a finding. Behaviour listed
under the story's `## Out of scope`, or under the product scope's `## Not part of the product`, that
the change delivers anyway is a finding too.

An added perspective is one more pass with its own rows in the report. Adding one is a profile
line plus the skill that carries it — never an edit to this file.

Then converge:

4. Deduplicate findings that describe the same defect and drop anything the project's own rule
   suite already enforces — a rule catches it every run, a review comment does not.
5. Discard style preferences, speculative concerns and anything you cannot point at in the code.
   Every remaining finding names a file, a line and the fix.
6. Check the story once more against the criteria: is each one actually met by behaviour, not just
   by a green test? A test that asserts too little is a **test** defect and belongs in the report.

## Ask, do not recall — but only a source the project named

Where the stack profile names a **knowledge skill** — `knowledge: <skill>`, one that answers
architecture questions from a catalog and cites the node it read — use it instead of your own
recollection whenever the answer would decide something: which pattern applies, why a rule exists,
whether a construct is a pitfall, what a recipe prescribes. Name the node you relied on in your
file, the way you name a file and line for a claim about the code.

**Never adopt a knowledge source the profile did not name.** A catalog that happens to be installed
may be a vendored copy of an older release: its rule ids, marker names and recipes can describe a
version the project does not use, and a citation makes that wrongness look verified. If you notice
such a skill, say so in your file — "`<skill>` is available but not named in the profile, so it was
not used" — and decide from the project's own rules, markers and documents instead. Those are the
source of truth; a catalog is a convenience the project has to vouch for.

Without a `knowledge:` entry, work from what the project itself carries: its rule catalog and the
report its architecture suite prints, its building blocks, its glossary, its documents. Nothing
here fails for the absence of a knowledge skill.

## The verdict has three values, not two

Which value you choose decides where the run goes back to, and that is the point of this stage:

| Verdict | Means | The run goes back to |
|---|---|---|
| `pass` | no blocking defect left | nowhere — the story is deliverable |
| `changes-requested` | the code deviates from the plan or is wrong | `stage-build` |
| `story-conflict` | the **plan or the story itself** was wrong: a criterion contradicts another, the design cannot meet it, or meeting it would need a decision nobody took | the story — a human, never `stage-build` |

Only `blocker` and `major` findings prevent `pass`. A review that finds something everywhere is
ignored and therefore worthless: rank, and let `minor` findings be recorded without blocking.
A `story-conflict` is a question to a human, so it is a **decision record** like any other: write
`## needs-human` in the judge file naming it (`decision: <story>-<nn>`), and the record at
`.agents/factory/decisions/<story>-<nn>.md` with the front matter `id:`, `story:`, `asked:` (UTC) and
`stage:` — the stage that will **apply** the answer, not yourself: `plan` when the story or the plan
has to change, `test` when an agreed expectation has to change. Say in `## Question` that the judge
asked. The run waits for the answer and resumes at that stage; everything after it runs again.
Never resolve a `story-conflict` by quietly reinterpreting the criterion — a correction that
changes an agreed decision belongs in the document, or after five rounds the story describes
something the code no longer does and nobody notices.

## The judge file

```markdown
# Judge — <story id>

## Verdict
verdict: <pass | changes-requested | story-conflict>

## Perspectives covered
- <perspective>: <the skill or agent that ran it, or "in-session"> | not covered — <why>

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

Where the plan lists `## Changed tests`, check each changed test against the line that backs it:
the new assertion follows from that line, and nothing else in the test changed. A changed test
that expects more or other than its backing line says is a `major` defect.

In a repeat round, account for **every** defect the previous verdict confirmed before you judge
anew. A defect does not disappear because this round's reading missed it: it is fixed, with the
line that shows it, or withdrawn, with the reason — and a withdrawal that contradicts the source
the previous round cited (a glossary line, a criterion) is a `story-conflict`, not a `pass`.

`verdict: pass` means the change is deliverable. Say it plainly when it is true; inventing a
finding to look thorough costs a build round and teaches the pipeline nothing. Every finding
names the file and line it stands on — a finding without that is a suspicion and is marked as one.

## Do not

- Do not edit code or tests.
- Do not report what the architecture rule suite already fails on — the gate runs it in the build
  stage, so a finding it catches is already blocking; repeating it double-counts one defect.
- Do not rate style, formatting or personal preference.
