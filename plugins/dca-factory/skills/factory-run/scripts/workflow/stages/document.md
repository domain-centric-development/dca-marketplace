---
name: document
role: delivers
order: 6
hand_over: document.md
window: verifier
kinds:
- story
- journey
- task
traits:
- gated
- post_gated
- in_order
commands:
- architecture
sizes:
- judge.md
- document.md
---

# document

Brings the project's own documents in line with what the story changed — the glossary, the context map, the reader documentation.

<!-- frame: what the stage is told, each rule by its marker -->

Read what every stage is told first (its file: in the prompt).

Input, nothing else: the story, `plan.md`, `build.md`, `judge.md`, and `.dca-factory/evidence/<story>/story.diff`
(no diff → `changed.txt`).
Output: the updated documents and `.dca-factory/runs/<story>/document.md`, started by
`factory-cli.py --document-skeleton <story>` (the runner runs it; by hand, run it first): headings and `## Paths` —
every changed and run file **as it resolves from the project root**. Fill the tables, cite paths from `## Paths` in
exactly that form, keep the section. **Checkable** statements only.

## Do

<!-- rule: STAGE-DOCUMENT-0 -->
<!-- rule: STAGE-DOCUMENT-1 -->
<!-- rule: STAGE-DOCUMENT-2 -->
<!-- rule: STAGE-DOCUMENT-3 -->
<!-- rule: STAGE-DOCUMENT-4 -->
<!-- rule: STAGE-DOCUMENT-5 -->

## Ask, do not recall

`knowledge: <skill>` in the profile: ask it, cite the node path; never a source the profile does not name.

## The document file

```markdown
# Document — <story id>

## Glossary
| Term | Context | Added or changed | Definition source |

## Documents updated
| File | What changed | Verified by |

## Not documented
- <thing>: <why, and what it waits for>           (one line each)

## Paths                           (written by the pipeline — the paths you may cite, in this form; keep it)
- `<path from the project root>`

## needs-human                     (only when the run must stop — otherwise leave the heading out)
```

- Fill the tables, run the gate once, fix exactly what it refuses. A size `gate:note` is information only.
- `Verified by`: the file read or command run; a row without it is a claim. Cite a path from the project root with
  its line (`src/main/java/com/example/billing/domain/model/BookId.java:8`, never `BookId.java:8`) — the gate resolves
  each one.
- Never list `document.md` itself under `## Documents updated`.
- Nothing to list → one row with `—` in the first column and, under `Verified by`, what you read to know it.

## Do not

<!-- rule: STAGE-DOCUMENT-NOT1 -->
<!-- rule: STAGE-DOCUMENT-NOT2 -->
<!-- rule: STAGE-DOCUMENT-NOT3 -->
<!-- rule: STAGE-DOCUMENT-NOT4 -->
