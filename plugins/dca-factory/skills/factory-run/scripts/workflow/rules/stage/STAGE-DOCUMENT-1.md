---
id: STAGE-DOCUMENT-1
part: told
stages:
- document
section: Do
order: 2
---

# STAGE-DOCUMENT-1

1. Read the plan's glossary proposals and the diff's new names. Every **domain** identifier the
   story introduced — an aggregate, a value object, an event, a use case, a domain term in a result
   — needs an entry in the bounded context's glossary (`product/spec/<context>/glossary.md`, the one file under
   `spec/` you write — the context's `scenarios.md` is the gate's); a use case is no glossary type of its own —
   it is an `Operations` line on the term it acts on — the domain word with the code word in
   parentheses, as the plan proposed it — or a `Concept` where it names a term nobody had. Add the missing ones in the project's own
   words, taking the definition from the plan's proposal where there is one — through the skill the
   profile names as `carrier.glossary:` (the glossary skill, where installed), so the glossary's format
   is described in one place; by hand in the glossary's existing format otherwise. A term nobody can
   define is a term the model should not carry: say so rather than inventing a definition.
   The skeleton's `## Glossary` table already carries one row per proposed term, the term **as the plan
   wrote it**: write each entry from its row and keep the term's words in the entry's heading — the
   domain word, with the code word in parentheses where they differ (`### Titel (TaskTitle)`). The
   gate finds a term by any of those words, case aside, anywhere in a glossary file; a term you leave
   out goes under `## Not documented` with what it waits for, and nowhere else (`factory-cli.py
   --contract glossary` says the rule and the entry's shape).
