---
id: STAGE-TEST-ROUND
part: told
why: a too weak test sent to the build could not be fixed there, and a strengthened green test needed a break to show it bites
stages:
- test
section: A round sent back to this stage
order: 15
---

# STAGE-TEST-ROUND

`judge.md` says `verdict: changes-requested`: fix exactly this stage's confirmed defects — a test asserting too little,
with its break — nothing else.
- `back: test` from the judge: add the assertion the criterion names, nothing else.
- `back: test` from `build.md`: a test cannot pass because of its own code (helper, locator, page object) — repair exactly
  that; what it asserts stays.
The code already meets a strengthened test, so it is never seen red: prove it bites with its **break**,
`.dca-factory/runs/<story>/breaks/<fully.qualified.Class>--<method>.patch` — a `git apply` patch, the smallest production
change removing what the new assertion checks (the word from the template, the link from the page). The gate applies it
on a scratch copy, wants red, records the test's new version; the tree stays. An unchanged test needs no break. List
changed tests and breaks under `## Files`.
