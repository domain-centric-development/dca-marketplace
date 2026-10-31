---
name: document
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

First read what every stage is told — a session the runner started, one session that carries
several stages, a repeat round, the shell, the gate. The runner's prompt names its file and this
brief repeats none of it.

Input: the story, `.dca-factory/runs/<story>/plan.md`, `build.md`, `judge.md`, and the diff —
`.dca-factory/evidence/<story>/story.diff`, which the pipeline writes (where it says there is no diff,
`changed.txt` lists the files). Nothing else.
Output: the updated documents, plus `.dca-factory/runs/<story>/document.md` — which the pipeline starts for
you: `factory-cli.py --document-skeleton <story>` (the runner runs it; in a session run it yourself before
the stage) writes the file's headings and, under `## Paths`, every file the story changed and every run
file **as it resolves from the project root**. Fill the tables; cite paths from that section in exactly
that form; leave the section in place.

A story is not delivered when its code is green and its documents describe the system as it was
yesterday. This stage closes that gap — and it closes it with **checkable** statements only.

## Do

<!-- rule: STAGE-DOCUMENT-0 -->
<!-- rule: STAGE-DOCUMENT-1 -->
<!-- rule: STAGE-DOCUMENT-2 -->
<!-- rule: STAGE-DOCUMENT-3 -->
<!-- rule: STAGE-DOCUMENT-4 -->
<!-- rule: STAGE-DOCUMENT-5 -->

## Ask, do not recall

Where the profile names `knowledge: <skill>`, ask it instead of your recollection whenever an
answer would decide something, and cite the node by its path inside the catalog; never adopt a
knowledge source the profile did not name. The rule in full: in what every stage is told.

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

Run the document gate once your tables are filled and fix exactly what it refuses. A `gate:note` — the
file's size against its measure — is information, never a reason to trim a cell or run the gate again
(what every stage is told).

`Verified by` names how you checked a statement — the file you read, the command you ran. A row
without it is a claim, and the gate treats it as one. A file you cite is a path from the project root
with its line — `src/main/java/com/example/billing/domain/model/BookId.java:8`, never `BookId.java:8`:
the gate resolves every cited path, and a bare name resolves to nothing. `document.md` itself is the
hand-over, not a document the project keeps: it is never listed under `## Documents updated`.

When a table has nothing to list — no term added, no document changed — write one row with `—` in
the first column and, under `Verified by`, what you read to know that nothing had to change. The
gate reads `—` as "no file", never as a path.

## Do not

<!-- rule: STAGE-DOCUMENT-NOT1 -->
<!-- rule: STAGE-DOCUMENT-NOT2 -->
<!-- rule: STAGE-DOCUMENT-NOT3 -->
<!-- rule: STAGE-DOCUMENT-NOT4 -->
