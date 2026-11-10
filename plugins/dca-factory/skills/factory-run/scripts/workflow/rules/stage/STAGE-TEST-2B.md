---
id: STAGE-TEST-2B
part: told
why: unknown
stages:
- test
section: Do
order: 4
---

# STAGE-TEST-2B

2b. **A journey item** (`kind: journey`) is a guard over delivered stories: one test that walks the
   epic's `## Journey` to its outcome event, in the source set `test.journey:` declares. It is
   **green** when you finish — every step exists already — and it asserts the outcome event, not
   only a page. It gets no stub for the production code and writes no production code.
