---
id: STAGE-TEST-NOT3
part: told
why: a stage changed what an older test expected and turned a contradiction green unnoticed
stages:
- test
section: Do not
order: 19
---

# STAGE-TEST-NOT3

- Never change what an earlier test expects unless the plan lists and backs it under `## Changed tests` (`GATE-TESTS-KEPT`); elsewhere add a case. Allowed without a question: a new argument where a built type gains a field, a locator finding the same `data-test` marker on a moved path — assertions, expected values and matchers unchanged. A contradicting test the plan missed → decision record, `stage: test`.
