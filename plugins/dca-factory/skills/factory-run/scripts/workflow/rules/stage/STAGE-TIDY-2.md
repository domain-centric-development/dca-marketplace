---
id: STAGE-TIDY-2
part: told
stages:
- tidy
section: Do
marked: stage-tidy/SKILL.md
order: 2
---

# STAGE-TIDY-2

2. Keep every test green, and **change no test's claim**. The story's tests and the shared test support
   take moves that keep what each test asserts: a copy lifted into the shared support — the earlier
   copies too, at the third one —, a page object called instead of a raw locator, a test method named
   after its display name, a stale comment or a dead helper of the story's tests deleted. Never an
   assertion, an expected value, a selector of the `gate:tests` table or a test's scope — a test that
   asserts too little is a finding for the judge, and a change of what it expects is a human's
   decision. Each test file you change is a row under `## Moves`. The tidy gate runs every mapped
   test you moved on the tree the test stage left, with your test files laid over it (`red-reproof`):
   it must be red there as it was, so a move that renamed production code a test calls, or let a test
   pass without the code, is refused. A test that existed before the story keeps what it expects, as
   at every stage.
