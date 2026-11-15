---
id: STAGE-TIDY-4
part: told
why: synonyms the glossary says to avoid and stale doc comments survived in the story's own code
stages:
- tidy
section: Do
order: 4
---

# STAGE-TIDY-4

4. Ordinary moves only:
   - a name saying what the thing is in the project's vocabulary, doc comments too — a `Synonyms (avoid)` word is always
     replaced by its term;
   - a function split where two levels of abstraction share one;
   - a duplicate lifted once;
   - a comment deleted where the code now says it; one the change made wrong or too narrow rewritten to what holds, in
     this file's terms;
   - a value object where a primitive carried meaning.
   Each small, each leaving the tests green — run the touched test or class between moves; the whole suite runs once, in
   the gate.
