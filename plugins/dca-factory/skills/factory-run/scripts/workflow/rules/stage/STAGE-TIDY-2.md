---
id: STAGE-TIDY-2
part: told
why: a tidy move on a test could weaken what it asserts or let it pass without the code
stages:
- tidy
section: Do
order: 2
---

# STAGE-TIDY-2

2. Every test green, **no test's claim changed** (`GATE-TESTS-KEPT`, `GATE-RED-REPROOF`): story tests and shared support take only moves keeping what each asserts (a copy lifted into support — earlier copies too at the third —, a page object instead of a raw locator, a method named after its display name, a stale comment or dead helper deleted) — never an assertion, expected value, `gate:tests` selector or scope; each changed test file is a `## Moves` row; a moved test must stay red on the test stage's tree, so never rename production code a test calls.
