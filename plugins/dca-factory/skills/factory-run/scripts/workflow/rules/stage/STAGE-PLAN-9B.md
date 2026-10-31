---
id: STAGE-PLAN-9B
part: told
stages:
- plan
section: Do
order: 13
---

# STAGE-PLAN-9B

9b. **Derive the spec delta.** Read the story's context's spec — `product/spec/<context>/scenarios.md` and every
   `<feature>/scenarios.md` below it, the context lowercase and hyphenated; a context without one holds nothing yet.
   The story's `feature:` says which file its criteria go to (none: the context's own). A feature the context does
   not have yet is born here: the skeleton writes `- adds feature <name>`, and the plan proposes its glossary entry
   (`<Term> (<name>): <what it groups>`, `Type: Feature`) under `## Glossary proposals` — the document stage writes
   it, and the delivery refuses a feature without one. A criterion that stands under another feature moves; the
   skeleton writes `- moves <key>: <from> → <to>`. The skeleton's `## Spec delta`
   already says, key by key, what the comparison finds: `adds` (the spec lacks it), `holds` (word for word
   there) or `changes` (there, otherwise). Add what only you can see: `- removes <key>: <why>` for a criterion
   of the spec the story takes away, and `- rule "<old>" → "<new>"` where the story rewords a rule — the criteria the
   spec holds under the old text follow it to the new one without being the story's (a `- holds <key>` for one
   is accepted); a criterion the story takes away is `removes`. A rule `## Changed expectations` quotes that the
   story no longer writes is such a rewording: the test gate refuses a delta without its line. A change or removal must follow from
   the story's `## Changed expectations`; where it does not, it is a change of agreed behaviour nobody said —
   one decision record naming the keys, as in step 9, and stop. The other way round as well: a line of
   `## Changed expectations` that alters a criterion the spec holds, while the story does not carry that key
   with its new text, would leave the spec's old text standing — one decision record naming the keys and
   the text each would need, and stop.
