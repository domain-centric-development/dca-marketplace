---
id: STAGE-DOCUMENT-1
part: told
why: the code gained domain names the glossary never defined, so the language drifted from the code
stages:
- document
section: Do
order: 2
---

# STAGE-DOCUMENT-1

1. Every **domain** identifier the story introduced (aggregate, value object, event, domain term in a result) needs an
   entry in `product/spec/<context>/glossary.md` — the one file under `spec/` you write (`scenarios.md` is the gate's).
   - A use case is no glossary type: an `Operations` line on the term it acts on, domain word with code word in
     parentheses as the plan proposed — or a `Concept` where it names a term nobody had.
   - Definitions from the plan's proposals, in the project's words, through `carrier.glossary:` where installed (one
     place for the format); else by hand in the existing format.
   - A term nobody can define is not carried: say so, never invent a definition.
   - The skeleton's `## Glossary` has one row per proposed term as the plan wrote it: keep its words in the entry's
     heading — domain word, code word in parentheses where they differ (`### Titel (TaskTitle)`). The gate finds a term by
     any of those words, case aside. A term left out goes under `## Not documented` with what it waits for, nowhere else
     (`factory-cli.py --contract glossary`).
