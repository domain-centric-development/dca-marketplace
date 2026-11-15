---
id: STAGE-PLAN-9B
part: told
why: delivery could not update the spec without knowing which criteria a story adds, keeps, changes or moves
stages:
- plan
section: Do
order: 13
---

# STAGE-PLAN-9B

9b. **Derive the spec delta.** Read `product/spec/<context>/scenarios.md` and every `<feature>/scenarios.md` below it
   (context lowercase, hyphenated; none → holds nothing yet). `feature:` says where the criteria go (none: the context's
   own file).
   - A new feature: the skeleton writes `- adds feature <name>`; propose its glossary entry under `## Glossary
     proposals` (`<Term> (<name>): <what it groups>`, `Type: Feature`) — delivery refuses a feature without one.
   - A criterion under another feature moves: `- moves <key>: <from> → <to>` (skeleton).
   - The skeleton's `## Spec delta` gives per key `adds`, `holds` (word for word) or `changes`. Add what only you see:
     `- removes <key>: <why>`; `- rule "<old>" → "<new>"` where the story rewords a rule (the spec's criteria under it
     follow without being the story's; `- holds <key>` for one is accepted). A rule `## Changed expectations` quotes that
     the story no longer writes is such a rewording — the test gate refuses a delta without its line.
   - A change or removal not following from `## Changed expectations` = agreed behaviour changed unsaid → one decision
     record naming the keys (as step 9), stop. Conversely, a `## Changed expectations` line altering a spec criterion
     the story does not carry with its new text would leave the old text standing → one decision record naming the
     keys and the text each needs, stop.
