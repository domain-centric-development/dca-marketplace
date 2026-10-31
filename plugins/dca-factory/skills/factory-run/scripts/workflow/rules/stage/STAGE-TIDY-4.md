---
id: STAGE-TIDY-4
part: told
stages:
- tidy
section: Do
marked: stage-tidy/SKILL.md
order: 4
---

# STAGE-TIDY-4

4. Take the ordinary moves and nothing exotic: a name that says what the thing is in the project's
   own vocabulary — in doc comments too, and a word the glossary lists under `Synonyms (avoid)` is
   always a move, replaced by its term — a function split where two levels of abstraction sit in one,
   a duplicate lifted once, a comment deleted where the code now says it, a comment or doc comment in
   a touched file that the change made wrong or too narrow rewritten to what holds now, a value object
   where a primitive was carrying meaning. A comment says what holds in this file, not what a source
   the reader cannot see says. Each move is small and each leaves the tests green — between moves run the
   tests the move touches (one test or one class, as `stage-common.md` says); the whole suite runs once, in the gate.
