---
id: STAGE-TEST-ROUND
part: told
stages:
- test
section: A round sent back to this stage
order: 15
---

# STAGE-TEST-ROUND

Where `judge.md` in the run folder says `verdict: changes-requested`, fix exactly the confirmed defects
that are this stage's — a test that asserts too little, with its break (see the contract) — nothing else.
When the judge's verdict says `back: test` (`.dca-factory/runs/<story>/judge.md`), fix exactly the test
defects it confirmed: add the assertion the criterion names, nothing else. When the build stage wrote
`back: test` (`.dca-factory/runs/<story>/build.md`), a test cannot pass because of its own code — a
helper, a locator, a page object: repair exactly that, and leave what the test asserts as it is. The code already meets it, so
the strengthened test is green and can never be seen red. Prove instead that it bites: write its
**break** — `.dca-factory/runs/<story>/breaks/<fully.qualified.Class>--<method>.patch`, a `git apply` patch
against the production code, the smallest change that removes what the new assertion checks (the word
from the template, the link from the page). The gate applies it on a scratch copy, runs the test, wants
it red, and records the test's new version; the tree stays as it is. A test you did not change needs no
break. List the changed tests and their breaks under `## Files`.
