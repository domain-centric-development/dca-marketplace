---
name: stage-document
description: Documentation stage of a factory run — brings the project's own documents in line with what the story changed: the glossary, the context map, and whatever the project keeps as reader documentation. Use after the judge stage of a story, when the orchestrator hands over the verdict, or on "/stage-document". Writes only statements that can be checked against the code.
---

# Document what the story changed

Input: the story, `tasks/<story>/plan.md`, `build.md`, `judge.md`, and the diff. Nothing else.
Output: the updated documents, plus `tasks/<story>/document.md`.

A story is not delivered when its code is green and its documents describe the system as it was
yesterday. This stage closes that gap — and it closes it with **checkable** statements only.

## Do

1. Read the plan's glossary proposals and the diff's new names. Every **domain** identifier the
   story introduced — an aggregate, a value object, an event, a use case, a domain term in a result
   — needs an entry in the bounded context's glossary. Add the missing ones in the project's own
   words, taking the definition from the plan's proposal where there is one. A term nobody can
   define is a term the model should not carry: say so rather than inventing a definition.
2. Update the context map when the story changed how contexts relate — a new upstream, a new
   translation site, a relationship that changed kind. A story that *needs* a new context or
   relationship should never have reached this stage; if you find one, write `## needs-human`.
3. Update the documents the project keeps for readers, and only where the story made them wrong:
   the package or namespace layout when it changed, a described flow that now works differently, a
   list of contexts or capabilities that is now incomplete. Where the project declares its
   documentation targets (in the stack profile or its own instructions), follow that declaration
   instead of guessing which file matters.
4. **Write only what you can verify.** Every path, file, class, method and command you put in a
   document must exist — check it, do not remember it. A documented path that does not resolve is
   worse than no documentation: it survives, gets cited, and sends the next reader nowhere.
   Write every path **as it resolves from the project root**, in your file and in the document you
   write — `src/main/java/com/example/billing/domain/glossary.md`, not the package- or
   namespace-relative shorthand `billing/domain/glossary.md`. A shorthand a reader has to complete
   is not a path: it reads like one, it cannot be opened, and it is indistinguishable from a typo.
   Add the line or the section separately (`file.md:149`, `Book.cs:28-31`) — the location is
   allowed and is not part of the file name.
5. Record what you did *not* document and why: a decision that belongs in an architecture decision
   record rather than a README, a term the domain contact has to define first, an open assumption
   the story never resolved.

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

## The document file

```markdown
# Document — <story id>

## Glossary
| Term | Context | Added or changed | Definition source |

## Documents updated
| File | What changed | Verified by |

## Not documented
- <thing>: <why, and what it waits for>

## needs-human                     (only when the run must stop)
```

`Verified by` names how you checked a statement — the file you read, the command you ran. A row
without it is a claim, and the gate treats it as one.

## Do not

- Do not write production code or tests; the story is already green and judged.
- Do not restate the story in prose. A document repeats a fact only where a reader needs it in that
  place; otherwise it points at where the fact lives.
- Do not describe history — no "changed in this story", no "previously". A document says what is
  true now; the story, the diff and the run's files carry the history.
- Do not add a term to the glossary that the code does not use, and do not rename a term in the
  code from here. Renaming is a story of its own.
